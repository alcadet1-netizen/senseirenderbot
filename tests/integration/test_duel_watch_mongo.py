"""Read-only reservation diagnostics against disposable MongoDB."""
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

from src.services.duel_watch import read_old_reservations


@pytest.mark.asyncio
async def test_only_old_reserved_with_date_selected_no_writes():
    uri = os.environ.get('CAMPAIGN_TEST_MONGO_URI')
    if not uri:
        pytest.skip('Test MongoDB required')
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
    name = 'sensei_watch_' + uuid.uuid4().hex
    db = client[name]
    now = datetime.now(timezone.utc)
    try:
        await db.duel_escrows.insert_many([
            {'_id': 'old', 'state': 'reserved', 'created_at': now - timedelta(hours=2), 'bet': 300},
            {'_id': 'new', 'state': 'reserved', 'created_at': now - timedelta(minutes=1)},
            {'_id': 'decided', 'state': 'decided', 'created_at': now - timedelta(hours=3)},
            {'_id': 'unknown_date', 'state': 'reserved'},
        ])
        before = await db.duel_escrows.find({}).sort('_id', 1).to_list(length=10)
        rows, more = await read_old_reservations(db, now=now)
        assert [row['_id'] for row in rows] == ['old'] and not more
        assert before == await db.duel_escrows.find({}).sort('_id', 1).to_list(length=10)
        assert await db.transactions.count_documents({}) == 0
        assert await db.users.count_documents({}) == 0
    finally:
        await client.drop_database(name)
        client.close()
