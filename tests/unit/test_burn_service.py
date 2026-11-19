"""Burn accounting commits all writes together and is retry-safe."""
import asyncio
import copy
from types import SimpleNamespace as NS

import pytest
from pymongo.errors import DuplicateKeyError

from src.services.burn_service import BurnService
from src.services.hedgehog_service import GameError


class Collection:
    def __init__(self, docs=()):
        self.docs = {d.get('_id', d.get('id')): copy.deepcopy(d) for d in docs}
        self.fail_insert = False
        self.sessions = []

    @staticmethod
    def matches(doc, query):
        for key, value in query.items():
            actual = doc.get(key)
            if isinstance(value, dict):
                if '$ne' in value and actual == value['$ne']: return False
                if '$gte' in value and (actual is None or actual < value['$gte']): return False
                if '$lte' in value and (actual is None or actual > value['$lte']): return False
            elif actual != value: return False
        return True

    async def find_one(self, query, **kwargs):
        return next((copy.deepcopy(d) for d in self.docs.values() if self.matches(d, query)), None)

    async def update_one(self, query, changes, **kwargs):
        self.sessions.append(kwargs.get("session"))
        doc = next((d for d in self.docs.values() if self.matches(d, query)), None)
        if doc is None: return NS(matched_count=0)
        doc.update(copy.deepcopy(changes.get('$set', {})))
        for key, value in changes.get('$inc', {}).items(): doc[key] = doc.get(key, 0) + value
        return NS(matched_count=1)

    async def insert_one(self, doc, **kwargs):
        self.sessions.append(kwargs.get('session'))
        if self.fail_insert: raise RuntimeError('log unavailable')
        if doc['_id'] in self.docs: raise DuplicateKeyError('duplicate')
        self.docs[doc['_id']] = copy.deepcopy(doc)


@pytest.fixture
def setup(monkeypatch):
    db = NS(users=Collection([{'id': 7, 'coins': 5000}]), transactions=Collection(),
            bank=Collection([{'_id': 'single', 'coins': 1_000_000,
                              'total_emitted': 10_000, 'burned': 0, 'emission_cap': 10_000_000_000}]))
    lock = asyncio.Lock()
    async def transaction(mongo, callback):
        async with lock:
            snapshots = [copy.deepcopy(c.docs) for c in (db.users, db.bank, db.transactions)]
            try:
                return await callback('session')
            except BaseException:
                for collection, saved in zip((db.users, db.bank, db.transactions), snapshots):
                    collection.docs = saved
                raise
    monkeypatch.setattr('src.services.burn_service.transaction', transaction)
    return db, BurnService(NS(database=db))


@pytest.mark.asyncio
async def test_burn_and_retry(setup):
    db, burner = setup
    result = await burner.burn(7, 1000, 'burn-request-0001')
    assert result['amount'] == 1000 and result['balance'] == 4000
    assert db.users.docs[7]['burned_coins'] == 1000
    assert db.bank.docs['single']['coins'] == 1_000_000
    assert db.bank.docs['single']['total_emitted'] == 9000
    assert db.bank.docs['single']['burned'] == 1000
    assert (await burner.burn(7, 1000, 'burn-request-0001'))['duplicate']
    assert len(db.transactions.docs) == 1
    assert db.users.sessions == ['session']
    assert db.bank.sessions == ['session', 'session']
    assert db.transactions.sessions == ['session']


@pytest.mark.asyncio
async def test_concurrent_duplicate_and_interleaved_ids(setup):
    db, burner = setup
    results = await asyncio.gather(*(burner.burn(7, 1000, 'same-id-0001') for _ in range(8)))
    assert sum(bool(x.get('duplicate')) for x in results) == 7
    await burner.burn(7, 1000, 'other-id-0001')
    assert (await burner.burn(7, 1000, 'same-id-0001'))['duplicate']
    assert db.users.docs[7]['coins'] == 3000
    assert db.bank.docs['single']['total_emitted'] == 8000


@pytest.mark.asyncio
async def test_receipt_write_failure_rolls_back_all_and_retry_succeeds(setup):
    db, burner = setup
    db.transactions.fail_insert = True
    with pytest.raises(GameError, match='Не удалось сжечь'):
        await burner.burn(7, 1000, 'burn-request-0002')
    assert db.users.docs[7]['coins'] == 5000
    assert db.bank.docs['single']['total_emitted'] == 10000
    assert db.bank.docs['single'].get('burned', 0) == 0
    db.transactions.fail_insert = False
    assert (await burner.burn(7, 1000, 'burn-request-0002'))['amount'] == 1000


@pytest.mark.asyncio
async def test_insufficient_balance_or_emission_aborts_without_partial_burn(setup):
    db, burner = setup
    with pytest.raises(GameError, match='Недостаточно'):
        await burner.burn(7, 5001)
    db.bank.docs['single']['total_emitted'] = 400
    with pytest.raises(GameError, match='Эмиссия меньше'):
        await burner.burn(7, 1000)
    assert db.users.docs[7]['coins'] == 5000
    assert db.bank.docs['single']['total_emitted'] == 400
    assert not db.transactions.docs


@pytest.mark.asyncio
async def test_invalid_request_id_is_rejected(setup):
    db, burner = setup
    with pytest.raises(GameError, match='Неверный запрос'):
        await burner.burn(7, 1000, 'short')
    assert db.users.docs[7]['coins'] == 5000


@pytest.mark.asyncio
async def test_reused_id_with_different_amount_is_rejected(setup):
    db, burner = setup
    await burner.burn(7, 1000, 'burn-request-0004')
    with pytest.raises(GameError, match='другой суммы'):
        await burner.burn(7, 2000, 'burn-request-0004')
    assert db.users.docs[7]['coins'] == 4000
    assert db.bank.docs['single']['total_emitted'] == 9000


@pytest.mark.asyncio
async def test_missing_burn_counter_does_not_invent_a_baseline(setup):
    db, burner = setup
    del db.bank.docs['single']['burned']
    with pytest.raises(GameError):
        await burner.burn(7, 1000, 'burn-request-unknown')
    assert db.users.docs[7]['coins'] == 5000
    assert db.bank.docs['single']['total_emitted'] == 10000
    assert 'burned' not in db.bank.docs['single']
    assert not db.transactions.docs
