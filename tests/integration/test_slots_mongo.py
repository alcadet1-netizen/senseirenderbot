"""Slot races and rollback on an isolated MongoDB replica set."""
import asyncio
import os
import uuid
from types import SimpleNamespace as NS
from unittest.mock import patch

import pytest
from motor.motor_asyncio import AsyncIOMotorClient
from src.services.slots_service import SlotsService


@pytest.mark.asyncio
async def test_slots_concurrent_balance_funding_and_failed_journal():
    uri = os.environ.get('CAMPAIGN_TEST_MONGO_URI')
    if not uri:
        pytest.skip('MongoDB replica set required')
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
    name = 'sensei_slots_test_' + uuid.uuid4().hex
    db = client[name]
    try:
        await db.bank.insert_many([{'_id': 'single', 'coins': 100, 'total_emitted': 10000, 'burned': 20},
                                   {'_id': 'main', 'balance': 500}])
        await db.users.insert_one({'id': 7, 'coins': 100})
        workers = [SlotsService(NS(database=db)) for _ in range(6)]
        with patch('src.services.slots_service.random.random', return_value=.5):
            results = await asyncio.gather(*(w.play_slots(7, 100) for w in workers))
        assert sum(bool(r['success']) for r in results) == 1
        assert (await db.users.find_one({'id': 7}))['coins'] == 0
        assert (await db.bank.find_one({'_id': 'single'}))['coins'] == 200
        assert await db.transactions.count_documents({'tx_type': 'slots_bet'}) == 1
        await db.users.update_one({'id': 7}, {'$set': {'coins': 100}})
        # 3x prize is drawn across both bank documents after stake deposit.
        await db.bank.update_one({'_id': 'single'}, {'$set': {'coins': 50}})
        with patch('src.services.slots_service.random.random', return_value=.1), \
             patch('src.services.slots_service.random.choice', return_value='🍒'):
            win = await SlotsService(NS(database=db)).play_slots(7, 100)
        assert win['success'] and win['prize'] == 300
        assert (await db.users.find_one({'id': 7}))['coins'] == 300
        assert (await db.bank.find_one({'_id': 'single'}))['coins'] == 0
        assert (await db.bank.find_one({'_id': 'main'}))['balance'] == 350
        assert (await db.bank.find_one({'_id': 'single'}))['total_emitted'] == 10000
        before_user = await db.users.find_one({'id': 7})
        before_single = await db.bank.find_one({'_id': 'single'})
        before_main = await db.bank.find_one({'_id': 'main'})
        broken = SlotsService(NS(database=db))
        async def fail(*args, **kwargs): raise RuntimeError('journal unavailable')
        broken.transactions = NS(insert_one=fail)
        with patch('src.services.slots_service.random.random', return_value=.5):
            result = await broken.play_slots(7, 100)
        assert result['reason'] == 'unconfirmed'
        assert await db.users.find_one({'id': 7}) == before_user
        assert await db.bank.find_one({'_id': 'single'}) == before_single
        assert await db.bank.find_one({'_id': 'main'}) == before_main
        assert await db.transactions.count_documents({'tx_type': 'slots_bet'}) == 2
    finally:
        await client.drop_database(name)
        client.close()


@pytest.mark.asyncio
async def test_redelivered_slot_command_credits_once_across_workers_and_restart():
    uri = os.environ.get('CAMPAIGN_TEST_MONGO_URI')
    if not uri:
        pytest.skip('MongoDB replica set required')
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
    name = 'sensei_slots_replay_' + uuid.uuid4().hex
    db = client[name]
    try:
        await db.bank.insert_one({'_id': 'single', 'coins': 1000})
        await db.users.insert_one({'id': 7, 'coins': 1000})
        workers = [SlotsService(NS(database=db)) for _ in range(8)]
        with patch('src.services.slots_service.random.random', return_value=.1), \
             patch('src.services.slots_service.random.choice', return_value='🍒'):
            results = await asyncio.gather(*(w.play_slots(7, 100, request_id='chat:42') for w in workers))
            restart = await SlotsService(NS(database=db)).play_slots(7, 100, request_id='chat:42')
        assert all(result == results[0] and result['success'] for result in results)
        assert restart == results[0]
        assert (await db.users.find_one({'id': 7}))['coins'] == 1200
        assert (await db.bank.find_one({'_id': 'single'}))['coins'] == 800
        assert await db.transactions.count_documents({'tx_type': 'slots_bet'}) == 1
        assert await db.transactions.count_documents({'tx_type': 'slots_win'}) == 1
        conflict = await workers[0].play_slots(7, 200, request_id='chat:42')
        assert conflict['reason'] == 'request_conflict'
    finally:
        await client.drop_database(name)
        client.close()
