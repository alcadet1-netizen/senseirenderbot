"""Daily hedgehog settlement on an isolated transactional MongoDB."""
import asyncio
import os
import uuid
from types import SimpleNamespace as NS

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

from src.services.daily_service import DailyService
from src.services.hedgehog_service import utc_day


@pytest.mark.asyncio
async def test_daily_reward_replay_shared_bank_and_failed_journal():
    uri = os.environ.get('CAMPAIGN_TEST_MONGO_URI')
    if not uri:
        pytest.skip('MongoDB replica set required')
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
    name = 'sensei_daily_reward_test_' + uuid.uuid4().hex
    db = client[name]
    try:
        await db.bank.insert_many([{'_id': 'single', 'coins': 20, 'total_emitted': 1000, 'burned': 0},
                                   {'_id': 'main', 'balance': 35}])
        await db.users.insert_many([{'id': i, 'coins': 100, 'xp': 0, 'daily_streak': 0,
                                     'is_banned': False} for i in (7, 8, 9)])
        workers = [DailyService(NS(database=db)) for _ in range(6)]
        result = await asyncio.gather(*(svc.settle_hedgehog(7, True, utc_day(), ordinary=True) for svc in workers))
        assert all(r == result[0] for r in result)
        assert result[0]['total_coins'] == 55
        assert (await db.users.find_one({'id': 7}))['coins'] == 155
        assert (await db.bank.find_one({'_id': 'single'}))['coins'] == 0
        assert (await db.bank.find_one({'_id': 'main'}))['balance'] == 0
        assert await db.daily_claims.count_documents({'user_id': 7}) == 1
        assert await db.transactions.count_documents({'user_id': 7, 'tx_type': 'daily_bonus'}) == 1

        # Refill only the isolated test bank and race two users for 55 coins.
        await db.bank.update_one({'_id': 'single'}, {'$set': {'coins': 55}})
        two = await asyncio.gather(*(DailyService(NS(database=db)).settle_hedgehog(uid, True, utc_day(), ordinary=True)
                                     for uid in (8, 9)))
        assert sum(r['total_coins'] for r in two) == 55
        assert (await db.users.find_one({'id': 8}))['coins'] + (await db.users.find_one({'id': 9}))['coins'] == 255
        assert (await db.bank.find_one({'_id': 'single'}))['coins'] == 0
        assert (await db.bank.find_one({'_id': 'single'}))['total_emitted'] == 1000

        # A journal failure aborts bank debit and user receipt together.
        await db.users.insert_one({'id': 10, 'coins': 100, 'xp': 0, 'daily_streak': 0, 'is_banned': False})
        await db.bank.update_one({'_id': 'single'}, {'$set': {'coins': 55}})
        broken = DailyService(NS(database=db))
        async def fail(*args, **kwargs): raise RuntimeError('journal unavailable')
        broken.transactions = NS(update_one=fail)
        with pytest.raises(RuntimeError, match='journal unavailable'):
            await broken.settle_hedgehog(10, True, utc_day(), ordinary=True)
        assert (await db.users.find_one({'id': 10}))['coins'] == 100
        assert 'hedgehog_day' not in await db.users.find_one({'id': 10})
        assert (await db.bank.find_one({'_id': 'single'}))['coins'] == 55
        assert await db.daily_claims.count_documents({'user_id': 10}) == 0
    finally:
        await client.drop_database(name)
        client.close()
