"""Collection bootstrap against an isolated MongoDB replica set."""
import asyncio
import os
import uuid

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

from src.infra.mongo.financial_collections import COLLECTIONS, prepare_financial_collections


@pytest.mark.asyncio
async def test_concurrent_startup_preserves_existing_documents():
    uri = os.environ.get('CAMPAIGN_TEST_MONGO_URI')
    if not uri:
        pytest.skip('MongoDB replica set required')
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
    name = 'sensei_prepare_' + uuid.uuid4().hex
    db = client[name]
    try:
        await db.transactions.insert_one({'_id': 'existing', 'coins_change': 5})
        results = await asyncio.gather(*(prepare_financial_collections(db) for _ in range(8)))
        assert results == [[] for _ in range(8)]
        assert set(COLLECTIONS) <= set(await db.list_collection_names())
        assert await db.transactions.find_one({'_id': 'existing'}) == {'_id': 'existing', 'coins_change': 5}
        assert await db.duel_escrows.count_documents({}) == 0
        assert await db.tickets.count_documents({}) == 0
        assert await prepare_financial_collections(db) == []
    finally:
        await client.drop_database(name)
        client.close()
