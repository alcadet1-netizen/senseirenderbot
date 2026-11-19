from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

import pytest

from src.bot.handlers.callbacks import cb_exchange_coins_to_ticket, cb_exchange_ticket_to_coins


@pytest.mark.asyncio
@pytest.mark.parametrize('direction', ['buy', 'sell'])
async def test_exchange_callback_reuses_id_and_warns_if_display_failed(direction):
    query = NS(id='callback-1', from_user=NS(id=7, username='user', full_name='User'),
               message=NS(edit_text=AsyncMock(side_effect=RuntimeError('unavailable'))), answer=AsyncMock())
    result = {'success': True, 'coins_spent': 3000, 'ticket_code': 'T1', 'coins_received': 2600}
    service = NS(coins_to_ticket=AsyncMock(return_value=result), ticket_to_coins=AsyncMock(return_value=result))
    handler = cb_exchange_coins_to_ticket if direction == 'buy' else cb_exchange_ticket_to_coins
    with patch('src.bot.handlers.callbacks.check_owner', new=AsyncMock(return_value=True)):
        await handler(query, NS(user_id=7), NS(exchange_service=service))
    method = service.coins_to_ticket if direction == 'buy' else service.ticket_to_coins
    method.assert_awaited_once_with(7, request_id='callback-1')
    assert 'Не повторяйте обмен' in query.answer.await_args.args[0]
