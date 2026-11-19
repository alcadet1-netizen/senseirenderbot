"""Concurrent daily pet taps on an isolated MongoDB replica set."""
import asyncio
import os
import time
import uuid
from types import SimpleNamespace as NS

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

from src.services.daily_pet_service import DailyPetService


@pytest.mark.asyncio
async def test_tap_replays_concurrency_and_journal_rollback():
    uri = os.environ.get('CAMPAIGN_TEST_MONGO_URI')
    if not uri:
        pytest.skip('MongoDB replica set required')
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
    name = 'sensei_daily_tap_test_' + uuid.uuid4().hex
    db = client[name]
    try:
        token = 'A' * 32
        day = '2026-11-06'
        now = time.time()
        pet = {'token': token, 'day': day, 'state': 'active', 'deadline': now + 10,
               'duration': 15, 'queries': [], 'taps': 0, 'extra_coins': 0, 'base_coins': 55}
        await db.users.insert_one({'id': 7, 'coins': 100, 'xp': 70, 'is_banned': False,
                                   'hedgehog_day': day, 'daily_pet': pet})
        await db.bank.insert_many([{'_id': 'single', 'coins': 20, 'total_emitted': 1000, 'burned': 0},
                                   {'_id': 'main', 'balance': 100}])
        workers = [DailyPetService(NS(database=db), None, None) for _ in range(8)]
        # A replay of exactly the same callback can credit only once.
        repeats = await asyncio.gather(*(w.tap(token, 7, 'same-query', received_at=now, rate_limit=False) for w in workers))
        assert all(r['taps'] == 1 and r['extra_coins'] == 5 for r in repeats)
        # Different callbacks racing across workers remain additive and funded.
        await asyncio.gather(*(w.tap(token, 7, f'query-{i}', received_at=now, rate_limit=False)
                               for i, w in enumerate(workers)))
        user = await db.users.find_one({'id': 7})
        single = await db.bank.find_one({'_id': 'single'})
        legacy = await db.bank.find_one({'_id': 'main'})
        assert user['daily_pet']['taps'] == 9
        assert user['daily_pet']['extra_coins'] == 49
        assert user['coins'] == 149 and user['xp'] == 70
        assert single['coins'] + legacy['balance'] == 71
        assert single['total_emitted'] == 1000
        assert await db.transactions.count_documents({'tx_type': 'daily_pet_bonus'}) == 9
        before_user = user
        before_single, before_legacy = single, legacy
        broken = DailyPetService(NS(database=db), None, None)
        async def fail(*args, **kwargs): raise RuntimeError('journal unavailable')
        broken.transactions = NS(update_one=fail)
        with pytest.raises(RuntimeError, match='journal unavailable'):
            await broken.tap(token, 7, 'failed-query', received_at=now, rate_limit=False)
        assert await db.users.find_one({'id': 7}) == before_user
        assert await db.bank.find_one({'_id': 'single'}) == before_single
        assert await db.bank.find_one({'_id': 'main'}) == before_legacy
        assert await db.transactions.count_documents({'tx_type': 'daily_pet_bonus'}) == 9
    finally:
        await client.drop_database(name)
        client.close()
