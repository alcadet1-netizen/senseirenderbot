import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.types import ChatMemberUpdated, User
from src.bot.handlers.events import on_user_leave

@pytest.mark.asyncio
async def test_autoban_includes_phrase():
    # Mock container
    container = MagicMock()
    container.moderation_service.handle_user_left = AsyncMock(return_value={
        "success": True,
        "confiscated": 100.0,
        "user_id": 123
    })
    # Mock chat_settings_service
    container.chat_settings_service = MagicMock()
    container.chat_settings_service.get_setting = AsyncMock(return_value="1")  # Not "0", so notifications are enabled

    # Mock event
    event = AsyncMock(spec=ChatMemberUpdated)
    event.old_chat_member = MagicMock()
    event.old_chat_member.user = User(id=123, is_bot=False, first_name="TestUser", username="testuser")
    event.chat = MagicMock()
    event.chat.id = -100123
    event.chat.type = "supergroup"
    event.from_user = event.old_chat_member.user
    event.new_chat_member = MagicMock(status='left')
    event.answer = AsyncMock()

    # Mock phrases
    with patch("src.bot.handlers.events.get_random_ban_phrase", return_value="Ban Phrase"), \
         patch("src.bot.handlers.events.get_random_phrase", return_value="Sensei Phrase"):
        await on_user_leave(event, container)

    # Verify
    container.moderation_service.handle_user_left.assert_called_with(123)
    event.answer.assert_called_once()

    args, kwargs = event.answer.call_args
    text = args[0]
    assert "АВТОБАН" in text
    assert "Ban Phrase" in text
    assert "100.00 монет" in text

@pytest.mark.asyncio
async def test_unsubscribe_from_task_channel_does_not_autoban():
    """Отписка от канала задания — не нарушение.

    Канал не является чатом: игрок выполнил «подпишись» и вправе отписаться.
    Раньше тип чата не проверялся, и отписка банила игрока вместе с
    конфискацией баланса.
    """
    container = MagicMock()
    container.moderation_service.handle_user_left = AsyncMock(return_value={"success": True})
    container.chat_settings_service = MagicMock()
    container.chat_settings_service.get_setting = AsyncMock(return_value="1")

    event = AsyncMock(spec=ChatMemberUpdated)
    event.old_chat_member = MagicMock()
    event.old_chat_member.user = User(id=555, is_bot=False, first_name="Channel")
    event.chat = MagicMock()
    event.chat.id = -1001234567890
    event.chat.type = "channel"
    event.answer = AsyncMock()

    await on_user_leave(event, container)

    container.moderation_service.handle_user_left.assert_not_awaited()
    event.answer.assert_not_awaited()


@pytest.mark.asyncio
async def test_leaving_plain_group_autobans():
    """Обычная группа тоже является чатом."""
    container = MagicMock()
    container.moderation_service.handle_user_left = AsyncMock(return_value={"success": True})
    container.chat_settings_service = MagicMock()
    container.chat_settings_service.get_setting = AsyncMock(return_value="1")

    event = AsyncMock(spec=ChatMemberUpdated)
    event.old_chat_member = MagicMock()
    event.old_chat_member.user = User(id=556, is_bot=False, first_name="Group")
    event.chat = MagicMock()
    event.chat.id = -100999
    event.chat.type = "group"
    event.from_user = event.old_chat_member.user
    event.new_chat_member = MagicMock(status='left')
    event.answer = AsyncMock()

    await on_user_leave(event, container)

    container.moderation_service.handle_user_left.assert_awaited_once_with(556)


@pytest.mark.asyncio
@pytest.mark.parametrize('status,actor,setting', [('kicked', 556, '1'), ('left', 999, '1'), ('left', 556, '0')])
async def test_no_autoban_for_kicks_or_disabled(status, actor, setting):
    container = MagicMock()
    container.moderation_service.handle_user_left = AsyncMock()
    container.chat_settings_service.get_setting = AsyncMock(return_value=setting)
    user = User(id=556, is_bot=False, first_name='Group')
    event = MagicMock()
    event.old_chat_member.user = user
    event.new_chat_member.status = status
    event.from_user.id = actor
    event.chat.id, event.chat.type = -100, 'group'
    await on_user_leave(event, container)
    container.moderation_service.handle_user_left.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('chat_type,expected', [('supergroup', True), ('group', True), ('channel', False)])
async def test_leave_real_aiogram_update(chat_type, expected):
    from aiogram import Bot, Dispatcher
    from aiogram.filters import ChatMemberUpdatedFilter, IS_MEMBER, IS_NOT_MEMBER
    from aiogram.types import Update
    from types import SimpleNamespace as NS

    user = {'id': 77, 'is_bot': False, 'first_name': 'Student'}
    update = Update.model_validate({'update_id': 3, 'chat_member': {
        'chat': {'id': -100, 'type': chat_type, 'title': 'Test'}, 'from': user,
        'date': 1700000000, 'old_chat_member': {'status': 'member', 'user': user},
        'new_chat_member': {'status': 'left', 'user': user},
    }})
    moderation = NS(handle_user_left=AsyncMock(return_value={'success': False}))
    # Keep autoban enabled even for channels: the channel guard itself, not
    # a disabled setting, must prevent both the ban and any financial action.
    settings = NS(get_setting=AsyncMock(return_value='1'))
    container = NS(moderation_service=moderation, chat_settings_service=settings)
    dp = Dispatcher()
    dp.chat_member.register(on_user_leave, ChatMemberUpdatedFilter(IS_MEMBER >> IS_NOT_MEMBER))
    bot = Bot('123456:TEST_TOKEN')
    try:
        await dp.feed_update(bot, update, container=container)
        assert moderation.handle_user_left.await_count == int(expected)
        if chat_type == 'channel':
            settings.get_setting.assert_not_awaited()
    finally:
        await bot.session.close()
