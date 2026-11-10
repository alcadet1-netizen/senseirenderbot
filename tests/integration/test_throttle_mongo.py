import asyncio
import os
import uuid
from datetime import datetime
from types import SimpleNamespace as NS
from unittest.mock import patch
import pytest
from motor.motor_asyncio import AsyncIOMotorClient
from src.services.throttle_service import ThrottleService


@pytest.mark.asyncio
async def test_expiry_without_ttl_cleanup_legacy_numeric_and_concurrent_claim():
    uri=os.environ.get('CAMPAIGN_TEST_MONGO_URI')
    if not uri:
        pytest.skip('CI Mongo required')
    client=AsyncIOMotorClient(uri,serverSelectionTimeoutMS=5000)
    name='sensei_throttle_test_'+uuid.uuid4().hex;db=client[name]
    try:
        svc=ThrottleService(NS(database=db))
        # No TTL index: correctness must not depend on a periodic deletion job.
        with patch('src.services.throttle_service.time.time',return_value=1000):
            results=await asyncio.gather(*(svc.throttle('u',5) for _ in range(32)))
            assert sum(results)==1
            assert not await svc.throttle('u',5)
        assert isinstance((await db.throttle.find_one({'_id':'default:u'}))['expiry'],datetime)
        with patch('src.services.throttle_service.time.time',return_value=1005):
            assert await svc.throttle('u',5)
            assert await svc.throttle('u',5,scope='other')
        await db.throttle.insert_one({'_id':'default:legacy','expiry':999})
        with patch('src.services.throttle_service.time.time',return_value=1000):
            assert await svc.throttle('legacy',5)
            assert not await svc.throttle('legacy',5)
            assert await svc.throttle('legacy',0)
        await svc.ensure_indexes()
    finally:
        await client.drop_database(name);client.close()
