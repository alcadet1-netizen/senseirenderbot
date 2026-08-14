import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.types import ChatMemberUpdated, User

from src.bot.handlers.events import on_user_join


@pytest.mark.asyncio
async def test_join_initiates_captcha():
    container = MagicMock()
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