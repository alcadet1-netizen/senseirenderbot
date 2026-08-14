"""
�������������������������🛡��️ Сервис модерации.
"""

from typing import List, Optional
from datetime import datetime, timedelta, timezone
import logging

from src.core.config import settings
from src.infra.mongo.client import MongoClient

logger = logging.getLogger(__name__)


class ModerationService:
    """Сервис для модерации пользователей."""

    def __init__(self, mongo_client: MongoClient):
        self.mongo_client = mongo_client
        self.db = mongo_client.database
        # Collections
        self.users = self.db.users
        self.transactions = self.db.transactions
        self.bank = self.db.bank  # {_id: "main", balance: X}
        self.muted_users = self.db.muted_users  # For muted users
        # Cache for quick mute checks: user_id -> muted_until (None for permanent)
        self._muted_cache: dict[int, Optional[datetime]] = {}

    async def load_muted_users_cache(self):
        """Загрузить кэш замьюченных пользователей при старте."""
        cursor = self.muted_users.find({})
        self._muted_cache = {
            doc["user_id"]: doc.get("muted_until")
            async for doc in cursor
        }

    async def handle_user_left(self, user_id: int) -> dict:
        """Обработать выход пользователя (автобан и конфискация)."""
        return await self.ban_user(
            user_id=user_id,
            reason="Выход из чата (AutoBan)",
            confiscate_coins=True
        )

    async def ban_user(
        self,
        user_id: int,
        reason: str = "Нарушение правил",
        confiscate_coins: bool = True
    ) -> dict:
        """Забанить пользователя."""
        # Get user
        user = await self.users.find_one({"id": user_id})
        if not user:
            return {"success": False, "error": "User not found"}

        if user.get("is_banned"):
            return {"success": False, "error": "Already banned"}

        confiscated = 0.0
        if confiscate_coins:
            user_coins = user.get("coins", 0)
            if user_coins > 0:
                confiscated = user_coins
                # Set user coins to 0
                await self.users.update_one(
                    {"id": user_id},
                    {"$set": {"coins": 0}}
                )
                # Deposit to bank
                await self.bank.update_one(
                    {"_id": "main"},
                    {"$inc": {"balance": confiscated}},
                    upsert=True
                )
                # Create transaction record
                tx_doc = {
                    "user_id": user_id,
                    "tx_type": "ban_confiscation",
                    "coins_change": -confiscated,
                    "description": f"Ban confiscation: {reason}",
                    "created_at": datetime.now(timezone.utc),
                }
                await self.transactions.insert_one(tx_doc)

        # Ban user
        await self.users.update_one(
            {"id": user_id},
            {"$set": {
                "is_banned": True,
                "ban_reason": reason,
                "updated_at": datetime.now(timezone.utc)
            }}
        )

        logger.info(f"User {user_id} banned. Reason: {reason}. Confiscated: {confiscated}")

        return {
            "success": True,
            "user_id": user.id,
            "username": user.get("username") or user.get("first_name"),
            "reason": reason,
            "confiscated": confiscated,
        }

    async def unban_user(self, user_id: int) -> dict:
        """Разбанить пользователя."""
        result = await self.users.update_one(
            {"id": user_id, "is_banned": True},
            {"$set": {
                "is_banned": False,
                "ban_reason": None,
                "updated_at": datetime.now(timezone.utc)
            }}
        )

        if result.matched_count == 0:
            return {"success": False, "error": "User not found or not banned"}

        logger.info(f"User {user_id} unbanned")
        return {"success": True, "user_id": user_id}

    async def get_banned_users(self) -> List[dict]:
        """Получить список забаненных."""
        cursor = self.users.find({"is_banned": True})
        users = await cursor.to_list(length=None)

        return [
            {
                "user_id": u["id"],
                "username": u.get("username") or u.get("first_name") or f"User {u['id']}",
                "reason": u.get("ban_reason") or "Не указана",
            }
            for u in users
        ]

    async def unban_all_users(self) -> dict:
        """Амнистия: разбанить всех пользователей."""
        result = await self.users.update_many(
            {"is_banned": True},
            {"$set": {
                "is_banned": False,
                "ban_reason": None,
                "updated_at": datetime.now(timezone.utc)
            }}
        )
        affected = result.modified_count
        logger.info(f"Unbanned {affected} users (amnesty)")
        return {"success": True, "affected": affected}

    async def mute_user(
        self,
        user_id: int,
        muted_by: int = None,
        reason: str = None,
        until: datetime = None
    ) -> dict:
        """Замьютить пользователя."""
        # Check if already muted
        if user_id in self._muted_cache:
            existing_until = self._muted_cache[user_id]
            if existing_until is None or existing_until > datetime.now(timezone.utc):
                return {"success": False, "error": "Пользователь уже замьючен"}

        # Add to muted users collection
        mute_doc = {
            "user_id": user_id,
            "muted_by": muted_by,
            "reason": reason,
            "muted_at": datetime.now(timezone.utc),
            "muted_until": until,
        }
        await self.muted_users.insert_one(mute_doc)

        # Update cache
        self._muted_cache[user_id] = until

        logger.info(f"User {user_id} muted. Reason: {reason}. Until: {until}")
        return {"success": True}

    async def unmute_user(self, user_id: int) -> dict:
        """Снять мьют с пользователя."""
        # Remove from muted users collection
        result = await self.muted_users.delete_one({"user_id": user_id})

        # Update cache
        self._muted_cache.pop(user_id, None)

        if result.deleted_count == 0:
            return {"success": False, "error": "Пользователь не был замьючен"}

        logger.info(f"User {user_id} unmuted")
        return {"success": True}

    async def is_muted(self, user_id: int) -> bool:
        """Проверить, замьючен ли пользователь."""
        # Quick check via cache
        if user_id not in self._muted_cache:
            return False

        until = self._muted_cache[user_id]
        now = datetime.now(timezone.utc)
        if until is not None and now > until:
            # Time expired
            await self.unmute_user(user_id)
            return False

        return True

    async def get_muted_users(self) -> List[dict]:
        """Получить список всех замьюченных пользователей."""
        cursor = self.muted_users.find({})
        mutes = await cursor.to_list(length=None)

        # Convert to list of dicts (excluding MongoDB _id if needed, but we can keep it)
        return [
            {
                "user_id": m["user_id"],
                "muted_by": m.get("muted_by"),
                "reason": m.get("reason"),
                "muted_at": m.get("muted_at"),
                "muted_until": m.get("muted_until"),
            }
            for m in mutes
        ]

    async def mute_user_by_username(
        self,
        username: str,
        hours: float = 0,
        muted_by: int = None,
        reason: str = None
    ) -> dict:
        """Замьютить пользователя по нику."""
        # Find user by username
        user = await self.users.find_one(
            {"$or": [
                {"username": username},
                {"first_name": {"$regex": f"^{username}$", "$options": "i"}}
            ]}
        )
        if not user:
            return {"success": False, "error": "Пользователь не найден", "username": username}
        user_id = user["id"]

        until = None
        if hours > 0:
            until = datetime.now(timezone.utc) + timedelta(hours=hours)

        result = await self.mute_user(user_id, muted_by, reason, until)
        if result["success"]:
            result["username"] = user.get("username") or user.get("first_name")
        return result

    async def unmute_user_by_username(self, username: str) -> dict:
        """Снять мьют по нику."""
        # Find user by username
        user = await self.users.find_one(
            {"$or": [
                {"username": username},
                {"first_name": {"$regex": f"^{username}$", "$options": "i"}}
            ]}
        )
        if not user:
            return {"success": False, "error": "Пользователь не найден", "username": username}
        user_id = user["id"]

        result = await self.unmute_user(user_id)
        if result["success"]:
            result["username"] = user.get("username") or user.get("first_name")
        return result