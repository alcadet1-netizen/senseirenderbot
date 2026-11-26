"""Financial paths against an isolated MongoDB replica set (never production)."""
import asyncio
import os
import uuid
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

from src.services.moderation_service import ModerationService
from src.services.lottery_service import LotteryService


@pytest.fixture
async def replica_db():
    uri = os.environ.get('CAMPAIGN_TEST_MONGO_URI')
    if not uri:
        pytest.skip('MongoDB replica set required')
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
    db = client['sensei_autoban_lottery_test_' + uuid.uuid4().hex]
    try:
        # Avoid first-creation DDL conflicts inside concurrent transactions.
        for name in ('users', 'bank', 'tickets', 'transactions'):
            await db.create_collection(name)
        yield db
    finally:
        await client.drop_database(db.name)
        client.close()


@pytest.mark.asyncio
async def test_exit_confiscates_once_atomically_and_preserves_katana(replica_db):
    db = replica_db
    await db.users.insert_one({'id': 11, 'coins': 25, 'is_banned': False,
                               'has_katana': True, 'katana_length': 12.5})
    await db.bank.insert_one({'_id': 'single', 'coins': 100})
    await db.tickets.insert_many([
        {'_id': 1, 'user_id': 11, 'code': 'A', 'burned': False},
        {'_id': 2, 'user_id': 11, 'code': 'B', 'is_burned': False},
        {'_id': 3, 'user_id': 11, 'code': 'C', 'burned': True},
        {'_id': 4, 'user_id': 12, 'code': 'D', 'burned': False},
    ])
    service = ModerationService(NS(database=db))
    results = await asyncio.gather(service.handle_user_left(11), service.handle_user_left(11))
    assert sum(bool(r['success']) for r in results) == 1
    user = await db.users.find_one({'id': 11})
    assert user['is_banned'] and user['coins'] == 0
    assert user['has_katana'] and user['katana_length'] == 12.5
    assert (await db.bank.find_one({'_id': 'single'}))['coins'] == 125
    assert await db.transactions.count_documents({'user_id': 11, 'tx_type': 'ban_confiscation'}) == 1
    assert await db.tickets.count_documents({'user_id': 11, 'burn_reason': 'autoban_exit'}) == 2
    assert not (await db.tickets.find_one({'_id': 4}))['burned']


@pytest.mark.asyncio
async def test_exit_journal_failure_rolls_back_everything(replica_db):
    db = replica_db
    await db.users.insert_one({'id': 11, 'coins': 25, 'is_banned': False, 'katana_length': 12.5})
    await db.bank.insert_one({'_id': 'single', 'coins': 100})
    await db.tickets.insert_one({'_id': 1, 'user_id': 11, 'code': 'A', 'burned': False})
    service = ModerationService(NS(database=db))
    service.transactions = NS(insert_one=AsyncMock(side_effect=RuntimeError('journal unavailable')))
    with pytest.raises(RuntimeError, match='journal unavailable'):
        await service.handle_user_left(11)
    assert (await db.users.find_one({'id': 11}))['coins'] == 25
    assert not (await db.users.find_one({'id': 11}))['is_banned']
    assert (await db.bank.find_one({'_id': 'single'}))['coins'] == 100
    assert not (await db.tickets.find_one({'_id': 1}))['burned']


@pytest.mark.asyncio
async def test_lottery_respects_chat_and_burns_selected_tickets(replica_db):
    db = replica_db
    await db.tickets.insert_many([
        {'_id': 1, 'user_id': 11, 'code': 'A', 'burned': False},
        {'_id': 2, 'user_id': 12, 'code': 'B', 'is_burned': False},
        {'_id': 3, 'user_id': 13, 'code': 'C'},
    ])
    async def get_member(chat, uid):
        assert chat == -100
        user = NS(id=uid, is_bot=False, first_name='Test', last_name=None, username=None)
        return NS(status='left' if uid == 12 else 'member', user=user)
    svc = LotteryService(NS(database=db))
    winners = await svc.run_lottery(10, chat_id=-100, bot=NS(get_chat_member=get_member))
    assert {w['ticket_code'] for w in winners} == {'A', 'C'}
    assert (await db.tickets.find_one({'_id': 1}))['burned']
    assert not (await db.tickets.find_one({'_id': 2})).get('burned', False)
    assert (await db.tickets.find_one({'_id': 3}))['is_burned']
