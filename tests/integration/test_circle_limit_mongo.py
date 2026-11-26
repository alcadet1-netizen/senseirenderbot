"""Concurrent CAS across workers using a disposable MongoDB test database."""
import asyncio
import os
import uuid
from types import SimpleNamespace as NS
from unittest.mock import patch

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

from src.services.dojo_miner_service import DojoMinerService


@pytest.mark.asyncio
async def test_simultaneous_circles_across_mongo_clients():
    uri = os.environ.get('CAMPAIGN_TEST_MONGO_URI')
    if not uri:
        pytest.skip('MongoDB test instance required')
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
    name = 'sensei_circle_test_' + uuid.uuid4().hex
    db = client[name]
    try:
        await db.users.insert_one({'id': 7, 'coins': 0})
        services = [DojoMinerService(NS(database=db), NS()) for _ in range(20)]
        with patch('src.services.dojo_miner_service.time.time', return_value=1000):
            await services[0].start(7)
        with patch('src.services.dojo_miner_service.time.time', return_value=4600):
            results = await asyncio.gather(*(service.add_circle_energy(7, 1000, f'circle-{i:04}')
                                             for i, service in enumerate(services)))
            assert sum(r['added'] for r in results) == 1
            assert len((await db.dojo_miners.find_one({'_id': 7}))['circle_energy_events']) == 1
            winner = next(i for i, r in enumerate(results) if r['added'])
            assert (await services[-1].add_circle_energy(7, 1000, f'circle-{winner:04}'))['replayed']
    finally:
        await client.drop_database(name)
        client.close()
