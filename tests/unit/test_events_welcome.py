import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.types import ChatMemberUpdated, User

from src.bot.handlers.events import on_user_join


@pytest.mark.asyncio
async def test_join_initiates_captcha():
    container = MagicMock()
    # Mock moderation_service with AsyncMock for unban_user
    container.moderation_service = AsyncMock()
    container.moderation_service.unban_user = AsyncMock(return_value={"success": False})
    # Mock chat_settings_service with AsyncMock for get_setting
    container.chat_settings_service = AsyncMock()
    container.chat_settings_service.get_setting = AsyncMock(return_value="1")
    # Mock captcha_service
    container.captcha_service = MagicMock()
    container.captcha_service.set_lock = AsyncMock(return_value=True)  # Returns True so lock is acquired and we proceed

    user = User(id=123, is_bot=False, first_name="NewUser", username="newuser")

    event = AsyncMock(spec=ChatMemberUpdated)
    event.new_chat_member = MagicMock()
    event.new_chat_member.user = user

    event.chat = MagicMock()
    event.chat.id = -100
    event.chat.type = "supergroup"
    event.chat.restrict = AsyncMock()

    event.bot = AsyncMock()

    msg = MagicMock()
    msg.message_id = 777
    event.answer = AsyncMock(return_value=msg)

    with patch("src.bot.handlers.events._wait_for_captcha", new=AsyncMock()):
        await on_user_join(event, container)

    container.captcha_service.set_lock.assert_awaited()
    event.chat.restrict.assert_awaited()
    event.answer.assert_awaited()
    container.moderation_service.unban_user.assert_awaited()
    container.chat_settings_service.get_setting.assert_awaited()