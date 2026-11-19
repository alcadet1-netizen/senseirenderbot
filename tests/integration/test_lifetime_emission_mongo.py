"""Concurrent emission reservations and burn on a disposable Mongo replica set."""
import asyncio
import os
import uuid
from types import SimpleNamespace

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

from src.services.emission_service import EmissionService


@pytest.mark.asyncio
async def test_concurrent_reservations_and_burn_do_not_reuse_capacity():
    uri = os.environ.get('CAMPAIGN_TEST_MONGO_URI')
    if not uri:
        pytest.skip('MongoDB replica set required')
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
    name = 'sensei_emission_test_' + uuid.uuid4().hex
    db = client[name]
    try:
        await db.bank.insert_one({'_id': 'single', 'coins': 0, 'total_emitted': 500,
                                  'burned': 200, 'emission_cap': 1000})
        services = [EmissionService(SimpleNamespace(database=db), cap=1000) for _ in range(10)]
        results = await asyncio.gather(*(svc.reserve(100) for svc in services))
        assert sum(results) == 3
        assert await services[0].burn(100) == 100
        assert not await services[1].reserve(1)
        doc = await db.bank.find_one({'_id': 'single'})
        assert doc['total_emitted'] == 700 and doc['burned'] == 300
    finally:
        await client.drop_database(name)
        client.close()
