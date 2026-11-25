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
async def test_leaving_plain_group_does_not_autoban():
    """Обычная группа тоже не чат общения — баним только supergroup."""
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
    event.answer = AsyncMock()

    await on_user_leave(event, container)

    container.moderation_service.handle_user_left.assert_not_awaited()
    event.answer.assert_not_awaited()
