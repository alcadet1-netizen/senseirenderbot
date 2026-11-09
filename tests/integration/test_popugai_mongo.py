"""Disposable Mongo only: actual aggregation, concurrent upserts/reservations."""
import asyncio
import os
import uuid
from types import SimpleNamespace as NS
import pytest
from motor.motor_asyncio import AsyncIOMotorClient
from src.services.popugai_service import PopugaiService


@pytest.mark.asyncio
async def test_media_chat_isolation_dedup_and_single_reply_claim():
    uri=os.environ.get('CAMPAIGN_TEST_MONGO_URI')
    if not uri:
        pytest.skip('CI Mongo required')
    client=AsyncIOMotorClient(uri,serverSelectionTimeoutMS=5000)
    name='sensei_popugai_test_'+uuid.uuid4().hex
    db=client[name];svc=PopugaiService(NS(database=db))
    try:
        await svc.ensure_indexes()
        await db.popugai_chances.create_index('chat_id',unique=True)
        await db.popugai_chances.insert_one(dict(chat_id=-1,chance=.5))
        await svc.set_reply_chance(-1,.01)
        assert await svc.get_reply_chance(-1)==.01
        assert await db.popugai_chances.count_documents({})==1
        await asyncio.gather(*(svc.add_media(-1,'gif','file','unique') for _ in range(8)))
        await svc.add_media(-2,'sticker','other','unique')
        assert await db.popugai_media.count_documents({})==2
        assert await svc.get_random_media(-1)==('gif','file')
        assert await svc.get_random_media(-2)==('sticker','other')
        assert await svc.get_random_media(-3) is None
        results=await asyncio.gather(*(svc.reserve_reply(-1,10) for _ in range(8)))
        assert sum(results)==1
        assert await svc.reserve_reply(-2,10)
    finally:
        await client.drop_database(name)
        client.close()
