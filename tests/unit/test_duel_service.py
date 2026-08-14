import asyncio

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.services.duel_service import DuelService, Duel


@pytest.mark.asyncio
async def test_duel_process_decision_accept():
    container = MagicMock()
    service = DuelService(container)

    bot = AsyncMock()
    duel_id = 123
    duel = Duel(
        id=duel_id,
        challenger_id=1,
        opponent_id=2,
        bet=100,
        chat_id=999,
        bot=bot,
        container=container,
        challenge_message_id=555,
    )
    duel.timeout_task = MagicMock()
    service.duels[duel_id] = duel

    service._start_round = AsyncMock()

    res = await service.process_decision(duel_id, 2, "a")
    await asyncio.sleep(0)

    assert res == "✅ Принято! Смотрите ЛС."
    assert duel.accepted is True
    bot.edit_message_reply_markup.assert_called()


@pytest.mark.asyncio
async def test_duel_process_decision_decline_removes_duel():
    container = MagicMock()
    service = DuelService(container)

    bot = AsyncMock()
    duel_id = 123
    duel = Duel(
        id=duel_id,
        challenger_id=1,
        opponent_id=2,
        bet=100,
        chat_id=999,
        bot=bot,
        container=container,
        challenge_message_id=555,
    )
    service.duels[duel_id] = duel

    async def _cancel(duel_obj, _reason):
        duel_obj.finished = True
        service.duels.pop(duel_obj.id, None)

    service._cancel_duel = AsyncMock(side_effect=_cancel)

    res = await service.process_decision(duel_id, 1, "x")

    assert res == "Отклонено."
    assert duel_id not in service.duels


@pytest.mark.asyncio
async def test_duel_process_decision_wrong_user_cannot_accept():
    container = MagicMock()
    service = DuelService(container)

    bot = AsyncMock()
    duel_id = 123
    duel = Duel(
        id=duel_id,
        challenger_id=1,
        opponent_id=2,
        bet=100,
        chat_id=999,
        bot=bot,
        container=container,
        challenge_message_id=555,
    )
    service.duels[duel_id] = duel

    res = await service.process_decision(duel_id, 3, "a")
    assert res == "❜ Это не вам."
