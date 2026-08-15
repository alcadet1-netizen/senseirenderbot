"""
👤 Сервис пользователей.
"""

from typing import List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from src.core.exceptions import UserNotFoundError
from src.infra.mongo.client import MongoClient
from src.services.level_service import LevelService
import logging

logger = logging.getLogger(__name__)


class UserService:
    """Сервис для работы с пользователями."""

    def __init__(self, mongo_client: MongoClient):
        self.mongo_client = mongo_client
        self.db: AsyncIOMotorDatabase = mongo_client.database
        self.level_service = LevelService()
        # Collections
        self.users = self.db.users
        self.tickets = self.db.tickets
        self.transactions = self.db.transactions
        self.achievements = self.db.user_achievements
        self.daily_claims = self.db.daily_claims

    async def get_profile(self, user_id: int) -> Optional[dict]:
        """Получить профиль пользователя."""
        try:
            user = await self.users.find_one({"id": user_id})
            if not user:
                return None

            # Count tickets
            tickets_count = await self.tickets.count_documents({"user_id": user_id})
            # Count achievements
            achievements_count = await self.achievements.count_documents({"user_id": user_id})

            # Check for special roles based on achievements
            role = None
            if await self.achievements.find_one({"user_id": user_id, "achievement_id": "duel_master"}):
                role = "Ронин"

            level = self.level_service.get_level(user.get("xp", 0))
            level_name = self.level_service.get_level_name(level)
            xp_next = self.level_service.get_xp_for_next_level(level)

            return {
                "id": user.get("id"),
                "username": user.get("username"),
                "first_name": user.get("first_name", ""),
                "last_name": user.get("last_name"),
                "xp": user.get("xp", 0),
                "level": level,
                "level_name": level_name,
                "xp_next": xp_next,
                "coins": user.get("coins", 0.0),
                "tickets": tickets_count,
                "messages": user.get("messages_count", 0),
                "streak": user.get("daily_streak", 0),
                "has_katana": user.get("has_katana", False),
                "katana_length": user.get("katana_length", 0.0),
                "achievements_count": achievements_count,
                "wins": user.get("wins", 0),
                "losses": user.get("losses", 0),
                "is_banned": user.get("is_banned", False),
                "created_at": user.get("created_at"),
                "referrer_id": user.get("referrer_id"),
                "referral_count": user.get("referral_count", 0),
                "role": role,
            }
        except Exception as e:
            logger.error(f"Error in get_profile for user {user_id}: {e}")
            return None

    async def get_or_create(
        self,
        user_id: int,
        username: Optional[str] = None,
        first_name: str = "",
        last_name: Optional[str] = None,
        is_bot: bool = False,
    ) -> dict:
        """Получить или создать пользователя."""
        try:
            user = await self.users.find_one({"id": user_id})
            if user:
                # Update if needed
                update_data = {}
                if username is not None:
                    update_data["username"] = username
                if first_name:
                    update_data["first_name"] = first_name
                if last_name is not None:
                    update_data["last_name"] = last_name
                if update_data:
                    await self.users.update_one({"id": user_id}, {"$set": update_data})
                    user.update(update_data)
                return {"user": user, "created": False}
            else:
                # Create new user
                new_user = {
                    "id": user_id,
                    "username": username,
                    "first_name": first_name,
                    "last_name": last_name,
                    "is_bot": is_bot,
                    "xp": 0,
                    "coins": 0.0,
                    "messages_count": 0,
                    "wins": 0,
                    "losses": 0,
                    "daily_streak": 0,
                    "last_daily": None,
                    "is_banned": False,
                    "ban_reason": None,
                    "is_muted": False,
                    "mute_until": None,
                    "has_katana": False,
                    "katana_length": 0.0,
                    "last_katana_up": None,
                    "referrer_id": None,
                    "referral_count": 0,
                    "can_receive_broadcast": True,
                    "created_at": __import__("datetime").datetime.utcnow(),
                }
                await self.users.insert_one(new_user)
                return {"user": new_user, "created": True}
        except Exception as e:
            logger.error(f"Error in get_or_create for user {user_id}: {e}")
            raise

    async def get_user_by_username(self, username: str) -> Optional[dict]:
        """Получить пользователя по username."""
        try:
            user = await self.users.find_one({"username": username})
            if not user:
                return None
            return {
                "id": user["id"],
                "username": user.get("username"),
                "first_name": user.get("first_name", ""),
                "last_name": user.get("last_name"),
                "is_banned": user.get("is_banned", False),
            }
        except Exception as e:
            logger.error(f"Error in get_user_by_username for username {username}: {e}")
            return None

    async def get_random_user(self) -> Optional[dict]:
        """Получить случайного пользователя."""
        try:
            # Note: This is inefficient for large collections, but okay for now.
            count = await self.users.count_documents({})
            if count == 0:
                return None
            import random
            skip = random.randint(0, count - 1)
            user = await self.users.find().skip(skip).limit(1).next()
            return {
                "id": user["id"],
                "username": user.get("username"),
                "first_name": user.get("first_name", ""),
                "last_name": user.get("last_name"),
            }
        except Exception as e:
            logger.error(f"Error in get_random_user: {e}")
            return None

    async def process_referral(self, user_id: int, referrer_id: int) -> dict:
        """Обработать реферальную систему."""
        try:
            # We'll do this in a transaction-like manner (but MongoDB multi-document transactions are available)
            # For simplicity, we'll do it without transaction and hope for the best.
            # In production, we should use a transaction.

            # 1. Get the user (referral)
            user = await self.users.find_one({"id": user_id})
            if not user:
                return {"success": False, "error": "User not found"}

            # 2. Check if user already has a referrer
            if user.get("referrer_id"):
                return {"success": False, "error": "Already has referrer"}

            # 3. Check self referral
            if user_id == referrer_id:
                return {"success": False, "error": "Self referral"}

            # 4. Get the referrer
            referrer = await self.users.find_one({"id": referrer_id})
            if not referrer:
                return {"success": False, "error": "Referrer not found"}

            # 5. Set the relationship
            await self.users.update_one({"id": user_id}, {"$set": {"referrer_id": referrer_id}})
            await self.users.update_one(
                {"id": referrer_id},
                {"$inc": {"referral_count": 1, "coins": 200.0, "xp": 100}}
            )
            await self.users.update_one(
                {"id": user_id},
                {"$inc": {"coins": 100.0, "xp": 100}}
            )

            # 6. Withdraw from bank (we don't have a bank service yet, so we'll skip for now)
            # TODO: Implement bank withdrawal

            # 7. Create transactions (we'll skip for now, but we can add later)
            # TODO: Create transaction records

            return {
                "success": True,
                "referrer_id": referrer_id,
                "referrer_username": referrer.get("username"),
                "referrer_reward": {"coins": 200.0, "xp": 100},
                "referral_reward": {"coins": 100.0, "xp": 100},
            }
        except Exception as e:
            logger.error(f"Error in process_referral: {e}")
            return {"success": False, "error": str(e)}

    # We'll implement the rest of the methods as needed, but for now, we'll stub them out
    # to avoid breaking the bot. We'll fill them in later.

    async def get_active_users(self, since_hours: int = 720, limit: int = 10000) -> List[dict]:
        """Получить активных пользователей."""
        try:
            # TODO: Implement
            return []
        except Exception as e:
            logger.error(f"Error in get_active_users: {e}")
            return []

    async def get_top_by_xp(self, limit: int = 10) -> List[dict]:
        """Топ по XP."""
        try:
            cursor = self.users.find().sort("xp", -1).limit(limit)
            users = []
            async for user in cursor:
                users.append({
                    "user_id": user["id"],
                    "username": user.get("username") or user.get("first_name") or f"User {user['id']}",
                    "xp": user["xp"],
                    "level": self.level_service.get_level(user["xp"]),
                })
            return users
        except Exception as e:
            logger.error(f"Error in get_top_by_xp: {e}")
            return []

    async def get_top_by_coins(self, limit: int = 10) -> List[dict]:
        """Топ по монетам."""
        try:
            cursor = self.users.find().sort("coins", -1).limit(limit)
            users = []
            async for user in cursor:
                users.append({
                    "user_id": user["id"],
                    "username": user.get("username") or user.get("first_name") or f"User {user['id']}",
                    "coins": user["coins"],
                })
            return users
        except Exception as e:
            logger.error(f"Error in get_top_by_coins: {e}")
            return []

    async def get_top_by_messages(self, limit: int = 10) -> List[dict]:
        """Топ по сообщениям."""
        try:
            cursor = self.users.find().sort("messages_count", -1).limit(limit)
            users = []
            async for user in cursor:
                users.append({
                    "user_id": user["id"],
                    "username": user.get("username") or user.get("first_name") or f"User {user['id']}",
                    "messages": user["messages_count"],
                })
            return users
        except Exception as e:
            logger.error(f"Error in get_top_by_messages: {e}")
            return []

    async def get_top_by_tickets(self, limit: int = 10) -> List[dict]:
        """Топ по билетам."""
        try:
            # We'll need to aggregate
            pipeline = [
                {"$group": {"_id": "$user_id", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
                {"$limit": limit},
                {"$lookup": {
                    "from": "users",
                    "localField": "_id",
                    "foreignField": "id",
                    "as": "user"
                }},
                {"$unwind": "$user"}
            ]
            cursor = self.tickets.aggregate(pipeline)
            tops = []
            async for doc in cursor:
                user = doc["user"]
                tops.append({
                    "user_id": user["id"],
                    "username": user.get("username") or user.get("first_name") or f"User {user['id']}",
                    "tickets": doc["count"],
                })
            return tops
        except Exception as e:
            logger.error(f"Error in get_top_by_tickets: {e}")
            return []

    async def get_ticket_holders_paginated(self, page: int = 0, page_size: int = 20) -> dict:
        """Пагинированный список держателей билетов (без кэша)."""
        try:
            # Get distinct user_ids that have tickets
            pipeline = [
                {"$group": {"_id": "$user_id"}},
                {"$skip": page * page_size},
                {"$limit": page_size},
                {"$lookup": {
                    "from": "users",
                    "localField": "_id",
                    "foreignField": "id",
                    "as": "user"
                }},
                {"$unwind": "$user"}
            ]
            cursor = self.tickets.aggregate(pipeline)
            items = []
            total = await self.tickets.distinct("user_id")
            total = len(total)
            async for doc in cursor:
                user = doc["user"]
                items.append({
                    "user_id": user["id"],
                    "username": user.get("username") or user.get("first_name") or f"User {user['id']}",
                })
            return {"items": items, "total": total}
        except Exception as e:
            logger.error(f"Error in get_ticket_holders_paginated: {e}")
            return {"items": [], "total": 0}

    async def get_top_by_streak(self, limit: int = 10) -> List[dict]:
        """Топ по страйку."""
        try:
            cursor = self.users.find().sort("daily_streak", -1).limit(limit)
            users = []
            async for user in cursor:
                users.append({
                    "user_id": user["id"],
                    "username": user.get("username") or user.get("first_name") or f"User {user['id']}",
                    "streak": user["daily_streak"],
                })
            return users
        except Exception as e:
            logger.error(f"Error in get_top_by_streak: {e}")
            return []

    async def get_top_by_katana(self, limit: int = 10, offset: int = 0) -> dict:
        """Топ по длине катаны."""
        try:
            cursor = self.users.find({"has_katana": True}).sort("katana_length", -1).skip(offset).limit(limit)
            items = []
            total = await self.users.count_documents({"has_katana": True})
            async for user in cursor:
                items.append({
                    "user_id": user["id"],
                    "username": user.get("username") or user.get("first_name") or f"User {user['id']}",
                    "katana_length": user.get("katana_length", 0.0),
                })
            return {"items": items, "total": total}
        except Exception as e:
            logger.error(f"Error in get_top_by_katana: {e}")
            return {"items": [], "total": 0}

    async def get_all_for_broadcast(self) -> List[int]:
        """Получить ID всех пользователей для рассылки."""
        try:
            cursor = self.users.find({"can_receive_broadcast": True}, {"id": 1})
            ids = []
            async for doc in cursor:
                ids.append(doc["id"])
            return ids
        except Exception as e:
            logger.error(f"Error in get_all_for_broadcast: {e}")
            return []

    async def admin_add_katana(self, user_id: int, length: float, admin_id: int) -> dict:
        """Админ: выдать катану."""
        try:
            user = await self.users.find_one({"id": user_id})
            if not user:
                return {"success": False, "error": "Пользователь не найден"}

            await self.users.update_one(
                {"id": user_id},
                {"$set": {"has_katana": True, "katana_length": length}}
            )
            # TODO: Add transaction log

            return {"success": True}
        except Exception as e:
            logger.error(f"Error in admin_add_katana: {e}")
            return {"success": False, "error": str(e)}