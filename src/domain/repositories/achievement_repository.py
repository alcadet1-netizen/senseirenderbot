"""
🏆 Репозиторий достижений.
"""

from typing import List, Optional, Set, Dict
from motor.motor_asyncio import AsyncIOMotorCollection
from datetime import datetime, timezone


class AchievementRepository:
    """Репозиторий для работы с достижениями и成績 пользователей."""

    def __init__(self, achievements_def_collection: AsyncIOMotorCollection, user_achievements_collection: AsyncIOMotorCollection):
        self.achievements_def = achievements_def_collection
        self.user_achievements = user_achievements_collection

    async def get_all_achievements(self) -> List[Dict]:
        """Получить все достижения."""
        cursor = self.achievements_def.find({})
        return await cursor.to_list(length=None)

    async def get_achievement(self, achievement_id: str) -> Optional[Dict]:
        """Получить достижение по ID."""
        return await self.achievements_def.find_one({"_id": achievement_id})

    async def get_user_achievements(self, user_id: int) -> List[Dict]:
        """Получить достижения пользователя."""
        cursor = self.user_achievements.find({"user_id": user_id})
        return await cursor.to_list(length=None)

    async def get_user_achievement_ids(self, user_id: int) -> Set[str]:
        """Получить ID достижений пользователя."""
        cursor = self.user_achievements.find({"user_id": user_id}, {"achievement_id": 1, "_id": 0})
        result = await cursor.to_list(length=None)
        return {doc["achievement_id"] for doc in result}

    async def has_achievement(self, user_id: int, achievement_id: str) -> bool:
        """Проверить наличие достижения у пользователя."""
        doc = await self.user_achievements.find_one({
            "user_id": user_id,
            "achievement_id": achievement_id
        })
        return doc is not None

    async def unlock_achievement(
        self,
        user_id: int,
        achievement_id: str
    ) -> bool:
        """Разблокировать достижение."""
        if await self.has_achievement(user_id, achievement_id):
            return False  # Already unlocked

        # Verify achievement exists
        ach_def = await self.achievements_def.find_one({"_id": achievement_id})
        if not ach_def:
            return False  # Achievement does not exist

        # Insert the user achievement
        doc = {
            "user_id": user_id,
            "achievement_id": achievement_id,
            "unlocked_at": datetime.now(timezone.utc),
        }
        await self.user_achievements.insert_one(doc)
        return True

    async def count_user_achievements(self, user_id: int) -> int:
        """Подсчитать количество достижений пользователя."""
        return await self.user_achievements.count_documents({"user_id": user_id})

    async def create_achievement(
        self,
        achievement_id: str,
        name: str,
        description: str,
        xp_reward: int = 0,
        coin_reward: int = 0
    ) -> str:
        """Создать достижение."""
        achievement = {
            "_id": achievement_id,
            "name": name,
            "description": description,
            "xp_reward": xp_reward,
            "coin_reward": coin_reward,
            "created_at": datetime.now(timezone.utc),
        }
        result = await self.achievements_def.insert_one(achievement)
        return str(result.inserted_id)

    async def add_achievement(self, achievement_id: str, achievement_def: Dict) -> str:
        """Добавить достижение из словаря определения."""
        achievement = {
            "_id": achievement_id,
            "name": achievement_def.get("name", ""),
            "description": achievement_def.get("description", ""),
            "xp_reward": achievement_def.get("reward_xp", 0),
            "coin_reward": achievement_def.get("reward_coins", 0),
            "rarity": achievement_def.get("rarity", "common"),
            "icon": achievement_def.get("icon", "🏆"),
            "created_at": datetime.now(timezone.utc),
        }
        result = await self.achievements_def.insert_one(achievement)
        return str(result.inserted_id)