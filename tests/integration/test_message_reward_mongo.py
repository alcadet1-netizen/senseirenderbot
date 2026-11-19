"""Message rewards and tickets on an isolated Mongo replica set."""
import asyncio
import os
import uuid
from types import SimpleNamespace as NS

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

from src.services.economy_service import EconomyService


@pytest.mark.asyncio
async def test_message_reward_concurrency_ticket_and_journal_rollback():
    uri = os.environ.get('CAMPAIGN_TEST_MONGO_URI')
    if not uri:
        pytest.skip('MongoDB replica set required')
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
    name = 'sensei_messages_test_' + uuid.uuid4().hex
    db = client[name]
    try:
        await db.bank.insert_many([{'_id': 'single', 'coins': 4, 'total_emitted': 1000, 'burned': 0},
                                   {'_id': 'main', 'balance': 6}])
        await db.users.insert_one({'id': 7, 'coins': 100, 'xp': 100, 'messages_count': 299, 'is_banned': False})
        services = [EconomyService(NS(database=db)) for _ in range(2)]
        results = await asyncio.gather(*(svc.process_message_reward(7) for svc in services))
        assert all(r['success'] for r in results)
        assert sum(r['coins_earned'] for r in results) == 10
        user = await db.users.find_one({'id': 7})
        assert user['messages_count'] == 301 and user['coins'] == 110
        assert (await db.bank.find_one({'_id': 'single'}))['coins'] == 0
        assert (await db.bank.find_one({'_id': 'main'}))['balance'] == 0
        assert await db.tickets.count_documents({'user_id': 7}) == 1
        assert await db.transactions.count_documents({'tx_type': 'message_reward'}) == 2
        rows = await db.transactions.find({'tx_type': 'message_reward'}).to_list(length=None)
        assert sum(r['coins_change'] for r in rows) == 10

        # Inject an unavailable journal while reads and updates use real Mongo.
        await db.bank.update_one({'_id': 'single'}, {'$set': {'coins': 20}})
        before = await db.users.find_one({'id': 7})
        async def fail(*args, **kwargs):
            raise RuntimeError('journal unavailable')
        broken = EconomyService(NS(database=db))
        broken.transactions = NS(insert_one=fail)
        with pytest.raises(RuntimeError, match='journal unavailable'):
            await broken.process_message_reward(7)
        assert await db.users.find_one({'id': 7}) == before
        assert (await db.bank.find_one({'_id': 'single'}))['coins'] == 20
        assert await db.transactions.count_documents({'tx_type': 'message_reward'}) == 2
    finally:
        await client.drop_database(name)
        client.close()
