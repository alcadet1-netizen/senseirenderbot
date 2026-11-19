"""Isolated Mongo replica set tests for Coin/ticket exchanges."""
import asyncio
import os
import uuid
from types import SimpleNamespace as NS

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

from src.services.exchange_service import ExchangeService
from src.infra.mongo.financial_collections import prepare_financial_collections


@pytest.mark.asyncio
@pytest.mark.parametrize('attempt', range(15))
@pytest.mark.parametrize('precreated', [False, True])
async def test_exchange_replay_conservation_and_rollback(attempt, precreated, caplog):
    uri = os.environ.get('CAMPAIGN_TEST_MONGO_URI')
    if not uri:
        pytest.skip('MongoDB replica set required')
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
    name = 'sensei_exchange_test_' + uuid.uuid4().hex
    db = client[name]
    try:
        await db.users.insert_one({'id': 7, 'coins': 6000})
        await db.bank.insert_many([{'_id': 'single', 'coins': 100, 'total_emitted': 10000, 'burned': 20},
                                   {'_id': 'main', 'balance': 500}])
        if precreated:
            assert await prepare_financial_collections(db) == []
        services = [ExchangeService(NS(database=db)) for _ in range(8)]
        buys = await asyncio.gather(*(s.coins_to_ticket(7, request_id='buy-callback') for s in services))
        successes = [r for r in buys if r['success']]
        unconfirmed = [r for r in buys if not r['success']]
        assert successes and all(r == successes[0] for r in successes), buys
        if unconfirmed:
            errors = [(type(r.exc_info[1]).__name__, getattr(r.exc_info[1], 'code', None),
                       str(r.exc_info[1]).split('full error:')[0][:400])
                      for r in caplog.records if r.levelname == 'ERROR' and r.exc_info]
            assert not precreated, (buys, errors)
            assert all('Не удалось подтвердить обмен' in r['error'] for r in unconfirmed), buys
            assert len(errors) >= len(unconfirmed), errors
            assert all(kind == 'OperationFailure' and code == 112
                       and 'Collection namespace' in message and 'is already in use' in message
                       for kind, code, message in errors), errors
        assert await db.tickets.count_documents({'user_id': 7, 'burned': False}) == 1
        assert await db.transactions.count_documents({'tx_type': 'exchange_in'}) == 1
        assert (await db.users.find_one({'id': 7}))['coins'] == 3000
        assert (await db.bank.find_one({'_id': 'single'}))['coins'] == 3100
        # Same request ID cannot be reused for another direction or user.
        assert not (await services[0].ticket_to_coins(7, 'buy-callback'))['success']
        assert not (await services[0].coins_to_ticket(8, 'buy-callback'))['success']
        sells = await asyncio.gather(*(s.ticket_to_coins(7, request_id='sell-callback') for s in services))
        assert all(r == sells[0] and r['success'] for r in sells)
        assert (await db.users.find_one({'id': 7}))['coins'] == 5600
        assert (await db.bank.find_one({'_id': 'single'}))['coins'] == 500
        assert (await db.bank.find_one({'_id': 'single'}))['total_emitted'] == 10000
        assert await db.tickets.count_documents({'user_id': 7, 'burned': True}) == 1
        assert await db.transactions.count_documents({'tx_type': 'exchange_out'}) == 1
        assert (await db.users.find_one({'id': 7}))['coins'] + 500 + 500 == 6600

        # Real Mongo operations followed by a journal failure must abort all steps.
        async def fail(*args, **kwargs):
            raise RuntimeError('journal unavailable')
        broken = ExchangeService(NS(database=db))
        broken.transactions = NS(insert_one=fail)
        result = await broken.coins_to_ticket(7)
        assert not result['success'] and 'подтвердить' in result['error']
        assert (await db.users.find_one({'id': 7}))['coins'] == 5600
        assert (await db.bank.find_one({'_id': 'single'}))['coins'] == 500
        assert await db.tickets.count_documents({'user_id': 7}) == 1
        # Insufficient bank aborts the tentative ticket burn.
        await db.tickets.insert_one({'user_id': 7, 'code': 'T2', 'burned': False})
        result = await services[0].ticket_to_coins(7, 'insufficient-bank')
        assert not result['success']
        assert not (await db.tickets.find_one({'code': 'T2'}))['burned']
        assert (await db.users.find_one({'id': 7}))['coins'] == 5600
    finally:
        await client.drop_database(name)
        client.close()
