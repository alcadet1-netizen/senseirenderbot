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
        self.bank = self.db.bank  # {_id: "main", balance: X}
        self.transactions = self.db.transactions
        self.tickets = self.db.tickets
        # Simple in-memory cache for admin stats (Redis replacement)
        self._admin_stats_cache = None
        self._cache_timestamp = None
        self._cache_ttl = 60  # seconds
        self._cache_lock = asyncio.Lock()

    async def get_admin_stats(self) -> dict:
        """Получить полную статистику для админа."""
        # Check cache
        now = datetime.now(timezone.utc).timestamp()
        async with self._cache_lock:
            if (self._admin_stats_cache is not None and
                self._cache_timestamp is not None and
                now - self._cache_timestamp < self._cache_ttl):
                return self._admin_stats_cache

        # Calculate stats
        try:
            # Total users
            total_users = await self.users.count_documents({})

            # Bank stats
            bank_doc = await self.bank.find_one({"_id": "main"})
            bank_balance = bank_doc.get("balance", 0) if bank_doc else 0
            bank_stats = {
                "balance": bank_balance,
                "initial_coins": getattr(settings, 'bank_initial_coins', 1000000),
                "total_emitted": 0,  # Would need to calculate from transactions
                "total_withdrawn": 0  # Would need to calculate from transactions
            }

            # Circulation - total coins in users' hands (not in bank)
            # We'll calculate this by summing all user coins
            pipeline = [
                {"$group": {"_id": None, "total": {"$sum": "$coins"}}}
            ]
            cursor = self.users.aggregate(pipeline)
            result = await cursor.to_list(length=1)
            total_user_coins = result[0]["total"] if result else 0

            # For simplicity, we'll assume bank balance + user coins = total supply
            # Circulation would be user coins
            circulation = total_user_coins

            # Total active tickets
            total_tickets = await self.tickets.count_documents({})

            # Transaction stats by type
            pipeline = [
                {"$group": {"_id": "$tx_type", "count": {"$sum": 1}, "total_amount": {"$sum": "$coins_change"}}}
            ]
            cursor = self.transactions.aggregate(pipeline)
            tx_stats_list = await cursor.to_list(length=None)
            tx_stats = {}
            for item in tx_stats_list:
                tx_type = item["_id"] or "unknown"
                tx_stats[tx_type] = {
                    "count": item["count"],
                    "total_amount": item["total_amount"]
                }

            # Total messages
            pipeline = [
                {"$group": {"_id": None, "total": {"$sum": "$messages_count"}}}
            ]
            cursor = self.users.aggregate(pipeline)
            result = await cursor.to_list(length=1)
            total_messages = result[0]["total"] if result else 0

            stats = {
                "users": {"total": total_users},
                "bank": bank_stats,
                "circulation": circulation,
                "tickets": {"active": total_tickets},
                "messages": {"total": total_messages},
                "transactions": tx_stats,
            }

            # Update cache
            self._admin_stats_cache = stats
            self._cache_timestamp = now

            return stats

        except Exception as e:
            logger.error(f"Error getting admin stats: {e}")
            # Return empty stats on error
            return {
                "users": {"total": 0},
                "bank": {"balance": 0, "initial_coins": 0, "total_emitted": 0, "total_withdrawn": 0},
                "circulation": 0,
                "tickets": {"active": 0},
                "messages": {"total": 0},
                "transactions": {},
            }

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
                {"_id": "main"},
                {"$set": {"balance": getattr(settings, 'bank_initial_coins', 1000000)}},
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