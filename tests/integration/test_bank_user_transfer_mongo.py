"""Admin and zov transfers on a disposable transactional MongoDB."""
import asyncio
import os
import uuid
from types import SimpleNamespace as NS

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

from src.services.economy_service import EconomyService


@pytest.mark.asyncio
async def test_bank_transfers_conserve_funds_under_race_and_rollback():
    uri = os.environ.get('CAMPAIGN_TEST_MONGO_URI')
    if not uri:
        pytest.skip('MongoDB replica set required')
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
    name = 'sensei_transfer_test_' + uuid.uuid4().hex
    db = client[name]
    try:
        await db.bank.insert_many([{'_id': 'single', 'coins': 3, 'total_emitted': 100, 'burned': 5},
                                   {'_id': 'main', 'balance': 7}])
        await db.users.insert_many([{'id': 7, 'coins': 1000}, {'id': 8, 'coins': 0}])
        svc = EconomyService(NS(database=db))
        other = EconomyService(NS(database=db))
        admin, zov = await asyncio.gather(svc.admin_add_coins(7, 8, 42),
                                          other.distribute_zov_reward(8, 8))
        assert int(admin['success']) + int(zov) == 1
        single = await db.bank.find_one({'_id': 'single'})
        legacy = await db.bank.find_one({'_id': 'main'})
        users = await db.users.find({}).to_list(length=None)
        assert single['coins'] + legacy['balance'] == 2
        assert sum(user['coins'] for user in users) == 1008
        assert single['total_emitted'] == 100 and single['burned'] == 5
        assert not (await svc.admin_add_coins(999, 1, 42))['success']
        assert (await db.bank.find_one({'_id': 'main'}))['balance'] == legacy['balance']

        # Inject a journal failure while all bank/user operations remain real Mongo operations.
        async def fail(*args, **kwargs):
            raise RuntimeError('journal unavailable')
        broken = EconomyService(NS(database=db))
        broken.transactions = NS(insert_one=fail)
        with pytest.raises(RuntimeError, match='journal unavailable'):
            await broken.admin_add_coins(7, 1, 42)
        assert await db.bank.find_one({'_id': 'single'}) == single
        assert await db.bank.find_one({'_id': 'main'}) == legacy
        assert sorted(await db.users.find({}).to_list(length=None), key=lambda u: u['id']) == sorted(users, key=lambda u: u['id'])
    finally:
        await client.drop_database(name)
        client.close()
