from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
import pytest
from src.bot.handlers.admin_commands import cmd_bonus_sensei


@pytest.mark.asyncio
async def test_lottery_refuses_private_chat():
    message = NS(from_user=NS(username='admin', full_name='Admin'), chat=NS(type='private'),
                 answer=AsyncMock())
    lottery = NS(run_lottery=AsyncMock())
    await cmd_bonus_sensei(message, NS(lottery_service=lottery))
    lottery.run_lottery.assert_not_awaited()
    assert 'чате' in message.answer.await_args.args[0]


@pytest.mark.asyncio
async def test_lottery_receives_origin_chat_and_bot():
    bot = NS(send_message=AsyncMock())
    message = NS(from_user=NS(username='admin', full_name='Admin'),
                 chat=NS(id=-100, type='supergroup'), text='/bonussensei 2', bot=bot,
                 answer=AsyncMock())
    lottery = NS(run_lottery=AsyncMock(return_value=[{'username': None, 'full_name': '<User>', 'ticket_code': '<A>'}]))
    await cmd_bonus_sensei(message, NS(lottery_service=lottery))
    lottery.run_lottery.assert_awaited_once_with(2, chat_id=-100, bot=bot)
    assert '&lt;User&gt;' in bot.send_message.await_args.args[1]
    assert '&lt;A&gt;' in bot.send_message.await_args.args[1]


@pytest.mark.asyncio
async def test_lottery_failure_warns_operator_to_check_ticket_state():
    message = NS(from_user=NS(username='admin', full_name='Admin'),
                 chat=NS(id=-100, type='group'), text='/bonussensei', bot=NS(), answer=AsyncMock())
    lottery = NS(run_lottery=AsyncMock(side_effect=OSError('down')))
    await cmd_bonus_sensei(message, NS(lottery_service=lottery))
    assert 'состояние билетов' in message.answer.await_args.args[0]
