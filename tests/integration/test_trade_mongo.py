"""Isolated replica-set trade concurrency and rollback checks."""
import asyncio
import os
import uuid
from types import SimpleNamespace as NS
from unittest.mock import patch

import pytest
from motor.motor_asyncio import AsyncIOMotorClient
from src.infra.mongo.financial_collections import prepare_financial_collections
from src.services.trade_service import TradeService


@pytest.mark.asyncio
async def test_trade_replay_funding_and_journal_failure():
    uri = os.environ.get('CAMPAIGN_TEST_MONGO_URI')
    if not uri:
        pytest.skip('MongoDB replica set required')
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
    name = 'sensei_trade_' + uuid.uuid4().hex
    db = client[name]
    try:
        assert await prepare_financial_collections(db) == []
        await db.users.insert_one({'id': 7, 'coins': 1000})
        await db.bank.insert_many([{'_id': 'single', 'coins': 20, 'total_emitted': 10000},
                                   {'_id': 'main', 'balance': 100}])
        workers = [TradeService(NS(database=db)) for _ in range(8)]
        with patch('src.services.trade_service.settings.trade_win_chance', .5), \
             patch('src.services.trade_service.random.random', return_value=.1):
            results = await asyncio.gather(*(w.play_game(7, 100, request_id='chat:42') for w in workers))
            restarted = await TradeService(NS(database=db)).play_game(7, 100, request_id='chat:42')
        assert all(r == results[0] and r['success'] for r in results)
        assert restarted == results[0] and results[0]['payout'] == 190
        assert (await db.users.find_one({'id': 7}))['coins'] == 1090
        assert (await db.bank.find_one({'_id': 'single'}))['coins'] == 0
        assert (await db.bank.find_one({'_id': 'main'}))['balance'] == 30
        assert (await db.bank.find_one({'_id': 'single'}))['total_emitted'] == 10000
        assert await db.transactions.count_documents({'description': 'Trade bet'}) == 1
        assert await db.transactions.count_documents({'description': 'Trade win'}) == 1
        before_user = await db.users.find_one({'id': 7})
        before_bank = await db.bank.find({}).sort('_id', 1).to_list(length=None)
        broken = TradeService(NS(database=db))
        async def fail(*args, **kwargs): raise RuntimeError('journal unavailable')
        broken.transactions = NS(insert_one=fail)
        with patch('src.services.trade_service.settings.trade_win_chance', .5), \
             patch('src.services.trade_service.random.random', return_value=.9):
            result = await broken.play_game(7, 100)
        assert not result['success'] and 'не подтверждён' in result['error']
        assert await db.users.find_one({'id': 7}) == before_user
        assert await db.bank.find({}).sort('_id', 1).to_list(length=None) == before_bank
        assert await db.transactions.count_documents({}) == 2
    finally:
        await client.drop_database(name)
        client.close()
