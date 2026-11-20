"""Verify the bank snapshot includes only still-held player stakes."""
import os
import uuid
from types import SimpleNamespace

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

from src.infra.mongo.financial_collections import prepare_financial_collections
from src.services.duel_escrow import DuelEscrow
from src.services.stats_service import StatsService


@pytest.mark.asyncio
async def test_bank_snapshot_tracks_reserved_decided_and_settled_duel_stakes():
    uri = os.environ.get('CAMPAIGN_TEST_MONGO_URI')
    if not uri:
        pytest.skip('MongoDB replica set required')
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
    name = 'sensei_bank_duel_' + uuid.uuid4().hex
    db = client[name]
    try:
        await prepare_financial_collections(db)
        await db.bank.insert_one({'_id': 'single', 'coins': 500, 'total_emitted': 2500, 'burned': 0})
        await db.users.insert_many([{'id': 7, 'coins': 1000}, {'id': 8, 'coins': 1000}])
        mongo = SimpleNamespace(database=db, client=client)
        duel = DuelEscrow(mongo)
        stats = StatsService(mongo)
        await duel.reserve('duel', 7, 8, 300, 1)
        reserved = await stats.get_bank_summary()
        assert (reserved['circulation'], reserved['duel_escrow'], reserved['total_supply']) == (1400, 600, 2500)
        broken = DuelEscrow(mongo)
        async def fail(*args, **kwargs):
            raise RuntimeError('journal unavailable')
        broken.transactions = SimpleNamespace(insert_one=fail)
        with pytest.raises(RuntimeError):
            await broken.settle('duel', 7)
        stats.invalidate()
        decided = await stats.get_bank_summary()
        assert (decided['circulation'], decided['duel_escrow'], decided['total_supply']) == (1400, 600, 2500)
        await duel.settle('duel', 7)
        stats.invalidate()
        settled = await stats.get_bank_summary()
        assert (settled['circulation'], settled['duel_escrow'], settled['total_supply']) == (2000, 0, 2500)
        await db.duel_escrows.insert_one({'_id': 'bad', 'state': 'reserved', 'bet': 'unknown'})
        stats.invalidate()
        unknown = await stats.get_bank_summary()
        assert unknown['duel_escrow'] is None and unknown['total_supply'] is None
    finally:
        await client.drop_database(name)
        client.close()
