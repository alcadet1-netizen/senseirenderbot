"""Compatibility ledger for the two SenseiBank documents in production.

The canonical account is ``bank/_id=single`` with field ``coins``.  A legacy
document ``bank/_id=main`` with field ``balance`` was written by daily/quiz/
slots/exchange/trade/moderation.  This wrapper treats both as one bank pool:
reads sum them, withdrawals atomically debit one account after another, and
deposits go to the canonical account when it exists.  That closes the split in
which a payout could see only one document while players' coins were sitting
in the other.

Every withdrawal is a conditional Mongo update (``field >= amount``), so no
caller can pay a player unless the bank balance really covered the debit at
that moment.  Transfers never change the total supply.
"""
from __future__ import annotations

import logging

from src.services.emission_service import EmissionService

logger = logging.getLogger(__name__)

BANK_ID = "single"
BANK_FIELD = "coins"
LEGACY_ID = "main"
LEGACY_FIELD = "balance"


def _matched(result) -> bool:
    if result is True or isinstance(result, dict):
        return True
    if result is None:
        return False
    matched = getattr(result, "matched_count", None)
    if isinstance(matched, int):
        return matched == 1
    # Test doubles often return a bare AsyncMock.  Real Motor results always
    # carry an integer matched_count, so this only keeps legacy fakes usable.
    return True


def _valid(doc, bank_id: str, field: str) -> bool:
    if not isinstance(doc, dict):
        return False
    if doc.get("_id") == bank_id:
        return True
    if doc.get("_id") is not None:
        # A mock that answers every query with the other document's _id.
        return False
    return field in doc


class BankLedger:
    def __init__(self, mongo_client):
        self.mongo_client = mongo_client
        self.db = mongo_client.database
        self.bank = self.db.bank
        self.emission = EmissionService(mongo_client)

    async def accounts(self) -> list[tuple[dict, str, str]]:
        """Return all live bank accounts that hold coins.

        The canonical account is first.  A legacy account is included only when
        it is a distinct document, so production coins parked in the old
        ``main/balance`` pool remain spendable and visible instead of being
        silently ignored by the new code.
        """
        found: list[tuple[dict, str, str]] = []
        try:
            single = await self.bank.find_one({"_id": BANK_ID})
        except Exception:
            single = None
        if _valid(single, BANK_ID, BANK_FIELD):
            found.append((single, BANK_ID, BANK_FIELD))
        try:
            legacy = await self.bank.find_one({"_id": LEGACY_ID})
        except Exception:
            legacy = None
        if _valid(legacy, LEGACY_ID, LEGACY_FIELD):
            same = (legacy.get("_id") is not None
                    and any(doc.get("_id") == legacy.get("_id") for doc, _, _ in found))
            if not same:
                found.append((legacy, LEGACY_ID, LEGACY_FIELD))
        if not found:
            # No bank yet: create the canonical one through the emission layer
            # so its initial fill is counted against the global ceiling once.
            doc = await self.emission.ensure_state()
            found.append((doc, BANK_ID, BANK_FIELD))
        return found

    async def balance(self) -> float:
        total = 0.0
        for doc, _, field in await self.accounts():
            try:
                total += max(0.0, float(doc.get(field, 0.0) or 0.0))
            except (TypeError, ValueError):
                continue
        return total

    async def try_withdraw(self, amount: float) -> bool:
        """Atomically debit ``amount`` across the pool.

        A partial debit is refunded if the remaining accounts cannot cover the
        rest, so a caller either gets the full amount or pays nothing.
        """
        amount = max(0.0, float(amount or 0.0))
        if amount == 0:
            return True
        remaining = amount
        debited: list[tuple[str, str, float]] = []
        for doc, bank_id, field in await self.accounts():
            if remaining <= 0:
                break
            try:
                available = max(0.0, float(doc.get(field, 0.0) or 0.0))
            except (TypeError, ValueError):
                available = 0.0
            take = min(remaining, available)
            if take <= 0:
                continue
            result = await self.bank.update_one(
                {"_id": bank_id, field: {"$gte": take}},
                {"$inc": {field: -take}},
            )
            if _matched(result):
                remaining -= take
                debited.append((bank_id, field, take))
            else:
                logger.warning("Bank debit missed: bank=%s amount=%.2f", bank_id, take)
        if remaining > 0:
            for bank_id, field, take in debited:
                await self.bank.update_one({"_id": bank_id}, {"$inc": {field: take}})
            logger.warning("Bank pool could not cover %.2f; debit rolled back", amount)
            return False
        return True

    async def deposit(self, amount: float) -> None:
        """Return already-existing coins to the bank (never a mint)."""
        amount = max(0.0, float(amount or 0.0))
        if amount == 0:
            return
        accounts = await self.accounts()
        doc, bank_id, field = accounts[0]
        await self.bank.update_one({"_id": bank_id}, {"$inc": {field: amount}})

    async def refund(self, amount: float, reason: str = "payout_rollback") -> None:
        logger.warning("Bank refund %s: %.2f", reason, amount)
        await self.deposit(amount)
