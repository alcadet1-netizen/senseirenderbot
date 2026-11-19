"""Real replica-set checks for player-to-player duel stakes."""
import asyncio
import os
import uuid
from types import SimpleNamespace as NS

import pytest
from motor.motor_asyncio import AsyncIOMotorClient
from src.services.duel_escrow import DuelEscrow


@pytest.mark.asyncio
async def test_duel_escrow_races_and_recovery_after_journal_error():
    uri = os.environ.get('CAMPAIGN_TEST_MONGO_URI')
    if not uri:
        pytest.skip('MongoDB replica set required')
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
    name = 'sensei_duel_escrow_' + uuid.uuid4().hex
    db = client[name]
    try:
        await db.users.insert_many([{'id': uid, 'coins': 1000} for uid in (7, 8, 9)])
        await db.bank.insert_one({'_id': 'single', 'coins': 500, 'total_emitted': 5000})
        workers = [DuelEscrow(NS(database=db)) for _ in range(8)]
        reserved = await asyncio.gather(*(w.reserve('game-one', 7, 8, 300, 123) for w in workers))
        assert all(reserved)
        assert (await db.users.find_one({'id': 7}))['coins'] == 700
        assert (await db.users.find_one({'id': 8}))['coins'] == 700
        assert await db.transactions.count_documents({'tx_type': 'duel_escrow'}) == 2
        results = await asyncio.gather(*(w.settle('game-one', 7) for w in workers))
        assert all(r['state'] == 'settled' for r in results)
        assert (await db.users.find_one({'id': 7}))['coins'] == 1300
        assert (await db.users.find_one({'id': 8}))['coins'] == 700
        assert await db.transactions.count_documents({'tx_type': 'duel_bet_payout'}) == 1
        assert (await db.bank.find_one({'_id': 'single'}))['coins'] == 500
        assert (await db.bank.find_one({'_id': 'single'}))['total_emitted'] == 5000
        # A payout failure retains its winner decision and rolls back credit.
        await workers[0].reserve('game-two', 8, 9, 300, 124)
        broken = DuelEscrow(NS(database=db))
        async def fail(*args, **kwargs): raise RuntimeError('journal unavailable')
        broken.transactions = NS(insert_one=fail)
        with pytest.raises(RuntimeError, match='journal unavailable'):
            await broken.settle('game-two', 9)
        assert (await db.users.find_one({'id': 9}))['coins'] == 700
        doc = await db.duel_escrows.find_one({'_id': 'game-two'})
        assert doc['state'] == 'decided' and doc['winner_id'] == 9
        with pytest.raises(RuntimeError, match='decided differently'):
            await workers[0].settle('game-two', None)
        await DuelEscrow(NS(database=db)).settle('game-two', 9)
        assert (await db.users.find_one({'id': 9}))['coins'] == 1300
        # A missing recipient aborts both potential refunds, even after the
        # first credit; fixing the document makes the same decision resumable.
        await workers[0].reserve('refund-test', 7, 8, 300, 126)
        await db.users.delete_one({'id': 8})
        before7 = (await db.users.find_one({'id': 7}))['coins']
        with pytest.raises(RuntimeError, match='recipient missing'):
            await workers[0].settle('refund-test', None)
        assert (await db.users.find_one({'id': 7}))['coins'] == before7
        assert (await db.duel_escrows.find_one({'_id': 'refund-test'}))['state'] == 'decided'
        await db.users.insert_one({'id': 8, 'coins': 100})
        await workers[0].settle('refund-test', None)
        assert (await db.users.find_one({'id': 7}))['coins'] == before7 + 300
        assert (await db.users.find_one({'id': 8}))['coins'] == 400
        await workers[0].reserve('game-three', 8, 9, 300, 125)
        await asyncio.gather(*(w.settle('game-three', None) for w in workers))
        assert (await db.users.find_one({'id': 8}))['coins'] == 400
        assert (await db.users.find_one({'id': 9}))['coins'] == 1300
    finally:
        await client.drop_database(name)
        client.close()


@pytest.mark.asyncio
async def test_recovery_retries_decided_concurrently_without_touching_live_escrow():
    uri = os.environ.get('CAMPAIGN_TEST_MONGO_URI')
    if not uri:
        pytest.skip('MongoDB replica set required')
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
    name = 'sensei_duel_recovery_' + uuid.uuid4().hex
    db = client[name]
    try:
        await db.users.insert_many([{'id': uid, 'coins': 1000, 'xp': 10, 'has_katana': True, 'katana_length': 1.0} for uid in (7, 8, 9, 10)])
        workers = [DuelEscrow(NS(database=db)) for _ in range(6)]
        await workers[0].reserve('finished', 7, 8, 300, 1)
        await workers[0].reserve('active', 9, 10, 300, 2)
        broken = DuelEscrow(NS(database=db))
        async def fail(*args, **kwargs): raise RuntimeError('journal unavailable')
        broken.transactions = NS(insert_one=fail)
        with pytest.raises(RuntimeError):
            await broken.settle('finished', 7)
        assert (await db.duel_escrows.find_one({'_id': 'finished'}))['state'] == 'decided'
        await asyncio.gather(*(w.recover_decided() for w in workers))
        await DuelEscrow(NS(database=db)).recover_decided()
        assert (await db.duel_escrows.find_one({'_id': 'finished'}))['state'] == 'settled'
        assert (await db.duel_escrows.find_one({'_id': 'active'}))['state'] == 'reserved'
        assert (await db.users.find_one({'id': 7}))['coins'] == 1300
        winner = await db.users.find_one({'id': 7})
        loser = await db.users.find_one({'id': 8})
        assert winner['xp'] == 60 and winner['wins'] == 1 and winner['katana_length'] == 1.01
        assert loser['losses'] == 1 and loser['katana_length'] == .99
        assert await db.transactions.count_documents({'escrow_id': 'finished', 'tx_type': 'duel_win'}) == 1
        assert (await db.users.find_one({'id': 8}))['coins'] == 700
        assert (await db.users.find_one({'id': 9}))['coins'] == 700
        assert (await db.users.find_one({'id': 10}))['coins'] == 700
        assert await db.transactions.count_documents({'escrow_id': 'finished', 'tx_type': 'duel_bet_payout'}) == 1
    finally:
        await client.drop_database(name)
        client.close()


@pytest.mark.asyncio
async def test_same_duel_command_reserves_once_across_processes_and_restart():
    from unittest.mock import AsyncMock
    from src.services.duel_service import DuelService, Duel
    uri = os.environ.get('CAMPAIGN_TEST_MONGO_URI')
    if not uri:
        pytest.skip('MongoDB replica set required')
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
    name = 'sensei_duel_request_' + uuid.uuid4().hex
    db = client[name]
    try:
        await db.users.insert_many([{'id': 7, 'coins': 1000}, {'id': 8, 'coins': 1000}])
        container = NS(mongo_client=NS(database=db), user_service=NS(), economy_service=NS())
        workers = [DuelService(container) for _ in range(8)]
        results = await asyncio.gather(*(w.create_duel(7, 8, 300, -100, AsyncMock(), request_id='-100:42')
                                         for w in workers))
        fights = [r for r in results if isinstance(r, Duel)]
        assert len(fights) == 1
        assert all(isinstance(r, Duel) or 'уже обработан' in r for r in results)
        assert (await db.users.find_one({'id': 7}))['coins'] == 700
        assert (await db.users.find_one({'id': 8}))['coins'] == 700
        assert await db.duel_escrows.count_documents({}) == 1
        assert await db.transactions.count_documents({'tx_type': 'duel_escrow'}) == 2
        owner = next(w for w in workers if fights[0].id in w.duels)
        await owner.shutdown()
        assert (await db.users.find_one({'id': 7}))['coins'] == 1000
        assert (await db.users.find_one({'id': 8}))['coins'] == 1000
        after_restart = await DuelService(container).create_duel(7, 8, 300, -100, AsyncMock(), request_id='-100:42')
        assert 'уже обработан' in after_restart
        assert await db.duel_escrows.count_documents({}) == 1
    finally:
        await client.drop_database(name)
        client.close()
