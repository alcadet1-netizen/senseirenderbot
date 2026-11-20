"""
📊 Сервис статистики.
"""

import asyncio
from typing import Dict, List, Optional
from datetime import datetime, timezone

from src.core.config import settings
from src.core.constants import TOTAL_EMISSION_CAP
from src.services.emission_service import EmissionService
from src.services.emission_watch import _amount, correction_reserve
from src.services.bank_ledger import BankLedger
from src.services.referral_economy import transaction
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
                stats = await transaction(self.mongo_client, self._read_admin_stats)
                self._admin_stats_cache = stats
                self._cache_timestamp = datetime.now(timezone.utc).timestamp()
                stats['snapshot_at'] = self._cache_timestamp
                return stats
            except Exception:
                logger.error('Admin statistics refresh failed', exc_info=True)
                # Never present a database error as a real zero balance.
                raise

    async def _read_admin_stats(self, session) -> dict:
        """Read all component balances from one MongoDB snapshot."""
        users = await self.users.aggregate([{'$group': {
            '_id': None, 'count': {'$sum': 1},
            'holders': {'$sum': {'$cond': [
                {'$and': [{'$isNumber': '$coins'}, {'$gt': ['$coins', 0]}]},
                1, 0]}},
            'coins': {'$sum': '$coins'},
            'messages': {'$sum': '$messages_count'}}}], session=session).to_list(length=1)
        totals = users[0] if users else {}
        bank = await self.bank.find_one({'_id': 'single'}, session=session) or {}
        legacy = await self.bank.find_one({'_id': 'main'}, session=session) or {}
        circulation = max(0.0, _to_float(totals.get('coins'), 0.0))
        single_balance = max(0.0, _to_float(bank.get('coins'), 0.0))
        legacy_balance = max(0.0, _to_float(legacy.get('balance'), 0.0))
        raw_bank_balance = single_balance + legacy_balance
        # Reserved/decided stakes are no longer in player balances, but still
        # exist. Settled stakes were credited atomically and must not be counted.
        valid_bet = {'$and': [{'$isNumber': '$bet'}, {'$gte': ['$bet', 0]}]}
        escrow_rows = await self.db.duel_escrows.aggregate([
            {'$match': {'state': {'$in': ['reserved', 'decided']}}},
            {'$group': {'_id': None,
                'bets': {'$sum': {'$cond': [valid_bet, '$bet', 0]}},
                'invalid': {'$sum': {'$cond': [valid_bet, 0, 1]}}}},
        ], session=session).to_list(length=1)
        escrow_row = escrow_rows[0] if escrow_rows else {'bets': 0, 'invalid': 0}
        bets = _amount(escrow_row.get('bets'))
        escrow = float(bets * 2) if bets is not None and not escrow_row.get('invalid') else None
        raw_total_supply = raw_bank_balance + circulation + escrow if escrow is not None else None
        cap = max(0.0, _to_float(bank.get('emission_cap'), TOTAL_EMISSION_CAP))
        # Never hide historical inconsistencies by clipping real balances.
        bank_balance = raw_bank_balance
        total_supply = raw_total_supply
        emitted_counter = _amount(bank.get('total_emitted'))
        emitted_raw = float(emitted_counter) if emitted_counter is not None else None
        emitted = emitted_raw
        current_counter, burn_counter = _amount(bank.get('total_emitted')), _amount(bank.get('burned'))
        reserve = correction_reserve(bank)
        lifetime = float(current_counter + burn_counter + reserve) if current_counter is not None and burn_counter is not None and reserve is not None else None
        remaining = max(0.0, cap - lifetime) if lifetime is not None else None
        percent = min(100.0, lifetime / cap * 100.0) if lifetime is not None and cap else None
        tickets = await self.tickets.count_documents({'burned': False}, session=session)
        rows = await self.transactions.aggregate([{'$group': {
            '_id': '$tx_type', 'count': {'$sum': 1},
            'total_amount': {'$sum': '$coins_change'}}}], session=session).to_list(length=None)
        by_type = {row['_id'] or 'unknown': {
            'count': row['count'], 'total_amount': row['total_amount']} for row in rows}
        confiscated = abs(min(0.0, _to_float(
            by_type.get('ban_confiscation', {}).get('total_amount'), 0.0)))
        burned_value = _amount(bank.get('burned'))
        burned = float(burned_value) if burned_value is not None else None
        stats = {
            'users': {'total': totals.get('count', 0), 'holders': totals.get('holders', 0)},
            'bank': {'balance': bank_balance,
                     'single_balance': single_balance,
                     'legacy_balance': legacy_balance,
                     'raw_balance': raw_bank_balance,
                     'initial_coins': getattr(settings, 'bank_initial_coins', 1000000.0),
                     'total_emitted': emitted,
                     'total_emitted_raw': emitted_raw,
                     'emission_cap': cap,
                     'emission_remaining': remaining,
                     'emission_percent': round(percent, 2) if percent is not None else None,
                     'lifetime_issued_estimate': lifetime,
                     'duel_escrow': escrow,
                     'total_supply': total_supply,
                     'raw_total_supply': raw_total_supply,
                     'supply_over_cap': raw_total_supply > cap if cap and raw_total_supply is not None else False,
                     'burned': burned,
                     'confiscated': confiscated,
                     'total_withdrawn': 0},
            'circulation': circulation,
            'raw_circulation': max(0.0, _to_float(totals.get('coins'), 0.0)),
            'tickets': {'active': tickets},
            'messages': {'total': totals.get('messages', 0)},
            'transactions': by_type}
        return stats

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
        escrow_value = _amount(bank.get('duel_escrow', 0))
        escrow = float(escrow_value) if escrow_value is not None else None
        total_supply = balance + circulation + escrow if escrow is not None else None
        users = stats.get('users') or {}
        current_counter = _amount(bank.get('total_emitted_raw', bank.get('total_emitted')))
        emitted = float(current_counter) if current_counter is not None else None
        return {
            'snapshot_at': stats.get('snapshot_at'),
            'bank_balance': round(balance, 2),
            'single_balance': round(max(0.0, _to_float(bank.get('single_balance'), balance)), 2),
            'legacy_balance': round(max(0.0, _to_float(bank.get('legacy_balance'), 0.0)), 2),
            'circulation': round(circulation, 2),
            'duel_escrow': round(escrow, 2) if escrow is not None else None,
            'total_supply': round(total_supply, 2) if total_supply is not None else None,
            'total_emitted': round(emitted, 2) if emitted is not None else None,
            'emission_cap': round(cap, 2),
            'emission_remaining': bank.get('emission_remaining'),
            'emission_percent': bank.get('emission_percent'),
            'lifetime_issued_estimate': bank.get('lifetime_issued_estimate'),
            'supply_remaining': round(max(0.0, cap - total_supply), 2) if total_supply is not None else None,
            'supply_percent': round(min(100.0, total_supply / cap * 100.0) if cap else 100.0, 2) if total_supply is not None else None,
            'burned': round(float(_amount(bank.get('burned'))), 2) if _amount(bank.get('burned')) is not None else None,
            'confiscated': round(max(0.0, _to_float(bank.get('confiscated'), 0.0)), 2),
            'supply_over_cap': bool(bank.get('supply_over_cap')) or bool(cap and total_supply is not None and total_supply > cap),
            'initial_coins': bank.get('initial_coins', getattr(settings, 'bank_initial_coins', 1000000.0)),
            'users': int(_to_float(users.get('total'), 0)),
            'holders': int(_to_float(users.get('holders'), 0)),
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