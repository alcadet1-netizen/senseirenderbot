import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from motor.motor_asyncio import AsyncIOMotorClient
from src.services.bank_history import read_bank_history


@pytest.mark.asyncio
async def test_history_aggregates_known_types_only_without_writes():
    uri = os.environ.get('CAMPAIGN_TEST_MONGO_URI')
    if not uri:
        pytest.skip('MongoDB replica set required')
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
    name = 'sensei_bank_history_' + uuid.uuid4().hex
    db = client[name]
    now = datetime(2026, 1, 31, tzinfo=timezone.utc)
    try:
        await db.transactions.insert_many([
            {'tx_type': 'burn', 'coins_change': -10, 'created_at': now - timedelta(days=1)},
            {'tx_type': 'burn', 'coins_change': 'bad', 'created_at': now - timedelta(days=2)},
            {'tx_type': 'burn', 'coins_change': -99, 'created_at': now - timedelta(days=31)},
            {'tx_type': 'private', 'coins_change': 100, 'created_at': now - timedelta(days=1)},
            {'tx_type': 'burn', 'coins_change': -1},
        ])
        _, _, rows = await read_bank_history(db, now=now)
        assert rows == [{'_id': 'burn', 'count': 2, 'amount': -10, 'invalid': 1}]
        assert await db.transactions.count_documents({}) == 5
    finally:
        await client.drop_database(name)
        client.close()
