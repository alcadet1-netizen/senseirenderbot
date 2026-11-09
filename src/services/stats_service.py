"""
📊 Сервис статистики.
"""

import asyncio
from typing import Dict, List, Optional
from datetime import datetime, timezone

from src.core.config import settings
from src.infra.mongo.client import MongoClient
import logging

logger = logging.getLogger(__name__)


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
                tickets = await self.tickets.count_documents({'burned': False})
                rows = await self.transactions.aggregate([{'$group': {
                    '_id': '$tx_type', 'count': {'$sum': 1},
                    'total_amount': {'$sum': '$coins_change'}}}]).to_list(length=None)
                stats = {
                    'users': {'total': totals.get('count', 0)},
                    'bank': {'balance': bank.get('coins', 0.0),
                             'initial_coins': getattr(settings, 'bank_initial_coins', 1000000.0),
                             'total_emitted': 0, 'total_withdrawn': 0},
                    'circulation': totals.get('coins', 0),
                    'tickets': {'active': tickets},
                    'messages': {'total': totals.get('messages', 0)},
                    'transactions': {row['_id'] or 'unknown': {
                        'count': row['count'], 'total_amount': row['total_amount']} for row in rows}}
                self._admin_stats_cache = stats
                self._cache_timestamp = datetime.now(timezone.utc).timestamp()
                return stats
            except Exception:
                logger.error('Admin statistics refresh failed', exc_info=True)
                # Retain existing API contract, but never cache a failed refresh.
                return {'users': {'total': 0}, 'bank': {'balance': 0, 'initial_coins': 0,
                    'total_emitted': 0, 'total_withdrawn': 0}, 'circulation': 0,
                    'tickets': {'active': 0}, 'messages': {'total': 0}, 'transactions': {}}

    async def reset_new_season(self) -> dict:
        """Сброс сезона."""
        try:
            # Burn all tickets
            tickets_result = await self.tickets.delete_many({})
            tickets_burned = tickets_result.deleted_count

            # Reset user data (keep katana and possibly other settings)
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
                    },
                    # Keep has_katana and katana_length as requested
                    # "$set": {"has_katana": "$has_katana", "katana_length": "$katana_length"}  # This doesn't work, need to keep existing values
                }
            )
            # Actually, to keep existing values, we don't set them at all
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

            # Reset bank balance
            await self.bank.update_one(
                {"_id": "single"},
                {"$set": {"coins": getattr(settings, 'bank_initial_coins', 1000000.0)}},
                upsert=True
            )

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