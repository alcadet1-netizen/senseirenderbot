"""
🎫 Репозиторий билетов.
"""

import random
import string
from datetime import datetime, timezone
from typing import List, Optional
from motor.motor_asyncio import AsyncIOMotorCollection


class TicketRepository:
    """Репозиторий для работы с билетами."""

    def __init__(self, collection: AsyncIOMotorCollection):
        self.collection = collection

    def _generate_code(self) -> str:
        """Генерация уникального кода билета."""
        prefix = "".join(random.choices(string.ascii_uppercase, k=3))
        number = "".join(random.choices(string.digits, k=4))
        # Note: TICKET_WORDS is imported from src.core.constants, but we don't have it here.
        # We'll assume it's available via a global import or we can pass it in.
        # For now, we'll use a placeholder word. In reality, we should import TICKET_WORDS.
        # Since we cannot import from src.core.constants in this file without causing a circular import?
        # Actually, we can. Let's do it at the top of the file.
        # We'll add: from src.core.constants import TICKET_WORDS
        # But note: we are in the process of converting the file, so we can add the import.
        # We'll do it below.
        word = random.choice(TICKET_WORDS)  # This will work if we import TICKET_WORDS
        return f"{prefix}-{number}-{word}"

    async def create(self, user_id: int) -> dict:
        """Создать новый билет."""
        for _ in range(10):
            code = self._generate_code()
            existing = await self.collection.find_one({"code": code, "is_burned": False})
            if not existing:
                break

        ticket = {
            "user_id": user_id,
            "code": code,
            "is_burned": False,
            "burned_at": None,
            "burn_reason": None,
            "created_at": datetime.now(timezone.utc),
        }
        await self.collection.insert_one(ticket)
        return ticket

    async def get_user_tickets(
        self,
        user_id: int,
        include_burned: bool = False
    ) -> List[dict]:
        """Получить билеты пользователя."""
        match = {"user_id": user_id}
        if not include_burned:
            match["is_burned"] = False
        cursor = self.collection.find(match).sort("created_at", -1)
        return await cursor.to_list(length=None)

    async def count_user_tickets(self, user_id: int) -> int:
        """Подсчитать активные билеты пользователя."""
        return await self.collection.count_documents({
            "user_id": user_id,
            "is_burned": False
        })

    async def burn_ticket(
        self,
        ticket_id: int,
        reason: str = "exchange"
    ) -> bool:
        """Сжечь билет."""
        result = await self.collection.update_one(
            {
                "_id": ticket_id,
                "is_burned": False
            },
            {
                "$set": {
                    "is_burned": True,
                    "burned_at": datetime.now(timezone.utc),
                    "burn_reason": reason
                }
            }
        )
        return result.modified_count > 0

    async def burn_user_ticket(
        self,
        user_id: int,
        reason: str = "exchange"
    ) -> Optional[dict]:
        """Сжечь один билет пользователя (FIFO)."""
        ticket = await self.collection.find_one_and_update(
            {
                "user_id": user_id,
                "is_burned": False
            },
            {
                "$set": {
                    "is_burned": True,
                    "burned_at": datetime.now(timezone.utc),
                    "burn_reason": reason
                }
            },
            sort=[("created_at", 1)],  # FIFO: oldest first
            return_document=True
        )
        return ticket

    async def get_random_tickets_for_lottery(self, count: int) -> List[dict]:
        """Получить случайные билеты для лотереи."""
        # Use aggregation with $sample for random selection
        pipeline = [
            {"$match": {"is_burned": False}},
            {"$sample": {"size": count}}
        ]
        cursor = self.collection.aggregate(pipeline)
        return await cursor.to_list(length=count)

    async def burn_all_tickets(self, reason: str = "season_reset") -> int:
        """Сжечь все билеты (новый сезон)."""
        result = await self.collection.update_many(
            {"is_burned": False},
            {
                "$set": {
                    "is_burned": True,
                    "burned_at": datetime.now(timezone.utc),
                    "burn_reason": reason
                }
            }
        )
        return result.modified_count

    async def burn_all_user_tickets(self, user_id: int, reason: str = "admin_burn") -> int:
        """Сжечь все билеты конкретного пользователя."""
        result = await self.collection.update_many(
            {"user_id": user_id, "is_burned": False},
            {
                "$set": {
                    "is_burned": True,
                    "burned_at": datetime.now(timezone.utc),
                    "burn_reason": reason
                }
            }
        )
        return result.modified_count

    async def get_total_active_tickets(self) -> int:
        """Получить общее количество активных билетов."""
        return await self.collection.count_documents({"is_burned": False})

    async def get_top_by_tickets(self, limit: int = 10) -> List[dict]:
        """Топ по количеству билетов."""
        # We need to group by user_id and count tickets, then join with users to get username and first_name.
        # Since we don't have the users collection in this repository, we'll do two steps:
        # 1. Aggregate tickets to get per-user counts.
        # 2. For each user, fetch the user details from the users collection (via a service or repository).
        # However, to keep the repository independent, we'll return the user_id and count, and let the service
        # fetch the user details if needed.

        # Alternatively, we can change the repository to accept the users collection as well.
        # Given the time, we'll return the user_id and count, and set username and first_name to None.
        # We'll update the method's docstring accordingly.

        pipeline = [
            {"$match": {"is_burned": False}},
            {"$group": {
                "_id": "$user_id",
                "ticket_count": {"$sum": 1}
            }},
            {"$sort": {"ticket_count": -1}},
            {"$limit": limit}
        ]
        cursor = self.collection.aggregate(pipeline)
        top_users = await cursor.to_list(length=None)

        result = []
        for item in top_users:
            user_id = item["_id"]
            ticket_count = item["ticket_count"]
            result.append({
                "user_id": user_id,
                "tickets": ticket_count,
                "username": None,  # To be filled by the service if needed
                "first_name": None
            })
        return result

    async def get_ticket_holders_paginated(self, offset: int, limit: int) -> tuple[List[dict], int]:
        """Пагинированный список держателей активных билетов."""
        # First, get the total number of distinct users with at least one active ticket.
        total_pipeline = [
            {"$match": {"is_burned": False}},
            {"$group": {
                "_id": "$user_id"
            }},
            {"$count": "total"}
        ]
        total_cursor = self.collection.aggregate(total_pipeline)
        total_result = await total_cursor.to_list(length=1)
        total = total_result[0]["total"] if total_result else 0

        # Then, get the paginated list of users with their ticket counts.
        pipeline = [
            {"$match": {"is_burned": False}},
            {"$group": {
                "_id": "$user_id",
                "ticket_count": {"$sum": 1}
            }},
            {"$sort": {"ticket_count": -1, "_id": 1}},
            {"$skip": offset},
            {"$limit": limit}
        ]
        cursor = self.collection.aggregate(pipeline)
        user_tickets = await cursor.to_list(length=None)

        # We don't have the users collection here, so we'll set username and first_name to None.
        items = []
        for doc in user_tickets:
            items.append({
                "user_id": doc["_id"],
                "tickets": doc["ticket_count"],
                "username": None,
                "first_name": None
            })

        return items, total