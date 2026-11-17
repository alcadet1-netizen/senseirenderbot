"""The canonical and legacy bank documents are one spendable pool."""
import asyncio
from types import SimpleNamespace as NS

import pytest

from src.services.bank_ledger import BankLedger
from tests.unit.test_emission_service import Collection, Users


def ledger(bank_docs):
    db = NS(bank=Collection(bank_docs), users=Users())
    return BankLedger(NS(database=db)), db


@pytest.mark.asyncio
async def test_balance_and_withdrawal_span_both_schemas():
    service, db = ledger([
        {"_id": "single", "coins": 100.0, "total_emitted": 1_000},
        {"_id": "main", "balance": 50.0},
    ])
    assert await service.balance() == 150.0
    assert await service.try_withdraw(120.0) is True
    assert (await db.bank.find_one({"_id": "single"}))["coins"] == 0.0
    assert (await db.bank.find_one({"_id": "main"}))["balance"] == 30.0
    assert await service.balance() == 30.0


@pytest.mark.asyncio
async def test_uncovered_withdrawal_rolls_back_every_partial_debit():
    service, db = ledger([
        {"_id": "single", "coins": 10.0, "total_emitted": 1_000},
        {"_id": "main", "balance": 10.0},
    ])
    assert await service.try_withdraw(25.0) is False
    assert (await db.bank.find_one({"_id": "single"}))["coins"] == 10.0
    assert (await db.bank.find_one({"_id": "main"}))["balance"] == 10.0


@pytest.mark.asyncio
async def test_legacy_only_bank_is_still_spendable_and_receives_deposits():
    service, db = ledger([{"_id": "main", "balance": 75.0}])
    assert await service.balance() == 75.0
    assert await service.try_withdraw(50.0) is True
    await service.deposit(5.0)
    assert (await db.bank.find_one({"_id": "main"}))["balance"] == 30.0


@pytest.mark.asyncio
async def test_concurrent_withdrawals_cannot_spend_the_same_coins_twice():
    service, db = ledger([
        {"_id": "single", "coins": 100.0, "total_emitted": 1_000},
    ])
    results = await asyncio.gather(*(service.try_withdraw(30.0) for _ in range(6)))
    assert sum(bool(value) for value in results) == 3
    assert (await db.bank.find_one({"_id": "single"}))["coins"] == 10.0
    assert (await db.bank.find_one({"_id": "single"}))["total_emitted"] == 1_000
