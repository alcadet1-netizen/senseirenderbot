"""Economic invariants and explicit known multi-document accounting limitation."""
import asyncio
import copy
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from tests.unit.test_daily_pet import setup, issue
from src.services.daily_pet_service import DailyPetService


@pytest.mark.asyncio
@pytest.mark.parametrize('base', [0, 1, 9, 10, 11, 55, 105, 305])
async def test_additive_rounding_and_coin_conservation(base):
    db, service, _, _ = setup()
    _, token = await issue(service)
    db.users.docs[7]['daily_pet']['base_coins'] = base
    start = copy.deepcopy(db.users.docs[7])
    bank = db.bank.docs['main']['balance']
    with patch('src.services.daily_pet_service.time.time', return_value=105):
        for n in range(1, 21):
            receipt = await service.tap(token, 7, f'rounding:{n}')
            assert receipt['extra_coins'] == base*n//10
            assert db.users.docs[7]['coins'] - start['coins'] == base*n//10
            assert bank-db.bank.docs['main']['balance'] == base*n//10
            assert db.users.docs[7]['xp'] == start['xp']
            assert db.users.docs[7]['daily_streak'] == start['daily_streak']
    payouts = [tx for tx in db.transactions.docs.values() if tx.get('tx_type') == 'daily_pet_bonus']
    assert len(payouts) == 20
    assert sum(tx['coins_change'] for tx in payouts) == base*2


@pytest.mark.asyncio
async def test_independent_workers_cas_and_query_replay_conserve_money():
    db, service, _, mongo = setup()
    _, token = await issue(service)
    workers = [DailyPetService(mongo, service.daily) for _ in range(4)]
    before = db.users.docs[7]['coins']
    bank = db.bank.docs['main']['balance']
    read = db.users.find_one

    async def interleaved(query):
        result = await read(query)
        await asyncio.sleep(0)
        return result

    with patch.object(db.users, 'find_one', side_effect=interleaved), \
         patch('src.services.daily_pet_service.time.time', return_value=105):
        await asyncio.gather(*(worker.tap(token,7,f'cross-worker:{i}') for i, worker in enumerate(workers)))
        await asyncio.gather(*(worker.tap(token,7,'cross-worker:0') for worker in workers))
    receipt = db.users.docs[7]['daily_pet']
    assert receipt['taps'] == 4 and len(set(receipt['queries'])) == 4
    assert db.users.docs[7]['coins']-before == receipt['base_coins']*4//10
    assert bank-db.bank.docs['main']['balance'] == db.users.docs[7]['coins']-before


@pytest.mark.asyncio
@pytest.mark.xfail(strict=True, raises=AssertionError, reason='Known: user credit and shared-bank debit are not one Mongo transaction; see docs/ECONOMY_AUDIT.md')
async def test_shared_bank_race_must_not_mint_unfunded_bonus():
    db, service, _, mongo = setup()
    db.users.docs[8] = {**copy.deepcopy(db.users.docs[7]), 'id': 8}
    _, token7 = await issue(service)
    _, session8 = await service.claim(8)
    await service.activate(session8['token'], 8, 100)
    other = DailyPetService(mongo, service.daily)
    db.bank.docs['main']['balance'] = 5
    before = sum(db.users.docs[uid]['coins'] for uid in (7,8))
    read = db.bank.find_one
    arrived = 0
    both = asyncio.Event()

    async def concurrent_balance(query):
        nonlocal arrived
        snapshot = await read(query)
        arrived += 1
        if arrived == 2:
            both.set()
        await asyncio.wait_for(both.wait(), 2)
        return snapshot

    with patch.object(db.bank, 'find_one', side_effect=concurrent_balance), \
         patch('src.services.daily_pet_service.time.time', return_value=105):
        await asyncio.gather(service.tap(token7,7,'bank-race:7'),
                             other.tap(session8['token'],8,'bank-race:8'))
    credited = sum(db.users.docs[uid]['coins'] for uid in (7,8))-before
    debited = 5-db.bank.docs['main']['balance']
    assert credited == debited  # Currently 10 credited, only 5 debited.


@pytest.mark.asyncio
async def test_failed_bank_debit_is_visible_and_retry_cannot_duplicate_user_credit(caplog):
    db, service, _, _ = setup()
    _, token = await issue(service)
    before = db.users.docs[7]['coins']
    with patch.object(db.bank, 'update_one', return_value=SimpleNamespace(matched_count=0)), \
         patch('src.services.daily_pet_service.time.time', return_value=105):
        await service.tap(token,7,'unmatched-bank')
        await service.tap(token,7,'unmatched-bank')
    assert db.users.docs[7]['coins']-before == db.users.docs[7]['daily_pet']['base_coins']//10
    assert db.users.docs[7]['daily_pet']['taps'] == 1
    assert 'ledger needs reconciliation' in caplog.text


@pytest.mark.asyncio
@pytest.mark.xfail(strict=True, raises=AssertionError, reason='Known: base daily user receipt and shared-bank debit are not atomic; see docs/ECONOMY_AUDIT.md')
async def test_shared_bank_race_must_not_mint_unfunded_base_daily():
    from src.services.daily_service import DailyService
    from src.services.hedgehog_service import utc_day
    db, service, _, mongo = setup()
    db.users.docs[8] = {**copy.deepcopy(db.users.docs[7]), 'id': 8}
    db.bank.docs['main']['balance'] = 55
    before = sum(db.users.docs[uid]['coins'] for uid in (7,8))
    read = db.bank.find_one
    both = asyncio.Event()
    reads = 0

    async def concurrent_balance(query):
        nonlocal reads
        snapshot = await read(query)
        reads += 1
        if reads == 2:
            both.set()
        await asyncio.wait_for(both.wait(), 2)
        return snapshot

    with patch.object(db.bank, 'find_one', side_effect=concurrent_balance):
        await asyncio.gather(*(DailyService(mongo).settle_hedgehog(uid,True,utc_day(),ordinary=True) for uid in (7,8)))
    credited = sum(db.users.docs[uid]['coins'] for uid in (7,8))-before
    debited = 55-db.bank.docs['main']['balance']
    assert credited == debited  # Currently 110 credited, only 55 debited.
