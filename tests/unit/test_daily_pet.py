"""Restored ordinary photo reward and private native taps on one persisted deadline."""
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from aiogram.types import Update

from src.bot.native_widgets import HedgehogWidgetMiddleware, SendWidget
from src.core.exceptions import DailyAlreadyClaimedError
from src.services.daily_pet_service import DailyPetService
from src.services.hedgehog_service import GameError
from tests.unit.test_hedgehog_game import services


def setup():
    db, daily, _ = services()
    mongo = SimpleNamespace(database=db)
    service = DailyPetService(mongo, daily)
    container = SimpleNamespace(daily_pet_service=service, daily_service=daily,
        settings=SimpleNamespace(BASE_DIR=Path(__file__).resolve().parents[2], maintenance_mode=False, mini_app_url='https://bot.example'),
        user_service=SimpleNamespace(get_or_create=AsyncMock()))
    return db, service, container, mongo


async def issue(service):
    result, session = await service.claim(7)
    await service.activate(session['token'], 7, 100)
    return result, session['token']


@pytest.mark.asyncio
async def test_standard_immediate_then_each_tap_ten_percent_no_five_tap_cap():
    db, service, _, _ = setup()
    result, token = await issue(service)
    coins = db.users.docs[7]['coins']
    xp = db.users.docs[7]['xp']
    assert coins == 1000 + result['total_coins'] and xp == 500 + result['total_xp']
    with patch('src.services.daily_pet_service.time.time', return_value=105):
        for i in range(12):
            session = await service.tap(token, 7, str(i))
    assert session['taps'] == 12
    assert session['extra_coins'] == result['total_coins'] * 12 // 10
    assert db.users.docs[7]['coins'] == coins + session['extra_coins']
    assert db.users.docs[7]['xp'] == xp
    assert db.users.docs[7]['daily_streak'] == result['streak']


@pytest.mark.asyncio
async def test_deadline_includes_travel_no_reset_no_pet_keeps_standard():
    db, service, _, mongo = setup()
    result, token = await issue(service)
    with patch('src.services.daily_pet_service.time.time', return_value=114.999):
        payload = await service.widget_action(token, 7, 'v', '')
        assert payload['taps'] == 0
    restarted = DailyPetService(mongo, service.daily)
    assert (await restarted.activate(token, 7, 109))['deadline'] == 115
    with patch('src.services.daily_pet_service.time.time', return_value=115):
        payload = await restarted.widget_action(token, 7, 'p', 'late')
    assert payload['state'] == 'done' and payload['taps'] == 0
    assert db.users.docs[7]['coins'] == 1000 + result['total_coins']
    assert db.users.docs[7]['xp'] == 500 + result['total_xp']


@pytest.mark.asyncio
async def test_idempotence_duplicate_queries_restart_and_repeated_claim():
    db, service, _, mongo = setup()
    result, token = await issue(service)
    with patch('src.services.daily_pet_service.time.time', return_value=101):
        await asyncio.gather(*(service.tap(token, 7, 'one-id') for _ in range(8)))
        restarted = DailyPetService(mongo, service.daily)
        await restarted.tap(token, 7, 'one-id')
    assert db.users.docs[7]['daily_pet']['taps'] == 1
    await service.mark_delivered(token, 7)
    with pytest.raises(DailyAlreadyClaimedError):
        await service.claim(7)
    assert db.users.docs[7]['coins'] == 1000 + result['total_coins'] + result['total_coins'] // 10


@pytest.mark.asyncio
async def test_delivery_retry_uses_same_receipt_and_never_renews_clock():
    db, service, _, _ = setup()
    first, token = await issue(service)
    second, session = await service.claim(7)
    assert first == second and session['token'] == token
    assert (await service.activate(token, 7, 150))['deadline'] == 115
    assert db.users.docs[7]['coins'] == 1000 + first['total_coins']


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['owner', 'banned', 'next_day'])
async def test_rejects_foreign_owner_ban_and_expired_day(kind):
    db, service, _, _ = setup()
    _, token = await issue(service)
    if kind == 'banned':
        db.users.docs[7]['is_banned'] = True
    target = 8 if kind == 'owner' else 7
    if kind == 'next_day':
        db.users.docs[7]['hedgehog_day'] = '2099-01-01'  # A new daily receipt invalidates the old personal token.
    day = db.users.docs[7]['daily_pet']['day']
    with patch('src.services.daily_pet_service.utc_day', return_value=day):
        with pytest.raises(GameError):
            await service.tap(token, target, 'x')
    assert db.users.docs[7]['daily_pet']['taps'] == 0


@pytest.mark.asyncio
async def test_old_native_claim_cannot_obtain_a_second_daily_or_new_pet_session():
    db, service, _, _ = setup()
    from src.services.hedgehog_service import utc_day
    await service.daily.settle_hedgehog(7, True, utc_day())
    with pytest.raises(DailyAlreadyClaimedError):
        await service.claim(7)
    assert 'daily_pet' not in db.users.docs[7]


@pytest.mark.asyncio
async def test_real_bridge_personal_only_no_group_inline_or_shared_taps():
    db, service, container, _ = setup()
    _, token = await issue(service)
    middleware = HedgehogWidgetMiddleware(container)
    bot = AsyncMock()
    for i, (kind, owner) in enumerate([('supergroup', 7), ('private', 8), ('inline', 7), ('shared', 7), ('private', 7)]):
        query = {'id': str(i), 'from': {'id': owner}, 'data': f'dp:p:{token}'}
        if kind == 'inline':
            query['inline_message_id'] = 'opaque'
        else:
            query['chat'] = {'id': owner if kind == 'private' else -100, 'type': kind}
            query['message_id'] = 1
        event = Update.model_validate({'update_id': i, 'shared_widget_query' if kind == 'shared' else 'widget_query': query})
        with patch('src.services.daily_pet_service.time.time', return_value=101):
            await middleware(AsyncMock(), event, {'bot': bot})
        payload = json.loads(bot.call_args.args[0].data)
        assert ('error' in payload) is (i != 4)
    assert db.users.docs[7]['daily_pet']['taps'] == 1


@pytest.mark.asyncio
async def test_group_command_photo_and_deeplink_not_native_group_send():
    from src.bot.presenters.hedgehog_presenter import launch_hedgehog
    db, service, container, _ = setup()
    bot = AsyncMock()
    bot.me.return_value = SimpleNamespace(username='Senseigame_bot')
    message = SimpleNamespace(chat=SimpleNamespace(id=-100, type='supergroup'), bot=bot,
                              answer=AsyncMock(), answer_photo=AsyncMock())
    user = SimpleNamespace(id=7, username=None, first_name='H', last_name=None, is_bot=False)
    with patch('src.services.daily_pet_service.time.time', return_value=100):
        await launch_hedgehog(message, user, container)
    message.answer_photo.assert_awaited_once()
    call = message.answer_photo.call_args
    assert 'XP' in call.kwargs['caption'] and 'Серия:' in call.kwargs['caption']
    assert 'Бонус серии' not in call.kwargs['caption']
    assert len(call.kwargs['caption']) < 180
    link = call.kwargs['reply_markup'].inline_keyboard[0][0].url
    assert link.startswith('https://t.me/Senseigame_bot?start=pet_')
    bot.assert_not_called()
    assert db.users.docs[7]['daily_pet']['delivered']
    assert db.users.docs[7]['daily_pet']['deadline'] == 115


@pytest.mark.asyncio
async def test_private_link_sends_native_widget_without_extending_or_paying():
    from src.bot.presenters.daily_hedgehog import open_pet
    db, service, container, _ = setup()
    result, token = await issue(service)
    bot = AsyncMock()
    message = SimpleNamespace(chat=SimpleNamespace(id=7, type='private'), bot=bot, answer=AsyncMock())
    with patch('src.services.daily_pet_service.time.time', return_value=104):
        await open_pet(message, SimpleNamespace(id=7), container, token)
    bot.assert_awaited_once()
    widget = bot.call_args.args[0]
    assert isinstance(widget, SendWidget)
    assert widget.chat_id == 7 and 'TelegramWidget.request' in widget.html
    assert 'https://t.me/airchatton' in widget.html
    message.answer.assert_not_called()
    assert db.users.docs[7]['daily_pet']['deadline'] == 115
    assert db.users.docs[7]['daily_pet']['taps'] == 0
    assert db.users.docs[7]['coins'] == 1000 + result['total_coins']


@pytest.mark.asyncio
async def test_bank_cap_and_zero_bank_never_increase_xp_or_subtract_user_money():
    db, service, _, _ = setup()
    result, token = await issue(service)
    db.bank.docs['main']['balance'] = 2
    with patch('src.services.daily_pet_service.time.time', return_value=105):
        await service.tap(token, 7, 'a')
        session = await service.tap(token, 7, 'b')
    assert session['taps'] == 2 and session['extra_coins'] == 2
    assert db.bank.docs['main']['balance'] == 0
    assert db.users.docs[7]['coins'] == 1000 + result['total_coins'] + 2
    assert db.users.docs[7]['xp'] == 500 + result['total_xp']


@pytest.mark.asyncio
async def test_midnight_does_not_renew_or_shorten_an_existing_fifteen_second_window():
    db, service, _, _ = setup()
    _, token = await issue(service)
    with patch('src.services.daily_pet_service.utc_day', return_value='2099-01-01'), \
         patch('src.services.daily_pet_service.time.time', return_value=105):
        session = await service.tap(token, 7, 'a')
    assert session['deadline'] == 115 and session['taps'] == 1


@pytest.mark.asyncio
async def test_retired_group_inline_search_returns_empty_without_creating_a_game():
    from tests.unit.test_inline_hedgehog import setup as legacy_setup, search
    from src.infra.mtproto import bootstrap
    bootstrap.load_runtime()
    from telethon import types, functions, utils
    tl = SimpleNamespace(types=types, functions=functions, utils=utils)
    db, _, container, client, transport = legacy_setup(tl)
    # Historical test fixture restores old builder; reset to the real production entrypoint.
    from src.infra.mtproto.widgets import MtprotoWidgets
    transport.answer_inline_hedgehog = MtprotoWidgets.answer_inline_hedgehog.__get__(transport)
    await transport.on_update(search(tl))
    assert client.call_args.args[0].results == []
    assert not db.hedgehog_games.docs and not db.users.writes


def test_private_native_markup_sizes_and_tap_protocol():
    import zlib
    from src.widgets.daily_pet import to_daily_pet_html
    html = to_daily_pet_html('A'*32, Path('src/infra/storage/ega'),
        dict(state='playing', remaining_ms=5000, taps=3, extra_coins=16, base_coins=55))
    assert len(zlib.compress(html.encode(), 9)) <= 3900
    assert 'dp:' in html and '7 секунд' not in html
    assert "if(ended)ask('v')" in html
    assert "document.body.onclick=touch" in html
    assert "15 секунд" in html and "openTelegramLink" in html
    assert 'TelegramWidget.request' in html and 'WebApp' not in html


@pytest.mark.asyncio
async def test_expired_private_link_can_open_readonly_result_without_new_coins():
    from src.bot.presenters.daily_hedgehog import open_pet
    db, service, container, _ = setup()
    result, token = await issue(service)
    bot = AsyncMock()
    message = SimpleNamespace(chat=SimpleNamespace(id=7, type='private'), bot=bot, answer=AsyncMock())
    with patch('src.services.daily_pet_service.time.time', return_value=115):
        await open_pet(message, SimpleNamespace(id=7), container, token)
    bot.assert_awaited_once()
    assert isinstance(bot.call_args.args[0], SendWidget)
    assert '"state":"done"' in bot.call_args.args[0].html
    with patch('src.services.daily_pet_service.time.time', return_value=115):
        assert (await service.widget_action(token, 7, 'v', ''))['state'] == 'done'
    assert db.users.docs[7]['coins'] == 1000 + result['total_coins']


@pytest.mark.asyncio
async def test_failed_photo_delivery_can_retry_without_duplicate_reward_or_new_window():
    from aiogram.exceptions import TelegramNetworkError
    from aiogram.methods import SendPhoto
    from src.bot.presenters.hedgehog_presenter import launch_hedgehog
    db, service, container, _ = setup()
    bot = AsyncMock()
    bot.me.return_value = SimpleNamespace(username='Senseigame_bot')
    message = SimpleNamespace(chat=SimpleNamespace(id=-100, type='supergroup'), bot=bot,
                              answer=AsyncMock(), answer_photo=AsyncMock())
    message.answer_photo.side_effect = TelegramNetworkError(method=SendPhoto(chat_id=-100, photo='x'), message='network')
    user = SimpleNamespace(id=7, username=None, first_name='H', last_name=None, is_bot=False)
    with patch('src.services.daily_pet_service.time.time', return_value=100):
        with pytest.raises(TelegramNetworkError):
            await launch_hedgehog(message, user, container)
    before = db.users.docs[7]['coins']
    message.answer_photo.side_effect = None
    with patch('src.services.daily_pet_service.time.time', return_value=115):
        await launch_hedgehog(message, user, container)
    assert db.users.docs[7]['coins'] == before
    assert db.users.docs[7]['daily_pet']['deadline'] == 115
    assert message.answer_photo.call_args.kwargs['reply_markup'] is None
    caption = message.answer_photo.call_args.kwargs['caption']
    assert 'Время ласки вышло' in caption
    assert 'на переход' not in caption and 'Принятый тап' not in caption


@pytest.mark.asyncio
async def test_historical_ten_second_receipt_is_not_extended():
    db, service, _, _ = setup()
    _, token = await issue(service)
    session = db.users.docs[7]['daily_pet']
    session.pop('duration')
    session['deadline'] = 110
    assert (await service.activate(token, 7, 104))['deadline'] == 110
    with patch('src.services.daily_pet_service.time.time', return_value=110):
        assert (await service.widget_action(token, 7, 'p', 'late'))['taps'] == 0


def test_hedgehog_quills_are_radially_mirrored_and_within_native_budget():
    import re
    import zlib
    from src.widgets.daily_pet import to_daily_pet_html
    html = to_daily_pet_html('Q'*32, Path('.'),
        dict(state='playing', remaining_ms=15000, taps=149, extra_coins=819, base_coins=55))
    positions = re.findall(r'class="spike" style="left:([-\d.]+)px;top:([-\d.]+)px;transform:rotate\(([-\d.]+)deg\)', html)
    assert len(positions) == 21
    for first, second in zip(positions, reversed(positions)):
        left, top, angle = map(float, first)
        right, other_top, other_angle = map(float, second)
        assert left + right == pytest.approx(158, abs=.11)
        assert top == pytest.approx(other_top, abs=.11)
        assert angle == -other_angle
    assert len(zlib.compress(html.encode(), 9)) <= 3900
