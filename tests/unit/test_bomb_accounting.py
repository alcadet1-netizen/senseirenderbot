from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest
from src.bot.handlers import bomb


def game(winners):
    return {'total': 1000, 'per_user': 500, 'winners': winners,
            'max_winners': 2, 'total_distributed': sum(w['bonus'] for w in winners),
            'message_id': 123}


@pytest.mark.asyncio
async def test_bomb_reports_only_confirmed_payouts_without_refunding_unreserved_money():
    bomb._active_bombs[70] = game([
        {'user_id': 7, 'name': 'one', 'bonus': 500, 'position': 1},
        {'user_id': 8, 'name': 'two', 'bonus': 500, 'position': 2},
    ])
    economy = NS(process_game_win=AsyncMock(side_effect=[{'success': True}, {'success': False}]),
                 _deposit_to_bank=AsyncMock())
    bot = NS(edit_message_text=AsyncMock(), send_message=AsyncMock())
    await bomb._finish_bomb(bot, 70, NS(economy_service=economy))
    economy._deposit_to_bank.assert_not_awaited()
    assert economy.process_game_win.await_count == 2
    text = bot.edit_message_text.await_args.args[0]
    assert 'Роздано: <b>500</b>' in text
    assert 'Не подтверждено выплат: 1' in text
    assert 'two' not in text


@pytest.mark.asyncio
async def test_empty_bomb_does_not_deposit_or_claim_coins_burned():
    bomb._active_bombs[71] = game([])
    economy = NS(process_game_win=AsyncMock(), _deposit_to_bank=AsyncMock())
    bot = NS(edit_message_text=AsyncMock(), send_message=AsyncMock())
    await bomb._finish_bomb(bot, 71, NS(economy_service=economy), is_timeout=True)
    economy._deposit_to_bank.assert_not_awaited()
    assert 'остались в банке' in bot.edit_message_text.await_args.args[0]
