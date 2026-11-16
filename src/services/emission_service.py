"""One hard, race-safe ceiling for every newly created SenseiCoin.

SenseiCoin has two kinds of money movements:

* transfers between the bank and players (rewards, mining, purchases) — these
  never change the total supply;
* new coins: the initial SenseiBank fill and registration starter kits.

Only the second kind is emission.  The counter lives in the canonical bank
document ``bank/_id=single`` (field ``total_emitted``).  Reserving coins is a
single conditional ``$inc``: Mongo increments only while the stored counter is
at or below ``cap - amount``, so concurrent workers cannot pass the ceiling.
Nothing in the bot should add coins to a user without either reserving them
here (starter) or withdrawing the same amount from the bank (all payouts).
"""
from __future__ import annotations

import inspect
import logging
from datetime import datetime, timezone

from pymongo.errors import DuplicateKeyError

from src.core.config import settings
from src.core.constants import TOTAL_EMISSION_CAP

logger = logging.getLogger(__name__)

BANK_ID = "single"
LEGACY_BANK_ID = "main"
FOLD_ID = "legacy-bank-fold-v1"


def _num(value, default: float = 0.0) -> float:
    """Coerce legacy Mongo values (None, Decimal128, int) to float."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _matched(result) -> bool:
    """Return True only when Mongo reported a match.

    Real Motor results always carry an integer ``matched_count``.  A bare test
    double that has no integer count is treated as a match; an explicit
    ``matched_count=0`` (used by tests for races) still fails.
    """
    if result is True or isinstance(result, dict):
        return True
    if result is None:
        return False
    matched = getattr(result, "matched_count", None)
    if isinstance(matched, int):
        return matched == 1
    return True


class EmissionService:
    """Reserve starter/bank emission against one global counter."""

    def __init__(self, mongo_client, cap: float = TOTAL_EMISSION_CAP):
        self.mongo_client = mongo_client
        self.db = mongo_client.database
        self.bank = self.db.bank
        self.users = self.db.users
        self.cap = max(0.0, _num(cap, TOTAL_EMISSION_CAP))

    async def _observed_supply(self) -> float:
        """Best-effort supply snapshot used only to initialise/reconcile.

        It deliberately counts both bank schemas that exist in production:
        canonical ``single.coins`` and the legacy ``main.balance``.  Player
        balances are summed only if positive; negative legacy balances must not
        hide coins that really are in circulation.
        """
        total = 0.0
        try:
            cursor = self.users.aggregate([
                {"$match": {"coins": {"$gt": 0}}},
                {"$group": {"_id": None, "total": {"$sum": "$coins"}}},
            ])
            # Motor returns a cursor synchronously; some test doubles expose an
            # async factory instead.  Support both without leaking coroutines.
            if inspect.isawaitable(cursor):
                cursor = await cursor
            rows = await cursor.to_list(length=1)
            if isinstance(rows, (list, tuple)) and rows:
                first = rows[0]
                if isinstance(first, dict):
                    total += max(0.0, _num(first.get("total"), 0.0))
        except Exception:
            # Older fakes/collections may not implement aggregate.  The
            # startup reconcile will still see the bank balance and retry on
            # the next real deployment; never fail a user registration here.
            logger.debug("Emission supply: users aggregate unavailable", exc_info=True)

        docs = []
        try:
            cursor = self.bank.find({"_id": {"$in": [BANK_ID, LEGACY_BANK_ID]}})
            if inspect.isawaitable(cursor):
                cursor = await cursor
            docs = await cursor.to_list(length=2)
        except Exception:
            docs = []
        if not isinstance(docs, (list, tuple)):
            docs = []
        for bank_id in (BANK_ID, LEGACY_BANK_ID):
            if any(isinstance(d, dict) and d.get("_id") == bank_id for d in docs):
                continue
            try:
                doc = await self.bank.find_one({"_id": bank_id})
            except Exception:
                doc = None
            if isinstance(doc, dict):
                docs.append(doc)

        for doc in docs:
            if not isinstance(doc, dict):
                continue
            if doc.get("_id") == BANK_ID:
                total += max(0.0, _num(doc.get("coins"), 0.0))
            elif doc.get("_id") == LEGACY_BANK_ID:
                total += max(0.0, _num(doc.get("balance"), 0.0))
        return max(0.0, total)

    async def ensure_state(self, *, force_reconcile: bool = False) -> dict:
        """Create the canonical bank/counter once and keep it monotonic.

        The counter may only move up to the observed supply, never down.  That
        makes a lost/reset ``total_emitted`` fail closed instead of handing out
        a fresh cap.  Normal calls return the existing document after a single
        read and do not scan players.
        """
        doc = await self.bank.find_one({"_id": BANK_ID})
        if doc is not None and "total_emitted" in doc and not force_reconcile:
            return doc

        observed = await self._observed_supply()
        now = datetime.now(timezone.utc)

        if doc is None:
            initial = max(0.0, _num(settings.bank_initial_coins, 0.0))
            # The initial bank fill is emission too.  If starter kits already
            # consumed part of the ceiling, create only the remainder.
            allowed = min(initial, max(0.0, self.cap - observed))
            try:
                await self.bank.update_one(
                    {"_id": BANK_ID},
                    {"$setOnInsert": {
                        "coins": allowed,
                        "total_emitted": observed + allowed,
                        "emission_cap": self.cap,
                        "emission_reconciled_at": now,
                    }},
                    upsert=True,
                )
            except DuplicateKeyError:
                pass
            doc = await self.bank.find_one({"_id": BANK_ID})
            if doc is not None and "total_emitted" in doc:
                return doc
            if doc is None:
                # Extremely defensive: a fake/unsupported collection could not
                # create the document.  Return a coherent, non-minting view.
                return {"_id": BANK_ID, "coins": 0.0, "total_emitted": observed,
                        "emission_cap": self.cap}

        stored = _num(doc.get("total_emitted"), -1.0)
        if stored < 0:
            stored = 0.0
        total = max(stored, observed)
        # $max is atomic and monotonic: a stale or concurrent reconcile can
        # never lower the counter and re-open part of the ceiling.
        update = {"$max": {"total_emitted": total},
                  "$set": {
                      "emission_cap": self.cap,
                      "emission_reconciled_at": now,
                  }}
        if total > self.cap:
            update["$set"]["emission_frozen"] = True
            logger.error(
                "SenseiCoin emission is already above the hard cap: %.2f > %.2f",
                total, self.cap,
            )
        try:
            await self.bank.update_one({"_id": BANK_ID}, update)
        except Exception:
            logger.exception("Could not persist emission reconcile state")
        doc = dict(doc)
        doc.update(update["$set"])
        doc["total_emitted"] = max(stored, _num(doc.get("total_emitted"), 0.0))
        return doc

    async def fold_legacy_bank(self) -> float:
        """Move the legacy ``main.balance`` pool into the canonical account.

        Payouts that still use a Mongo transaction (Stars, paid hedgehog,
        referrals, comment campaigns) can only see ``single.coins``.  The fold
        is idempotent: a marker document plus a conditional ``$inc`` keyed by
        that marker make a retry after a crash safe — the canonical credit is
        applied at most once, and the legacy balance is zeroed only after it.

        Returns the amount folded (0 when there was nothing to do).
        """
        try:
            legacy = await self.bank.find_one({"_id": LEGACY_BANK_ID})
            amount = max(0.0, _num((legacy or {}).get("balance"), 0.0))
            if amount <= 0:
                return 0.0
            marker = await self.bank.find_one({"_id": FOLD_ID})
            if marker is None:
                try:
                    await self.bank.insert_one({
                        "_id": FOLD_ID, "amount": amount, "status": "pending",
                        "created_at": datetime.now(timezone.utc),
                    })
                except DuplicateKeyError:
                    pass
                marker = await self.bank.find_one({"_id": FOLD_ID})
            elif marker.get("status") == "done":
                # A previous deployment already folded its pool.  Do not touch
                # anything that arrived afterwards without a new marker.
                return 0.0
            amount = max(0.0, _num((marker or {}).get("amount"), amount))
            if amount <= 0:
                return 0.0
            credit = await self.bank.update_one(
                {"_id": BANK_ID, "legacy_fold_id": {"$ne": FOLD_ID}},
                {"$inc": {"coins": amount},
                 "$set": {"legacy_fold_id": FOLD_ID,
                          "legacy_fold_at": datetime.now(timezone.utc)}},
            )
            if not _matched(credit):
                canonical = await self.bank.find_one({"_id": BANK_ID})
                if not canonical or canonical.get("legacy_fold_id") != FOLD_ID:
                    # Never delete the legacy pool unless the canonical credit
                    # is visible (a fake/partial collection must not lose it).
                    logger.error("Legacy bank fold skipped: canonical credit missing")
                    return 0.0
            await self.bank.update_one(
                {"_id": LEGACY_BANK_ID},
                {"$set": {"balance": 0.0}},
            )
            await self.bank.update_one(
                {"_id": FOLD_ID},
                {"$set": {"status": "done", "folded_at": datetime.now(timezone.utc)}},
            )
            logger.info("Legacy bank folded into canonical account: %.2f", amount)
            return amount
        except Exception:
            logger.exception("Legacy bank fold failed; canonical/legacy pool still usable")
            return 0.0

    async def bootstrap(self) -> dict:
        """Startup reconcile: never re-mint, never lower the cumulative total."""
        doc = await self.ensure_state(force_reconcile=True)
        await self.fold_legacy_bank()
        doc = await self.bank.find_one({"_id": BANK_ID}) or doc
        snapshot = self.snapshot_from_doc(doc)
        logger.info(
            "SenseiCoin emission: emitted=%.2f cap=%.2f remaining=%.2f",
            snapshot["total_emitted"], snapshot["emission_cap"],
            snapshot["emission_remaining"],
        )
        return snapshot

    async def reserve(self, amount: float, reason: str = "mint") -> bool:
        """Atomically reserve ``amount`` of the global ceiling.

        Returns False when the ceiling would be exceeded (including when the
        bank was frozen after an already-over-cap reconcile).  Callers must not
        credit the user when this returns False.
        """
        amount = _num(amount, 0.0)
        if amount <= 0:
            return True
        doc = await self.ensure_state()
        if doc.get("emission_frozen") or _num(doc.get("total_emitted")) > self.cap:
            logger.error("Emission reserve denied (frozen/over cap): reason=%s amount=%.2f",
                         reason, amount)
            return False
        limit = self.cap - amount
        if limit < 0:
            return False
        try:
            result = await self.bank.update_one(
                {"_id": BANK_ID, "total_emitted": {"$lte": limit}},
                {"$inc": {"total_emitted": amount},
                 "$set": {"emission_cap": self.cap,
                          "emission_updated_at": datetime.now(timezone.utc)}},
            )
        except Exception:
            logger.exception("Emission reserve failed: reason=%s amount=%.2f", reason, amount)
            return False
        if not _matched(result):
            logger.warning(
                "Emission cap reached: reason=%s amount=%.2f cap=%.2f",
                reason, amount, self.cap,
            )
            return False
        logger.info("Emission reserved: reason=%s amount=%.2f", reason, amount)
        return True

    async def release(self, amount: float, reason: str = "rollback") -> None:
        """Return a reservation whose credit failed.

        Only reserved-but-not-delivered amounts may be released.  This is not
        used to undo a successful player credit.
        """
        amount = _num(amount, 0.0)
        if amount <= 0:
            return
        try:
            await self.bank.update_one(
                {"_id": BANK_ID, "total_emitted": {"$gte": amount}},
                {"$inc": {"total_emitted": -amount},
                 "$set": {"emission_updated_at": datetime.now(timezone.utc)}},
            )
            logger.warning("Emission released: reason=%s amount=%.2f", reason, amount)
        except Exception:
            logger.exception("Emission release failed: reason=%s amounts=%.2f", reason, amount)

    async def reserve_starter(self, user_id: int, amount: float) -> float:
        """Return the starter amount actually allowed by the global ceiling."""
        amount = max(0.0, _num(amount, 0.0))
        if await self.reserve(amount, f"starter:{user_id}"):
            return amount
        logger.warning("Starter kit skipped for user=%s: emission ceiling reached", user_id)
        return 0.0

    def snapshot_from_doc(self, doc: dict | None) -> dict:
        bank_doc = doc or {}
        emitted = max(0.0, _num(bank_doc.get("total_emitted"), 0.0))
        cap = max(0.0, _num(bank_doc.get("emission_cap"), self.cap))
        remaining = max(0.0, cap - emitted)
        percent = min(100.0, emitted / cap * 100.0) if cap else 100.0
        return {
            "total_emitted": round(emitted, 2),
            "emission_cap": round(cap, 2),
            "emission_remaining": round(remaining, 2),
            "emission_percent": round(percent, 2),
            "emission_frozen": bool(bank_doc.get("emission_frozen")) or emitted >= cap,
        }

    async def snapshot(self, *, create: bool = True) -> dict:
        """Read-only view for /senseibank and the miner bank tab."""
        if create:
            doc = await self.ensure_state()
        else:
            doc = await self.bank.find_one({"_id": BANK_ID})
        return self.snapshot_from_doc(doc)
