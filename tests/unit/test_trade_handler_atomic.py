from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest
from aiogram.enums import ChatType
from aiogram.filters import CommandObject

from src.bot.handlers.trade import cmd_trade


@pytest.mark.asyncio
async def test_trade_command_passes_stable_message_id_and_unconfirmed_error():
    user = NS(id=7, username=None, full_name='Alice')
    message = NS(from_user=user, chat=NS(id=7, type=ChatType.PRIVATE), message_id=42,
                 delete=AsyncMock(), answer=AsyncMock())
    service = NS(play_game=AsyncMock(return_value={'success': False,
                 'error': 'Результат не подтверждён. Проверьте баланс и журнал перед повтором.'}))
    await cmd_trade(message, CommandObject(prefix='/', command='trade', args='100'), NS(trade_service=service))
    service.play_game.assert_awaited_once_with(7, 100, request_id='7:42')
    assert 'не подтверждён' in message.answer.call_args.args[0]
