from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest

from src.bot.handlers.duel_commands import cmd_duel


@pytest.mark.asyncio
async def test_duel_command_passes_stable_telegram_message_identity():
    user = NS(id=7, username='a', full_name='A', is_bot=False)
    opponent = NS(id=8, username='b', full_name='B', is_bot=False)
    message = NS(from_user=user, reply_to_message=NS(from_user=opponent),
                 chat=NS(id=-100), message_id=42, text='/duel 300', answer=AsyncMock())
    container = NS(user_service=NS(get_profile=AsyncMock(return_value={'id': 7})),
                   duel_service=NS(create_duel=AsyncMock(return_value='already handled')))
    bot = AsyncMock()
    await cmd_duel(message, container, bot)
    container.duel_service.create_duel.assert_awaited_once_with(
        challenger_id=7, opponent_id=8, bet=300, chat_id=-100, bot=bot, request_id='-100:42')
