"""Count semantics checked against an isolated Mongo database, never production."""
import os
import uuid
from types import SimpleNamespace

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

from src.services.broadcast_service import BroadcastService


@pytest.mark.asyncio
async def test_count_matches_legacy_eligibility():
    uri = os.environ.get('CAMPAIGN_TEST_MONGO_URI')
    if not uri:
        pytest.skip('Test MongoDB required')
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
    name = 'sensei_broadcast_' + uuid.uuid4().hex
    db = client[name]
    try:
        await db.users.insert_many([
            {'id': 1}, {'id': 2, 'is_banned': False},
            {'id': 3, 'is_banned': True}, {'id': 4, 'is_banned': None},
        ])
        service = BroadcastService(SimpleNamespace(database=db))
        assert await service.get_count() == len(await service.get_users()) == 3
    finally:
        await client.drop_database(name)
        client.close()
