"""Cross-service queries share the same definition of an active ticket."""
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest

from src.domain.tickets import active_ticket_filter
from src.services.lottery_service import LotteryService
from src.services.user_service import UserService


@pytest.mark.asyncio
async def test_profile_asks_for_same_tickets_as_lottery():
    tickets = NS(count_documents=AsyncMock(return_value=3))
    db = NS(users=NS(find_one=AsyncMock(return_value={'id': 7, 'xp': 0})),
            tickets=tickets, user_achievements=NS(count_documents=AsyncMock(return_value=0),
                                                   find_one=AsyncMock(return_value=None)),
            transactions=NS(), daily_claims=NS(), bank=NS())
    assert (await UserService(NS(database=db)).get_profile(7))['tickets'] == 3
    tickets.count_documents.assert_awaited_once_with(active_ticket_filter(user_id=7))


@pytest.mark.asyncio
async def test_admin_burn_handles_legacy_flags_and_dict_user():
    tickets = NS(update_many=AsyncMock(return_value=NS(modified_count=2)))
    users = NS(find_one=AsyncMock(return_value={'id': 7, 'first_name': 'Sensei'}))
    result = await LotteryService(NS(database=NS(tickets=tickets, users=users))).admin_burn_user_tickets(7, 9)
    assert result == {'success': True, 'user_id': 7, 'username': 'Sensei', 'burned_count': 2}
    query, update = tickets.update_many.await_args.args
    assert query == {'user_id': 7, 'burned': {'$ne': True}, 'is_burned': {'$ne': True}}
    assert update['$set']['burned'] and update['$set']['is_burned']


def test_active_filter_requires_a_code_and_excludes_either_burn_flag():
    assert active_ticket_filter(user_id=7) == {
        'burned': {'$ne': True}, 'is_burned': {'$ne': True},
        'code': {'$type': 'string'}, 'user_id': 7,
    }
