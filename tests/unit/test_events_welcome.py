"""Joining a chat must never restrict users or start a captcha timer."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.types import User

from src.bot.handlers.events import on_user_join, on_new_chat_members


@pytest.mark.asyncio
@pytest.mark.parametrize("via_message", [False, True])
@pytest.mark.parametrize("chat_type", ["group", "supergroup"])
@pytest.mark.parametrize("legacy_setting", ["0", "1", None])
async def test_join_welcomes_without_captcha(via_message, chat_type, legacy_setting):
    container = MagicMock()
    container.moderation_service.unban_user = AsyncMock(return_value={"success": False})
    container.throttle_service.throttle = AsyncMock(return_value=True)
    container.chat_settings_service.get_setting = AsyncMock(return_value=legacy_setting)
    user = User(id=123, is_bot=False, first_name="NewUser")
    event = SimpleNamespace(
        chat=SimpleNamespace(id=-100, type=chat_type, restrict=AsyncMock()),
        new_chat_member=SimpleNamespace(user=user),
        new_chat_members=[user], answer=AsyncMock(), bot=AsyncMock(),
    )
    handler = on_new_chat_members if via_message else on_user_join
    with patch("src.bot.handlers.events._send_welcome_message", new_callable=AsyncMock) as welcome:
        await handler(event, container)
    welcome.assert_awaited_once_with(user, container, event)
    container.moderation_service.unban_user.assert_awaited_once_with(user.id)
    container.chat_settings_service.get_setting.assert_not_awaited()
    event.chat.restrict.assert_not_awaited()
    event.answer.assert_not_awaited()
    event.bot.ban_chat_member.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("via_message", [False, True])
async def test_channel_join_is_ignored(via_message):
    container = MagicMock()
    event = SimpleNamespace(chat=SimpleNamespace(type="channel"))
    handler = on_new_chat_members if via_message else on_user_join
    with patch("src.bot.handlers.events._send_welcome_message", new_callable=AsyncMock) as welcome:
        await handler(event, container)
    welcome.assert_not_awaited()
    assert not container.mock_calls


@pytest.mark.asyncio
@pytest.mark.parametrize('existing,coins', [(False, 3000), (False, 0), (True, 3000)])
async def test_approved_join_request_routes_through_aiogram(existing, coins):
    """Exercise a real Telegram chat_member update, not just a handler mock."""
    from aiogram import Bot, Dispatcher
    from aiogram.types import Update
    from aiogram.filters import ChatMemberUpdatedFilter, IS_NOT_MEMBER, IS_MEMBER
    user = {'id': 77, 'is_bot': False, 'first_name': '<New & student>'}
    update = Update.model_validate({'update_id': 100, 'chat_member': {
        'chat': {'id': -100, 'type': 'supergroup', 'title': 'Dojo'},
        'from': {'id': 999, 'is_bot': False, 'first_name': 'Admin'},
        'date': 1700000000,
        'old_chat_member': {'status': 'left', 'user': user},
        'new_chat_member': {'status': 'member', 'user': user},
        'via_join_request': True,
    }})
    container = SimpleNamespace(
        throttle_service=SimpleNamespace(throttle=AsyncMock(return_value=True)),
        moderation_service=SimpleNamespace(unban_user=AsyncMock(return_value={'success': False})),
        user_service=SimpleNamespace(get_or_create=AsyncMock(return_value={
            'created': not existing, 'user': {'coins': coins}})),
    )
    dp = Dispatcher()
    dp.chat_member.register(on_user_join, ChatMemberUpdatedFilter(IS_NOT_MEMBER >> IS_MEMBER))
    bot = Bot('123456:TEST_TOKEN')
    try:
        with patch.object(bot, 'send_message', new_callable=AsyncMock) as send:
            await dp.feed_update(bot, update, container=container)
        assert send.await_count == (1 if existing else 2)
        greeting = send.await_args_list[0]
        assert greeting.args[0] == -100
        assert 'tg://user?id=77' in greeting.args[1]
        assert '&lt;New &amp; student&gt;' in greeting.args[1]
        container.user_service.get_or_create.assert_awaited_once()
        if not existing:
            text = send.await_args_list[1].args[1]
            assert 'СТАРТОВЫЙ НАБОР' in text and '10 см' in text and 'Уровень 1' in text
            assert ('+3 000 Coin' if coins else '0 Coin') in text
            if not coins:
                assert '3 000' not in text
    finally:
        await bot.session.close()


@pytest.mark.asyncio
async def test_two_join_updates_send_only_one_welcome_and_grant():
    from src.bot.handlers.events import _handle_join
    user = User(id=77, is_bot=False, first_name='New')
    event = SimpleNamespace(chat=SimpleNamespace(id=-100, type='supergroup'), answer=AsyncMock())
    container = SimpleNamespace(
        throttle_service=SimpleNamespace(throttle=AsyncMock(side_effect=[True, False])),
        moderation_service=SimpleNamespace(unban_user=AsyncMock(return_value={'success': False})),
        user_service=SimpleNamespace(get_or_create=AsyncMock(return_value={'created': True, 'user': {'coins': 3000}})),
    )
    await _handle_join(user, container, event)
    await _handle_join(user, container, event)
    assert event.answer.await_count == 2  # welcome + starter, no duplicate pair
    container.user_service.get_or_create.assert_awaited_once()
    container.moderation_service.unban_user.assert_awaited_once()
    assert container.throttle_service.throttle.await_args.kwargs == {
        'key': '-100:77', 'limit_seconds': 15, 'scope': 'join_welcome'}


@pytest.mark.asyncio
async def test_join_greets_when_registration_or_unban_fails_without_claiming_reward():
    from src.bot.handlers.events import _handle_join
    user = User(id=77, is_bot=False, first_name='New')
    event = SimpleNamespace(chat=SimpleNamespace(id=-100, type='group'), answer=AsyncMock())
    container = SimpleNamespace(
        throttle_service=SimpleNamespace(throttle=AsyncMock(return_value=True)),
        moderation_service=SimpleNamespace(unban_user=AsyncMock(side_effect=OSError('unavailable'))),
        user_service=SimpleNamespace(get_or_create=AsyncMock(side_effect=OSError('unavailable'))),
    )
    await _handle_join(user, container, event)
    event.answer.assert_awaited_once()
    assert 'tg://user?id=77' in event.answer.await_args.args[0]
    assert 'СТАРТОВЫЙ НАБОР' not in event.answer.await_args.args[0]


@pytest.mark.asyncio
async def test_service_join_passes_admin_check_but_bypasses_blocking_message_middleware(caplog):
    from aiogram import BaseMiddleware, Bot, Dispatcher
    from aiogram.types import Update
    from src.bot.middlewares.group_admin import GroupAdminMiddleware, group_admin_access
    from src.bot.middlewares.join_events import JoinDiagnosticsMiddleware, JoinServiceMessageMiddleware

    class BlockAll(BaseMiddleware):
        async def __call__(self, handler, event, data):
            return None

    user = {'id': 77, 'is_bot': False, 'first_name': 'New'}
    update = Update.model_validate({'update_id': 55, 'message': {
        'message_id': 1, 'date': 1700000000,
        'chat': {'id': -100222, 'type': 'supergroup', 'title': 'Dojo'},
        'from': {'id': 78, 'is_bot': False, 'first_name': 'Inviter'},
        'new_chat_members': [user],
    }})
    container = SimpleNamespace(
        throttle_service=SimpleNamespace(throttle=AsyncMock(return_value=True)),
        moderation_service=SimpleNamespace(unban_user=AsyncMock(return_value={'success': False})),
        user_service=SimpleNamespace(get_or_create=AsyncMock(return_value={'created': True, 'user': {'coins': 3000}})),
    )
    dp = Dispatcher()
    dp.update.outer_middleware(JoinDiagnosticsMiddleware())
    dp.update.outer_middleware(GroupAdminMiddleware())
    dp.update.outer_middleware(JoinServiceMessageMiddleware(container))
    dp.message.outer_middleware(BlockAll())
    bot = Bot('123456:TEST_TOKEN')
    group_admin_access.invalidate(bot.id, -100222)
    try:
        with patch.object(bot, 'get_chat_member', new_callable=AsyncMock, return_value=SimpleNamespace(status='administrator')), \
             patch.object(Bot, '__call__', new_callable=AsyncMock) as send:
            await dp.feed_update(bot, update)
        assert send.await_count == 2
        assert 'tg://user?id=77' in send.await_args_list[0].args[0].text
        container.user_service.get_or_create.assert_awaited_once()
    finally:
        group_admin_access.invalidate(bot.id, -100222)
        await bot.session.close()


@pytest.mark.asyncio
async def test_diagnostics_record_membership_before_dispatch(caplog):
    import logging
    from aiogram.types import Update
    from src.bot.middlewares.join_events import JoinDiagnosticsMiddleware
    user = {'id': 77, 'is_bot': False, 'first_name': 'New'}
    update = Update.model_validate({'update_id': 10, 'chat_member': {
        'chat': {'id': -100, 'type': 'supergroup', 'title': 'Dojo'},
        'from': {'id': 78, 'is_bot': False, 'first_name': 'Admin'}, 'date': 1700000000,
        'old_chat_member': {'status': 'left', 'user': user},
        'new_chat_member': {'status': 'member', 'user': user}, 'via_join_request': True}})
    with caplog.at_level(logging.INFO):
        await JoinDiagnosticsMiddleware()(AsyncMock(), update, {})
    assert 'Join ingress update=10 chat=-100 user=77 old=left new=member via_request=True' in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize('username,template', [
    (None, 'Добро пожаловать в додзё, @{username}! 🥋'),
    ('test_user', '🐉 Дракон приветствует тебя, @{username}!'),
    (None, '🦑 {username}, игра в кальмара отменяется. У нас игра в «напиши больше всех»!'),
])
async def test_random_existing_welcome_templates_use_safe_mention(username, template):
    from src.bot.handlers.events import _send_welcome_message
    from src.texts.phrases import WELCOME_PHRASES
    assert template in WELCOME_PHRASES
    user = User(id=77, is_bot=False, first_name='<Николай & друг>', username=username)
    event = SimpleNamespace(chat=SimpleNamespace(id=-100, type='supergroup'), answer=AsyncMock())
    container = SimpleNamespace(user_service=SimpleNamespace(get_or_create=AsyncMock(
        return_value={'created': True, 'user': {'coins': 3000}})))
    with patch('src.texts.phrases.random.choice', return_value=template) as choice:
        await _send_welcome_message(user, container, event)
    choice.assert_called_once_with(WELCOME_PHRASES)
    greeting = event.answer.await_args_list[0].args[0]
    mention = '<a href="tg://user?id=77">&lt;Николай &amp; друг&gt;</a>'
    assert greeting == template.replace('@{username}', '{username}').format(username=mention)
    assert '@<a' not in greeting
    assert event.answer.await_args_list[0].kwargs['parse_mode'] == 'HTML'
    assert event.answer.await_count == 2
    assert 'СТАРТОВЫЙ НАБОР' in event.answer.await_args_list[1].args[0]
