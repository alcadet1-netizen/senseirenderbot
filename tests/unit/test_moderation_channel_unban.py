"""Historical bans share a reason; bulk channel refunds must not touch them."""
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest

from src.bot.handlers.admin_commands import cmd_unban_channels
from src.services.moderation_service import ModerationService


@pytest.mark.asyncio
async def test_ambiguous_restore_disabled_without_accessing_database():
    service = ModerationService.__new__(ModerationService)
    result = await service.restore_channel_unsubscribe_bans()
    assert result['success'] is False
    assert 'ambiguous' in result['error']


@pytest.mark.asyncio
async def test_restore_command_explains_and_does_not_refund():
    message = NS(answer=AsyncMock())
    service = NS(restore_channel_unsubscribe_bans=AsyncMock())
    await cmd_unban_channels(message, NS(moderation_service=service))
    service.restore_channel_unsubscribe_bans.assert_not_awaited()
    assert 'нельзя надёжно различить' in message.answer.await_args.args[0]
