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
