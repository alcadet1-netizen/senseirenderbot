import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram import Bot, Dispatcher
from aiogram.types import Update

from src.bot.native_widgets import HedgehogWidgetMiddleware
from src.services.duel_service import DuelService, Duel


@pytest.mark.asyncio
@pytest.mark.parametrize('text,reserved', [('ежа', True), (' ЁЖ ', True), ('еж', True),
                                          ('HEDGEHOG', True), ('music', False), ('sc_code', False)])
async def test_real_dispatch_native_inline_has_one_owner_not_music(text, reserved):
    dp = Dispatcher()
    dp.update.outer_middleware(HedgehogWidgetMiddleware(SimpleNamespace()))
    seen = []
    @dp.inline_query()
    async def generic_inline(query):
        seen.append(query.query)
    bot = Bot('123456:TEST')
    bot.session = AsyncMock()
    event = Update.model_validate({'update_id': 1, 'inline_query': {
        'id': '123', 'from': {'id': 7, 'is_bot': False, 'first_name': 'H'},
        'query': text, 'offset': ''}})
    await dp.feed_update(bot, event)
    assert seen == ([] if reserved else [text])
    bot.session.assert_not_called()


def setup_duels():
    container = MagicMock()
    container.mongo_client.database.users = AsyncMock()
    container.mongo_client.database.transactions = AsyncMock()
    service = DuelService(container)
    for i in range(2):
        service.duels[i] = Duel(id=i, challenger_id=10+i*2, opponent_id=11+i*2,
                               bet=100, chat_id=-100, bot=AsyncMock(), container=container)
    return container, service


@pytest.mark.asyncio
async def test_shutdown_refunds_once_cancels_timers_without_bot_or_archive_calls():
    container, service = setup_duels()
    timers = []
    for duel in service.duels.values():
        duel.timeout_task = asyncio.create_task(asyncio.sleep(3600))
        timers.append(duel.timeout_task)
    with patch.object(service, '_archive_duel', new_callable=AsyncMock) as archive:
        await asyncio.gather(service.shutdown(), service.shutdown())
        await service.shutdown()
        archive.assert_not_called()
    assert service.users.update_one.await_count == 4
    assert service.transactions.insert_one.await_count == 4
    assert all(t.cancelled() for t in timers)
    for duel in service.duels.values():
        assert duel.finished
        duel.bot.edit_message_text.assert_not_called()
    assert isinstance(await service.create_duel(1, 2, 100, -100, AsyncMock()), str)
    service.users.find_one.assert_not_called()


@pytest.mark.asyncio
async def test_shutdown_skips_finished_and_zero_bet_never_credits():
    _, service = setup_duels()
    service.duels[0].finished = True
    service.duels[1].bet = 0
    await service.shutdown()
    service.users.update_one.assert_not_called()
    service.transactions.insert_one.assert_not_called()


@pytest.mark.asyncio
async def test_shutdown_attempts_other_duels_and_propagates_failure():
    _, service = setup_duels()
    original = service._cancel_duel
    async def cancel(duel, reason, **kwargs):
        if duel.id == 0:
            raise RuntimeError('database unavailable')
        await original(duel, reason, **kwargs)
    with patch.object(service, '_cancel_duel', side_effect=cancel):
        with pytest.raises(ExceptionGroup):
            await service.shutdown()
    assert service.duels[1].finished
    assert service.users.update_one.await_count == 2


@pytest.mark.asyncio
async def test_main_shutdown_closes_mongo_even_when_refund_fails():
    from src.main import on_shutdown
    container = SimpleNamespace(duel_service=SimpleNamespace(shutdown=AsyncMock(side_effect=RuntimeError())),
                                mongo_client=SimpleNamespace(close=AsyncMock()))
    with pytest.raises(RuntimeError):
        await on_shutdown(AsyncMock(), container)
    container.mongo_client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_shutdown_waits_for_inflight_creation_escrow_registration():
    _, service = setup_duels()
    service.duels.clear()
    service._check_eligibility = AsyncMock(return_value=None)
    entered, release = asyncio.Event(), asyncio.Event()
    async def escrow(*args):
        entered.set()
        await release.wait()
        return True
    service._escrow_funds = escrow
    creation = asyncio.create_task(service.create_duel(1, 2, 100, -100, AsyncMock()))
    await entered.wait()
    stopping = asyncio.create_task(service.shutdown())
    await asyncio.sleep(0)
    assert not stopping.done()
    release.set()
    duel = await creation
    await stopping
    assert duel.finished and duel.timeout_task.cancelled()
    assert service.users.update_one.await_count == 2
