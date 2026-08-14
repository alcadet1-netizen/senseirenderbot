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