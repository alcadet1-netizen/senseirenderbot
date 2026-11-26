"""Mongo transaction rollback and duplicate invoice protection for Stars."""
import asyncio
import os
import uuid
from types import SimpleNamespace as NS

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

from src.services.dojo_miner_service import DojoMinerService
from src.services.dojo_upgrade_service import DojoUpgradeService


@pytest.mark.asyncio
async def test_boost_and_invoice_concurrency_with_real_mongo():
    uri = os.environ.get('CAMPAIGN_TEST_MONGO_URI')
    if not uri:
        pytest.skip('MongoDB replica set required')
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
    name = 'sensei_dojo_test_' + uuid.uuid4().hex
    db = client[name]
    mongo = NS(database=db)
    try:
        await db.users.insert_one({'id': 7, 'coins': 0})
        miner = DojoMinerService(mongo, NS())
        await miner.start(7)
        services = [DojoUpgradeService(NS(mongo_client=mongo, dojo_miner_service=miner)) for _ in range(2)]
        order = await services[0].prepare(7, 'energy')
        def payment(charge):
            return NS(invoice_payload=order['payload'], currency='XTR', total_amount=50,
                      telegram_payment_charge_id=charge)
        results = await asyncio.gather(*(s.receive(7, payment(f'charge-{i}')) for i, s in enumerate(services)))
        assert sorted(r['state'] for r in results) == ['fulfilled', 'refund_required']
        assert (await db.users.find_one({'id': 7}))['dojo_energy_purchases'] == 1
        assert await miner.apply_speed_boost(7, 'boost-charge')
        after = await db.dojo_miners.find_one({'_id': 7})
        assert await miner.apply_speed_boost(7, 'boost-charge')
        assert (await db.dojo_miners.find_one({'_id': 7}))['amount'] == after['amount']
    finally:
        await client.drop_database(name)
        client.close()
