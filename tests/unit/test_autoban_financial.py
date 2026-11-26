from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest

from src.services.moderation_service import ModerationService


@pytest.mark.asyncio
async def test_exit_updates_money_and_both_ticket_formats_in_transaction(monkeypatch):
    users = NS(find_one=AsyncMock(return_value={'id': 5, 'coins': 42, 'is_banned': False,
                                                 'has_katana': True, 'katana_length': 3}),
               update_one=AsyncMock(return_value=NS(matched_count=1)))
    bank = NS(find_one=AsyncMock(return_value={'_id': 'single', 'coins': 100}),
              update_one=AsyncMock(return_value=NS(matched_count=1)))
    tickets = NS(update_many=AsyncMock(return_value=NS(modified_count=2)))
    journal = NS(insert_one=AsyncMock())
    db = NS(users=users, bank=bank, tickets=tickets, transactions=journal, muted_users=NS())
    mongo = NS(database=db)
    async def transaction(_mongo, callback):
        return await callback('test-session')
    monkeypatch.setattr('src.services.referral_economy.transaction', transaction)
    result = await ModerationService(mongo).handle_user_left(5)
    assert result['confiscated'] == 42 and result['tickets_confiscated'] == 2
    change = users.update_one.await_args.args[1]['$set']
    assert change['coins'] == 0 and change['is_banned'] is True
    assert 'katana_length' not in change and 'has_katana' not in change
    assert bank.update_one.await_args.args[1] == {'$inc': {'coins': 42}}
    assert tickets.update_many.await_args.args[1]['$set']['is_burned'] is True
    assert tickets.update_many.await_args.args[1]['$set']['burned'] is True
    for method in (users.find_one, users.update_one, bank.update_one, tickets.update_many, journal.insert_one):
        assert method.await_args.kwargs['session'] == 'test-session'


@pytest.mark.asyncio
async def test_duplicate_exit_does_not_move_any_money(monkeypatch):
    users = NS(find_one=AsyncMock(return_value={'id': 5, 'is_banned': True}), update_one=AsyncMock())
    bank = NS(update_one=AsyncMock())
    tickets = NS(update_many=AsyncMock())
    db = NS(users=users, bank=bank, tickets=tickets, transactions=NS(), muted_users=NS())
    async def transaction(_mongo, callback):
        return await callback('session')
    monkeypatch.setattr('src.services.referral_economy.transaction', transaction)
    result = await ModerationService(NS(database=db)).handle_user_left(5)
    assert not result['success']
    users.update_one.assert_not_awaited()
    bank.update_one.assert_not_awaited()
    tickets.update_many.assert_not_awaited()
