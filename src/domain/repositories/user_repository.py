"""
�������������👤 Репозиторий пользователей.
"""

from typing import List, Optional

from src.domain.repositories.base import BaseRepository


class UserRepository(BaseRepository):
    """Репозиторий для работы с пользователями."""

    def __init__(self, collection):
        super().__init__(collection)

    async def get_by_id(self, user_id: int) -> Optional[dict]:
        """Получить пользователя по ID."""
        return await self.collection.find_one({"id": user_id})

    async def get_for_update(self, user_id: int) -> Optional[dict]:
        """Получить пользователя по ID с блокировкой (для транзакций).

        В MongoDB мы не можем блокировать отдельные документы для обновления
        в том же смысле, что и в SQL с FOR UPDATE, но мы можем использовать
        findAndModify с upsert для атомарных операций.
        Для простоты здесь возвращаем обычный документ.
        """
        # В реальной реализации с транзакциями мы бы использовали сессию
        # Но для простоты возвращаем обычное чтение
        return await self.collection.find_one({"id": user_id})

    async def get_by_username(self, username: str) -> Optional[dict]:
        """Получить пользователя по username."""
        username = username.lstrip("@")
        return await self.collection.find_one(
            {"username": {"$regex": f"^{username}$", "$options": "i"}}
        )

    async def get_or_create(
        self,
        user_id: int,
        username: Optional[str] = None,
        first_name: str = "",
        last_name: Optional[str] = None,
        is_bot: bool = False,
        with_lock: bool = False
    ) -> tuple[Optional[dict], bool]:
        """Получить или создать пользователя."""
        if with_lock:
            # Для простоты игнорируем with_lock в MongoDB версии
            # В реальной реализации с транзакциями мы бы использовали сессию
            user = await self.get_by_id(user_id)
        else:
            user = await self.get_by_id(user_id)

        created = False

        if user is None:
            # Create new user
            from datetime import datetime, timezone
            user = {
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
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }

            result = await self.collection.insert_one(user)
            user["_id"] = result.inserted_id
            created = True
        else:
            # Update if needed
            update_data = {}
            if username is not None and user.get("username") != username:
                update_data["username"] = username
            if first_name and user.get("first_name") != first_name:
                update_data["first_name"] = first_name
            if last_name is not None and user.get("last_name") != last_name:
                update_data["last_name"] = last_name
            if user.get("is_bot") != is_bot:
                update_data["is_bot"] = is_bot

            if update_data:
                update_data["updated_at"] = datetime.now(timezone.utc)
                await self.collection.update_one(
                    {"id": user_id},
                    {"$set": update_data}
                )
                # Update the user dict for return
                user.update(update_data)

        return user, created

    async def update(self, user: dict) -> bool:
        """Обновить пользователя."""
        if "_id" not in user and "id" not in user:
            raise ValueError("User must have _id or id field for update")

        # Use id field if _id not present
        user_id = user.get("_id") or user.get("id")
        if user_id is None:
            raise ValueError("User must have _id or id field for update")

        # Remove id fields from update data to avoid conflicts
        update_data = {k: v for k, v in user.items() if k not in ["_id", "id"]}

        result = await self.collection.update_one(
            {"id": user_id},
            {"$set": update_data}
        )
        return result.modified_count > 0

    async def get_top_by_xp(self, limit: int = 10) -> List[dict]:
        """Топ по XP."""
        cursor = self.collection.find(
            {"is_banned": False}
        ).sort("xp", -1).limit(limit)
        return await cursor.to_list(length=limit)

    async def get_top_by_coins(self, limit: int = 10) -> List[dict]:
        """Топ по монетам."""
        cursor = self.collection.find(
            {"is_banned": False}
        ).sort("coins", -1).limit(limit)
        return await cursor.to_list(length=limit)

    async def get_top_by_messages(self, limit: int = 10) -> List[dict]:
        """Топ по сообщениям."""
        cursor = self.collection.find(
            {"is_banned": False}
        ).sort("messages_count", -1).limit(limit)
        return await cursor.to_list(length=limit)

    async def get_top_by_streak(self, limit: int = 10) -> List[dict]:
        """Топ по страйку."""
        cursor = self.collection.find(
            {"is_banned": False}
        ).sort("daily_streak", -1).limit(limit)
        return await cursor.to_list(length=limit)

    async def get_top_by_katana(self, limit: int = 10, offset: int = 0) -> List[dict]:
        """Топ по длине катаны."""
        cursor = self.collection.find({
            "is_banned": False,
            "is_bot": False,
            "has_katana": True
        }).sort("katana_length", -1).skip(offset).limit(limit)
        return await cursor.to_list(length=limit)

    async def count_with_katana(self) -> int:
        """Подсчитать пользователей с катаной."""
        return await self.collection.count_documents({
            "is_banned": False,
            "is_bot": False,
            "has_katana": True
        })

    async def get_active_users(self, since_hours: int = 720, limit: int = 10000) -> List[dict]:
        """Получить активных пользователей."""
        from datetime import datetime, timedelta

        since = datetime.now() - timedelta(hours=since_hours)

        cursor = self.collection.find({
            "is_banned": False,
            "updated_at": {"$gte": since}
        }).limit(limit)
        return await cursor.to_list(length=limit)

    async def get_all_for_broadcast(self) -> List[dict]:
        """Получить всех пользователей для рассылки."""
        cursor = self.collection.find({
            "is_banned": False,
            "can_receive_broadcast": True
        })
        return await cursor.to_list(length=None)

    async def get_banned_users(self) -> List[dict]:
        """Получить забаненных пользователей."""
        cursor = self.collection.find({"is_banned": True})
        return await cursor.to_list(length=None)

    async def ban_user(self, user_id: int, reason: str = "") -> bool:
        """Забанить пользователя."""
        from datetime import datetime, timezone
        result = await self.collection.update_one(
            {"id": user_id},
            {
                "$set": {
                    "is_banned": True,
                    "ban_reason": reason,
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
        return result.modified_count > 0

    async def unban_user(self, user_id: int) -> bool:
        """Разбанить пользователя."""
        from datetime import datetime, timezone
        result = await self.collection.update_one(
            {"id": user_id},
            {
                "$set": {
                    "is_banned": False,
                    "ban_reason": None,
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
        return result.modified_count > 0

    async def unban_all_users(self) -> int:
        """Разбанить всех пользователей."""
        from datetime import datetime, timezone
        result = await self.collection.update_many(
            {"is_banned": True},
            {
                "$set": {
                    "is_banned": False,
                    "ban_reason": None,
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
        return result.modified_count

    async def count_all(self) -> int:
        """Подсчитать всех пользователей."""
        return await self.collection.count_documents({})

    async def reset_season_data(self, keep_katana: bool = True) -> int:
        """Сброс сезонных данных."""
        from datetime import datetime, timezone

        update_data = {
            "xp": 0,
            "coins": 0.0,
            "messages_count": 0,
            "daily_streak": 0,
            "last_daily": None,
            "updated_at": datetime.now(timezone.utc)
        }

        if not keep_katana:
            update_data["has_katana"] = False
            update_data["katana_length"] = 0.0

        result = await self.collection.update_many(
            {"is_banned": False},
            {"$set": update_data}
        )
        return result.modified_count

    async def get_random_user(self) -> Optional[dict]:
        """Получить случайного пользователя."""
        # Note: This is inefficient for large collections, but okay for now.
        # In production, we might want to use aggregation with $sample
        count = await self.collection.count_documents({"is_banned": False})
        if count == 0:
            return None

        import random
        skip = random.randint(0, count - 1)

        cursor = self.collection.find({"is_banned": False}).skip(skip).limit(1)
        results = await cursor.to_list(length=1)
        return results[0] if results else None