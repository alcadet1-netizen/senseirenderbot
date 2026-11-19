"""Admin grant results must not imply an ambiguous transfer failed."""
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest

from src.bot.handlers.admin_commands import cmd_add_coin


@pytest.mark.asyncio
async def test_unconfirmed_grant_warns_before_retry():
    user = NS(id=7, username='target', full_name='Target')
    message = NS(from_user=NS(id=42, username='admin', full_name='Admin'),
                 reply_to_message=NS(from_user=user), text='/addcoin 10', answer=AsyncMock())
    service = NS(admin_add_coins=AsyncMock(side_effect=TimeoutError('unknown outcome')))
    await cmd_add_coin(message, NS(economy_service=service))
    text = message.answer.await_args.args[0]
    assert 'Не удалось подтвердить результат' in text
    assert 'перед повтором' in text
    service.admin_add_coins.assert_awaited_once_with(user_id=7, amount=10, admin_id=42)
