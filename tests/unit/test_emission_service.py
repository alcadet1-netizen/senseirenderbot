"""The 10B SenseiCoin ceiling must hold under concurrency and restarts."""
import asyncio
import copy
from types import SimpleNamespace as NS

import pytest

from src.core.constants import TOTAL_EMISSION_CAP
from src.services.emission_service import EmissionService


class Cursor:
    def __init__(self, docs):
        self.docs = copy.deepcopy(docs)

    async def to_list(self, length=None):
        return self.docs if length is None else self.docs[:length]


class Collection:
    def __init__(self, docs=()):
        self.docs = {d["_id"]: copy.deepcopy(d) for d in docs}
        self.lock = asyncio.Lock()

    @staticmethod
    def _match(doc, query):
        for key, expected in query.items():
            actual = doc.get(key)
            if isinstance(expected, dict) and any(k.startswith("$") for k in expected):
                if "$gte" in expected and (actual is None or actual < expected["$gte"]):
                    return False
                if "$lte" in expected and (actual is None or actual > expected["$lte"]):
                    return False
                if "$exists" in expected and (key in doc) != expected["$exists"]:
                    return False
                if "$in" in expected and actual not in expected["$in"]:
                    return False
                if "$ne" in expected and actual == expected["$ne"]:
                    return False
            elif actual != expected:
                return False
        return True

    async def find_one(self, query):
        for doc in self.docs.values():
            if self._match(doc, query):
                return copy.deepcopy(doc)
        return None

    def find(self, query):
        return Cursor([d for d in self.docs.values() if self._match(d, query)])

    async def insert_one(self, doc):
        async with self.lock:
            if doc["_id"] in self.docs:
                from pymongo.errors import DuplicateKeyError
                raise DuplicateKeyError("duplicate _id")
            self.docs[doc["_id"]] = copy.deepcopy(doc)
            return NS(inserted_id=doc["_id"], acknowledged=True)

    async def update_one(self, query, changes, upsert=False):
        async with self.lock:
            for doc in self.docs.values():
                if self._match(doc, query):
                    self._apply(doc, changes)
                    return NS(matched_count=1, modified_count=1, upserted_id=None)
            if not upsert:
                return NS(matched_count=0, modified_count=0, upserted_id=None)
            doc = {k: v for k, v in query.items()
                   if not (isinstance(v, dict) and any(x.startswith("$") for x in v))}
            doc.update(copy.deepcopy(changes.get("$setOnInsert", {})))
            self._apply(doc, changes)
            self.docs[doc["_id"]] = doc
            return NS(matched_count=0, modified_count=1, upserted_id=doc["_id"])

    @staticmethod
    def _apply(doc, changes):
        doc.update(copy.deepcopy(changes.get("$set", {})))
        for key, amount in changes.get("$inc", {}).items():
            doc[key] = doc.get(key, 0) + amount
        for key, value in changes.get("$max", {}).items():
            doc[key] = max(doc.get(key, value), value)


class Users(Collection):
    def aggregate(self, pipeline):
        total = sum(max(0, float(d.get("coins", 0))) for d in self.docs.values())
        return Cursor([{"_id": None, "total": total}])


def service(bank=(), users=()):
    db = NS(bank=Collection(bank), users=Users(users))
    return EmissionService(NS(database=db)), db


@pytest.mark.asyncio
async def test_initial_fill_and_starter_are_counted_once():
    emission, db = service(users=[{"_id": 7, "coins": 500}])
    snapshot = await emission.bootstrap()
    bank = await db.bank.find_one({"_id": "single"})
    assert bank["coins"] == 1_000_000_000.0
    assert snapshot["total_emitted"] == 1_000_000_500.0
    assert snapshot["emission_remaining"] == TOTAL_EMISSION_CAP - 1_000_000_500.0

    assert await emission.reserve_starter(7, 10_000) == 10_000
    assert (await db.bank.find_one({"_id": "single"}))["total_emitted"] == 1_000_010_500.0


@pytest.mark.asyncio
async def test_initial_fill_is_limited_by_remaining_ceiling():
    emission, db = service(users=[{"_id": 1, "coins": 9_500_000_000}])
    snapshot = await emission.bootstrap()
    bank = await db.bank.find_one({"_id": "single"})
    assert bank["coins"] == 500_000_000
    assert snapshot["total_emitted"] == TOTAL_EMISSION_CAP
    assert snapshot["emission_remaining"] == 0

    assert await emission.reserve_starter(2, 10_000) == 0


@pytest.mark.asyncio
async def test_concurrent_reservations_cannot_cross_the_cap():
    cap = 1_000
    emission, db = service(bank=[{
        "_id": "single", "coins": 0, "total_emitted": 500, "burned": 0,
        "emission_cap": cap,
    }])
    emission.cap = cap
    results = await asyncio.gather(*(emission.reserve(100, f"worker:{i}") for i in range(10)))
    assert sum(results) == 5
    assert (await db.bank.find_one({"_id": "single"}))["total_emitted"] == cap


@pytest.mark.asyncio
async def test_restart_reconcile_never_reopens_the_ceiling():
    emission, db = service(bank=[{
        "_id": "single", "coins": 1_000, "total_emitted": 9_999_999_000,
    }])
    before = await emission.bootstrap()
    assert before["total_emitted"] == 9_999_999_000
    assert await emission.reserve(2_000) is False
    after = await emission.bootstrap()
    assert after["total_emitted"] == 9_999_999_000
    assert (await db.bank.find_one({"_id": "single"}))["total_emitted"] == 9_999_999_000


@pytest.mark.asyncio
async def test_existing_supply_above_cap_freezes_new_emission():
    emission, db = service(users=[{"_id": 1, "coins": TOTAL_EMISSION_CAP + 1_000}])
    snapshot = await emission.bootstrap()
    assert snapshot["total_emitted"] == TOTAL_EMISSION_CAP + 1_000
    assert snapshot["emission_frozen"] is True
    assert snapshot["emission_remaining"] == 0
    assert await emission.reserve(1) is False
    assert (await db.bank.find_one({"_id": "single"}))["total_emitted"] == TOTAL_EMISSION_CAP + 1_000


@pytest.mark.asyncio
async def test_release_only_returns_a_failed_reservation():
    emission, db = service(bank=[{
        "_id": "single", "coins": 0, "total_emitted": 1_000, "burned": 0,
    }])
    assert await emission.reserve(500) is True
    assert (await db.bank.find_one({"_id": "single"}))["total_emitted"] == 1_500
    await emission.release(500, "credit_failed")
    assert (await db.bank.find_one({"_id": "single"}))["total_emitted"] == 1_000


@pytest.mark.asyncio
async def test_legacy_bank_is_folded_once_and_never_double_counted():
    emission, db = service(bank=[
        {"_id": "single", "coins": 100.0, "total_emitted": 1_000.0},
        {"_id": "main", "balance": 50.0},
    ])
    await emission.bootstrap()
    canonical = await db.bank.find_one({"_id": "single"})
    legacy = await db.bank.find_one({"_id": "main"})
    assert canonical["coins"] == 150.0
    assert canonical["legacy_fold_id"] == "legacy-bank-fold-v1"
    assert legacy["balance"] == 0.0
    assert canonical["total_emitted"] == 1_000.0

    # A restart must not credit the same legacy balance again.
    await emission.bootstrap()
    canonical = await db.bank.find_one({"_id": "single"})
    assert canonical["coins"] == 150.0
    assert (await db.bank.find_one({"_id": "main"}))["balance"] == 0.0


@pytest.mark.asyncio
async def test_burn_reduces_only_the_lifetime_counter_and_never_goes_negative():
    emission, db = service(bank=[{
        "_id": "single", "coins": 50_000, "total_emitted": 5_000, "burned": 0,
        "emission_cap": TOTAL_EMISSION_CAP,
    }])
    assert await emission.burn(1_000) == 1_000
    bank = await db.bank.find_one({"_id": "single"})
    assert bank["total_emitted"] == 4_000
    assert bank["burned"] == 1_000
    assert bank["coins"] == 50_000  # bank coins are not burned
    assert await emission.burn(9_000) == 4_000
    bank = await db.bank.find_one({"_id": "single"})
    assert bank["total_emitted"] == 0
    assert bank["burned"] == 5_000
    assert await emission.burn(1) == 0


@pytest.mark.asyncio
async def test_burn_never_reopens_lifetime_reservation_capacity():
    emission, db = service(bank=[{'_id': 'single', 'coins': 0, 'total_emitted': 900, 'burned': 100}])
    emission.cap = 1000
    assert await emission.reserve(1) is False
    assert await emission.burn(300) == 300
    assert await emission.reserve(1) is False
    doc = await db.bank.find_one({'_id': 'single'})
    assert doc['total_emitted'] == 600 and doc['burned'] == 400


@pytest.mark.asyncio
async def test_unknown_burn_counter_denies_reservation_without_writing():
    emission, db = service(bank=[{'_id': 'single', 'coins': 50, 'total_emitted': 50}])
    before = copy.deepcopy(db.bank.docs)
    assert await emission.reserve(1) is False
    assert db.bank.docs == before


@pytest.mark.asyncio
async def test_competing_reservations_use_remaining_lifetime_capacity():
    emission, db = service(bank=[{'_id': 'single', 'coins': 0, 'total_emitted': 500, 'burned': 200}])
    emission.cap = 1000
    results = await asyncio.gather(*(emission.reserve(100) for _ in range(10)))
    assert sum(results) == 3
    doc = await db.bank.find_one({'_id': 'single'})
    assert doc['total_emitted'] + doc['burned'] == 1000


@pytest.mark.asyncio
async def test_reservation_retries_after_burn_changes_counters(monkeypatch):
    emission, db = service(bank=[{'_id': 'single', 'coins': 0, 'total_emitted': 700, 'burned': 100}])
    emission.cap = 1000
    original_update = db.bank.update_one
    first = True

    async def interleave(query, changes, upsert=False):
        nonlocal first
        if first and changes.get('$inc', {}).get('total_emitted', 0) > 0:
            first = False
            db.bank.docs['single']['total_emitted'] -= 100
            db.bank.docs['single']['burned'] += 100
        return await original_update(query, changes, upsert=upsert)

    monkeypatch.setattr(db.bank, 'update_one', interleave)
    assert await emission.reserve(200)
    doc = await db.bank.find_one({'_id': 'single'})
    assert doc['total_emitted'] == 800 and doc['burned'] == 200
    assert await emission.reserve(1) is False


@pytest.mark.asyncio
async def test_existing_counter_is_not_reconciled_or_initialized_by_reserve():
    emission, db = service(bank=[{'_id': 'single', 'coins': 10, 'burned': 1}])
    before = copy.deepcopy(db.bank.docs)
    assert not await emission.reserve(1)
    assert db.bank.docs == before


@pytest.mark.asyncio
async def test_restart_preserves_existing_counter_baseline():
    emission, db = service(bank=[{'_id': 'single', 'coins': 100, 'total_emitted': 50, 'burned': 5}],
                           users=[{'_id': 7, 'coins': 100}])
    snapshot = await emission.bootstrap()
    assert snapshot['total_emitted'] == 50
    assert snapshot['lifetime_issued_estimate'] == 55
    assert db.bank.docs['single']['total_emitted'] == 50

@pytest.mark.asyncio
async def test_correction_reserve_keeps_lifetime_ceiling_closed():
    emission, db = service(bank=[{'_id': 'single', 'coins': 0, 'total_emitted': 700,
                                  'burned': 100, 'emission_correction_reserve': 200,
                                  'emission_correction_applied': True}])
    emission.cap = 1000
    assert (await emission.snapshot())['lifetime_issued_estimate'] == 1000
    assert not await emission.reserve(1)
    assert (await db.bank.find_one({'_id': 'single'}))['total_emitted'] == 700


@pytest.mark.asyncio
async def test_missing_correction_reserve_after_correction_fails_closed():
    emission, db = service(bank=[{'_id': 'single', 'coins': 0, 'total_emitted': 700,
                                  'burned': 100, 'emission_correction_applied': True}])
    emission.cap = 1000
    assert (await emission.snapshot())['lifetime_issued_estimate'] is None
    assert not await emission.reserve(1)
