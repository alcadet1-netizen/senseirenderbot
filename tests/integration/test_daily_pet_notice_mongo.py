"""Notice CAS against a disposable Mongo database, never production."""
import asyncio
import os
import uuid
from types import SimpleNamespace as NS

import pytest
from motor.motor_asyncio import AsyncIOMotorClient
from src.services.daily_pet_service import DailyPetService


@pytest.mark.asyncio
async def test_notice_single_winner_across_workers_and_restart():
    uri = os.environ.get('CAMPAIGN_TEST_MONGO_URI')
    if not uri:
        pytest.skip('CI Mongo required')
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
    name = 'sensei_notice_test_' + uuid.uuid4().hex
    db = client[name]
    token = 'a' * 32
    try:
        session = dict(token=token, day='2026-11-09', state='active', deadline=1,
                       delivered=False, taps=0, extra_coins=0)
        await db.users.insert_one(dict(id=7, hedgehog_day=session['day'], daily_pet=session,
                                       coins=500, xp=200))
        workers = [DailyPetService(NS(database=db), None) for _ in range(20)]
        winners = await asyncio.gather(*(worker.reserve_notice(token, 7) for worker in workers))
        assert sum(winners) == 1
        restarted = DailyPetService(NS(database=db), None)
        assert not await restarted.reserve_notice(token, 7)
        await restarted.mark_delivered(token, 7)
        assert not await restarted.reserve_notice(token, 7)
        user = await db.users.find_one({'id': 7})
        assert user['daily_pet']['notice_state'] == 'sent'
        assert user['coins'] == 500 and user['xp'] == 200
        assert await db.transactions.count_documents({}) == 0
        assert await db.bank.count_documents({}) == 0
    finally:
        await client.drop_database(name)
        client.close()
