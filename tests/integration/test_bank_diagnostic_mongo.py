"""Read-only bank diagnostic against a real MongoDB snapshot."""
import os
import uuid

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

from src.services.bank_diagnostic import read_bank_diagnostic


@pytest.mark.asyncio
async def test_private_diagnostic_reads_same_snapshot_without_writes():
    uri = os.environ.get('CAMPAIGN_TEST_MONGO_URI')
    if not uri:
        pytest.skip('MongoDB replica set required')
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
    name = 'sensei_bank_diagnostic_' + uuid.uuid4().hex
    db = client[name]
    try:
        await db.bank.insert_many([{'_id': 'single', 'coins': 75, 'total_emitted': 150, 'burned': 3},
                                   {'_id': 'main', 'balance': 5}])
        await db.users.insert_many([{'id': 1, 'coins': 70}, {'id': 2, 'coins': -20}, {'id': 3}])
        await db.duel_escrows.insert_many([{'_id': 'a', 'state': 'reserved', 'bet': 10},
                                          {'_id': 'b', 'state': 'settled', 'bet': 99}])
        before = await db.bank.find_one({'_id': 'single'})
        result = await read_bank_diagnostic(db)
        assert result['calculated']['ui_total_supply'] == '150'
        assert result['calculated']['emission_minus_ui_total_supply'] == '0'
        assert result['users']['negative_count'] == 1
        assert result['users']['missing_or_non_numeric_count'] == 1
        assert result['duel_escrow']['held_coins'] == '20'
        assert await db.bank.find_one({'_id': 'single'}) == before
        assert await db.users.count_documents({}) == 3
        assert await db.duel_escrows.count_documents({}) == 2
    finally:
        await client.drop_database(name)
        client.close()
