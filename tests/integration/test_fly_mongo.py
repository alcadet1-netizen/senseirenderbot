"""Opt-in limits tested on the disposable CI replica set, never production."""
import asyncio
import os
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace as NS

import pytest
from motor.motor_asyncio import AsyncIOMotorClient
from src.services.fly_service import FlyService
from tests.unit.test_fly import message


@pytest.mark.asyncio
async def test_real_mongo_concurrent_fly_limits_and_replay():
    uri=os.environ.get('CAMPAIGN_TEST_MONGO_URI')
    if not uri: pytest.skip('CI replica set required')
    client=AsyncIOMotorClient(uri,tz_aware=True,serverSelectionTimeoutMS=5000)
    name='sensei_fly_test_'+uuid.uuid4().hex
    db=client[name]
    try:
        container=NS(mongo_client=NS(database=db),settings=NS(fly_reactions_enabled=True))
        service=FlyService(container,clock=lambda:datetime(2026,11,6,12,tzinfo=timezone.utc),roll=lambda:0)
        await service.ensure_indexes()
        assert await service.reserve(message()) is None
        await db.fly_settings.insert_one({'_id':-100222,'enabled':True})
        # Seed shared state to exercise write-conflict retries rather than initial upsert races.
        await db.fly_chat_state.insert_one({'_id':-100222})
        results=await asyncio.gather(*(service.reserve(message(mid=i,uid=i+20)) for i in range(10)))
        assert sum(r is not None for r in results)==1
        for i in range(10): assert await service.reserve(message(mid=i,uid=i+20)) is None
        assert (await db.fly_chat_state.find_one({'_id':-100222}))['count']==1
        assert await db.fly_decisions.count_documents({'selected':True})==1
        assert await db.users.count_documents({})==0 and await db.bank.count_documents({})==0
    finally:
        await client.drop_database(name)
        client.close()
