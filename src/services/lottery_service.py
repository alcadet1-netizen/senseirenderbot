"""
 Сервис лотереи.
"""

from typing import List, Dict, Optional
import random
from datetime import datetime, timezone

from src.core.config import settings
from src.infra.mongo.client import MongoClient
import logging

logger = logging.getLogger(__name__)


class LotteryService:
    """Сервис для проведения розыгрышей."""

    def __init__(self, mongo_client: MongoClient):
        self.mongo_client = mongo_client
        self.db = mongo_client.database
        # Collections
        self.tickets = self.db.tickets  # For ticket tracking
        self.users = self.db.users

    async def run_lottery(self, winners_count: int) -> List[dict]:
        """Провести розыгрыш."""
        winners = []

        # Get active (not burned) tickets
        active_tickets_cursor = self.tickets.find({"burned": False})
        active_tickets = await active_tickets_cursor.to_list(length=None)

        if not active_tickets:
            return winners

        # Shuffle and pick winners
        random.shuffle(active_tickets)
        winner_tickets = active_tickets[:min(winners_count, len(active_tickets))]

        for ticket_doc in winner_tickets:
            # Mark ticket as burned
            await self.tickets.update_one(
                {"_id": ticket_doc["_id"]},
                {"$set": {
                    "burned": True,
                    "burn_reason": "lottery_win",
                    "burned_at": datetime.now(timezone.utc)
                }}
            )

            # Get user info
            user = await self.users.find_one({"id": ticket_doc["user_id"]})
            if not user:
                continue

            username = user.get("username")
            first_name = user.get("first_name", "")
            last_name = user.get("last_name", "")
            full_name = f"{first_name} {last_name}".strip() or f"User {ticket_doc['user_id']}"

            winners.append({
                "user_id": ticket_doc["user_id"],
                "username": username,
                "full_name": full_name,
                "ticket_code": ticket_doc["code"],
            })

        return winners

    async def admin_add_ticket(self, user_id: int, admin_id: int) -> dict:
        """Админ выдаёт билет пользователю."""
        try:
            # Check if user exists
            user = await self.users.find_one({"id": user_id})
            if not user:
                return {"success": False, "error": "User not found"}

            # Generate ticket ID using atomic counter
            counter_doc = await self.db.counters.find_one_and_update(
                {"_id": "ticket_id"},
                {"$inc": {"seq": 1}},
                upsert=True,
                return_document=True
            )
            next_id = counter_doc["seq"]

            ticket_doc = {
                "_id": next_id,
                "user_id": user_id,
                "code": f"TICKET-{next_id:08d}",
                "created_at": datetime.now(timezone.utc),
                "burned": False
            }
            await self.tickets.insert_one(ticket_doc)

            return {
                "success": True,
                "user_id": user["id"],
                "username": user.get("username") or user.get("first_name") or f"User {user['id']}",
                "ticket_code": ticket_doc["code"],
            }
        except Exception as e:
            logger.error(f"Error in admin_add_ticket for user {user_id}: {e}")
            return {"success": False, "error": "Internal error"}

    async def admin_burn_user_tickets(self, user_id: int, admin_id: int) -> dict:
        """Админ сжигает все билеты пользователя."""
        # Check if user exists
        user = await self.users.find_one({"id": user_id})
        if not user:
            return {"success": False, "error": "User not found"}

        # Burn all user's tickets
        result = await self.tickets.update_many(
            {
                "user_id": user_id,
                "burned": False
            },
            {
                "$set": {
                    "burned": True,
                    "burn_reason": f"admin_burn_by_{admin_id}",
                    "burned_at": datetime.now(timezone.utc)
                }
            }
        )

        burned_count = result.modified_count

        return {
            "success": True,
            "user_id": user.id,
            "username": user.username or user.first_name or f"User {user.id}",
            "burned_count": burned_count
        }

    async def add_ticket(self, user_id: int, source: str = "system") -> dict:
        """Добавить билет пользователю (для системных наград, таких как выигрыш в играх).

        Args:
            user_id: ID пользователя
            source: Источник получения билета (для информации)

        Returns:
            Dict с результатом операции
        """
        # Для системных наград используем специальный системный admin_id = 0
        # В реальной системе можно создать отдельный системный аккаунт
        return await self.admin_add_ticket(user_id, 0)

    async def get_lottery_stats(self) -> dict:
        """Статистика для лотереи."""
        # Total active (not burned) tickets
        total_active = await self.tickets.count_documents({"burned": False})

        # Top holders - users with most active tickets
        pipeline = [
            {"$match": {"burned": False}},
            {"$group": {"_id": "$user_id", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 5}
        ]
        cursor = self.tickets.aggregate(pipeline)
        top_holders_raw = await cursor.to_list(length=None)

        # Get user info for top holders
        top_holders = []
        for holder in top_holders_raw:
            user_id = holder["_id"]
            count = holder["count"]
            user = await self.users.find_one({"id": user_id})
            username = user.get("username") if user else f"User {user_id}"
            top_holders.append({
                "user_id": user_id,
                "username": username,
                "ticket_count": count
            })

        return {
            "total_active_tickets": total_active,
            "top_holders": top_holders,
        }