"""
📊 Сервис статистики.
"""

import asyncio
from typing import Dict, List, Optional
from datetime import datetime, timezone

from src.core.config import settings
from src.core.constants import TOTAL_EMISSION_CAP
from src.services.emission_service import EmissionService
from src.services.bank_ledger import BankLedger
from src.infra.mongo.client import MongoClient
import logging

logger = logging.getLogger(__name__)


def _to_float(value, default=0):
    """Numeric fallback for cached stats that may contain None/missing fields."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class StatsService:
    """Сервис для сбора статистики."""

    def __init__(self, mongo_client: MongoClient):
        self.mongo_client = mongo_client
        self.db = mongo_client.database
        # Collections
        self.users = self.db.users
        self.bank = self.db.bank  # {_id: "single", coins: X}
        self.transactions = self.db.transactions
        self.tickets = self.db.tickets
        self.emission = EmissionService(mongo_client)
        self.ledger = BankLedger(mongo_client)
        # Simple in-memory cache for admin stats (Redis replacement)
        self._admin_stats_cache = None
        self._cache_timestamp = None
        self._cache_ttl = 60  # seconds
        self._cache_lock = asyncio.Lock()

    async def get_admin_stats(self) -> dict:
        """One refresh per process; one users scan instead of three."""
        async with self._cache_lock:
            now = datetime.now(timezone.utc).timestamp()
            if (self._admin_stats_cache is not None and self._cache_timestamp is not None
                    and now - self._cache_timestamp < self._cache_ttl):
                return self._admin_stats_cache
            try:
                users = await self.users.aggregate([{'$group': {
                    '_id': None, 'count': {'$sum': 1}, 'coins': {'$sum': '$coins'},
                    'messages': {'$sum': '$messages_count'}}}]).to_list(length=1)
                totals = users[0] if users else {}
                bank = await self.bank.find_one({'_id': 'single'}) or {}
                legacy = await self.bank.find_one({'_id': 'main'}) or {}
                circulation = max(0.0, _to_float(totals.get('coins'), 0.0))
                single_balance = max(0.0, _to_float(bank.get('coins'), 0.0))
                legacy_balance = max(0.0, _to_float(legacy.get('balance'), 0.0))
                raw_bank_balance = single_balance + legacy_balance
                raw_total_supply = raw_bank_balance + circulation
                cap = max(0.0, _to_float(bank.get('emission_cap'), TOTAL_EMISSION_CAP))
                # The hard rule is displayed and enforced even if legacy data
                # arrived from an older release: bank + circulation never
                # exceed 10,000,000,000.  Raw values stay available for admin
                # diagnostics.
                if cap:
                    circulation = min(circulation, cap)
                    bank_balance = min(raw_bank_balance, max(0.0, cap - circulation))
                    total_supply = min(cap, bank_balance + circulation)
                else:
                    bank_balance = raw_bank_balance
                    total_supply = raw_total_supply
                emitted_raw = max(0.0, _to_float(bank.get('total_emitted'), total_supply))
                emitted = min(cap, emitted_raw) if cap else emitted_raw
                remaining = max(0.0, cap - emitted)
                percent = min(100.0, emitted / cap * 100.0) if cap else 100.0
                tickets = await self.tickets.count_documents({'burned': False})
                rows = await self.transactions.aggregate([{'$group': {
                    '_id': '$tx_type', 'count': {'$sum': 1},
                    'total_amount': {'$sum': '$coins_change'}}}]).to_list(length=None)
                by_type = {row['_id'] or 'unknown': {
                    'count': row['count'], 'total_amount': row['total_amount']} for row in rows}
                burned_tx = abs(min(0.0, _to_float(
                    by_type.get('burn', {}).get('total_amount'), 0.0)))
                confiscated = abs(min(0.0, _to_float(
                    by_type.get('ban_confiscation', {}).get('total_amount'), 0.0)))
                burned = max(0.0, _to_float(bank.get('burned'), burned_tx))
                stats = {
                    'users': {'total': totals.get('count', 0)},
                    'bank': {'balance': bank_balance,
                             'single_balance': single_balance,
                             'legacy_balance': legacy_balance,
                             'raw_balance': raw_bank_balance,
                             'initial_coins': getattr(settings, 'bank_initial_coins', 1000000.0),
                             'total_emitted': emitted,
                             'total_emitted_raw': emitted_raw,
                             'emission_cap': cap,
                             'emission_remaining': remaining,
                             'emission_percent': round(percent, 2),
                             'total_supply': total_supply,
                             'raw_total_supply': raw_total_supply,
                             'supply_over_cap': raw_total_supply > cap if cap else False,
                             'burned': burned,
                             'confiscated': confiscated,
                             'total_withdrawn': 0},
                    'circulation': circulation,
                    'raw_circulation': max(0.0, _to_float(totals.get('coins'), 0.0)),
                    'tickets': {'active': tickets},
                    'messages': {'total': totals.get('messages', 0)},
                    'transactions': by_type}
                self._admin_stats_cache = stats
                self._cache_timestamp = datetime.now(timezone.utc).timestamp()
                return stats
            except Exception:
                logger.error('Admin statistics refresh failed', exc_info=True)
                # Retain existing API contract, but never cache a failed refresh.
                return {'users': {'total': 0}, 'bank': {'balance': 0, 'single_balance': 0,
                    'legacy_balance': 0, 'raw_balance': 0, 'initial_coins': 0, 'total_emitted': 0,
                    'total_emitted_raw': 0, 'emission_cap': TOTAL_EMISSION_CAP,
                    'emission_remaining': TOTAL_EMISSION_CAP, 'emission_percent': 0,
                    'total_supply': 0, 'raw_total_supply': 0, 'supply_over_cap': False,
                    'burned': 0, 'confiscated': 0, 'total_withdrawn': 0},
                    'circulation': 0, 'raw_circulation': 0, 'tickets': {'active': 0},
                    'messages': {'total': 0}, 'transactions': {}}

    async def get_bank_summary(self) -> dict:
        """Compact /senseibank snapshot for the dojo Mini App.

        Reuses the admin statistics cache: /senseibank and the miner show the
        same emission snapshot instead of scanning users twice per minute.
        """
        stats = await self.get_admin_stats()
        bank = stats.get('bank') or {}
        circulation = max(0.0, _to_float(stats.get('circulation'), 0))
        balance = max(0.0, _to_float(bank.get('balance'), 0))
        cap = max(0.0, _to_float(bank.get('emission_cap'), TOTAL_EMISSION_CAP))
        # Second line of defence: even a stale/mocked admin snapshot cannot
        # return bank + circulation above the hard 10B ceiling.
        if cap:
            circulation = min(circulation, cap)
            balance = min(balance, max(0.0, cap - circulation))
            total_supply = min(cap, balance + circulation)
        else:
            total_supply = max(0.0, balance + circulation)
        users = stats.get('users') or {}
        emitted_raw = max(0.0, _to_float(bank.get('total_emitted'), total_supply))
        emitted = min(cap, emitted_raw) if cap else emitted_raw
        return {
            'bank_balance': round(balance, 2),
            'single_balance': round(max(0.0, _to_float(bank.get('single_balance'), balance)), 2),
            'legacy_balance': round(max(0.0, _to_float(bank.get('legacy_balance'), 0.0)), 2),
            'circulation': round(circulation, 2),
            'total_supply': round(total_supply, 2),
            'total_emitted': round(emitted, 2),
            'emission_cap': round(cap, 2),
            'emission_remaining': round(max(0.0, cap - emitted), 2),
            'emission_percent': round(min(100.0, emitted / cap * 100.0) if cap else 100.0, 2),
            'supply_remaining': round(max(0.0, cap - total_supply), 2),
            'supply_percent': round(min(100.0, total_supply / cap * 100.0) if cap else 100.0, 2),
            'burned': round(max(0.0, _to_float(bank.get('burned'), 0.0)), 2),
            'confiscated': round(max(0.0, _to_float(bank.get('confiscated'), 0.0)), 2),
            'supply_over_cap': bool(bank.get('supply_over_cap')),
            'initial_coins': bank.get('initial_coins', getattr(settings, 'bank_initial_coins', 1000000.0)),
            'users': int(_to_float(users.get('total'), 0)),
        }

    def invalidate(self) -> None:
        """Drop the cached snapshot after a balance-moving action."""
        self._admin_stats_cache = None
        self._cache_timestamp = None

    async def reset_new_season(self) -> dict:
        """Сброс сезона."""
        try:
            # Burn all tickets
            tickets_result = await self.tickets.delete_many({})
            tickets_burned = tickets_result.deleted_count

            # Reset user data (keep katana and other profile settings).
            users_result = await self.users.update_many(
                {},
                {
                    "$set": {
                        "coins": 0,
                        "xp": 0,
                        "level": 1,
                        "messages_count": 0,
                        "daily_streak": 0,
                        "last_daily": None,
                        "achievements_count": 0,
                        "wins": 0,
                        "losses": 0,
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )
            users_reset = users_result.modified_count

            # A new season still may not mint past the lifetime ceiling.  Only
            # the shortfall to the initial bank fill is new emission: existing
            # bank coins were already counted, and excess above the target is
            # burned rather than minted again.
            initial = max(0.0, _to_float(
                getattr(settings, 'bank_initial_coins', 1000000.0), 0.0))
            pool = await self.ledger.balance()
            target = initial
            if pool < initial:
                minted = await self.emission.reserve(initial - pool, 'season_reset')
                if not minted:
                    target = pool
            await self.bank.update_one(
                {"_id": "single"},
                {"$set": {"coins": target}},
                upsert=True,
            )
            # Fold the legacy pool into the canonical account so the next
            # bank read cannot see the old balance twice.
            await self.bank.update_one({"_id": "main"}, {"$set": {"balance": 0.0}})

            # Clear cache
            self._admin_stats_cache = None
            self._cache_timestamp = None

            logger.info(f"Season reset: {tickets_burned} tickets burned, {users_reset} users reset")

            return {
                "success": True,
                "tickets_burned": tickets_burned,
                "users_reset": users_reset,
            }

        except Exception as e:
            logger.error(f"Error resetting season: {e}")
            return {
                "success": False,
                "tickets_burned": 0,
                "users_reset": 0,
            }

    async def reset_sansara(self) -> dict:
        """Полный сброс."""
        return await self.reset_new_season()