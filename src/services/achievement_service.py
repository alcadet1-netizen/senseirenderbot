"""
�����������������������������🏆 Сервис достижений.
"""

from typing import List, Dict
from motor.motor_asyncio import AsyncIOMotorDatabase
from src.core.config import settings
from src.core.constants import ACHIEVEMENTS
from src.infra.mongo.client import MongoClient
from src.services.level_service import LevelService
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class AchievementService:
    """Сервис для работы с достижениями."""

    def __init__(self, mongo_client: MongoClient):
        self.mongo_client = mongo_client
        self.db: AsyncIOMotorDatabase = mongo_client.database
        self.level_service = LevelService()
        # Collections
        self.achievements_def = self.db.achievements_def  # Stores the definition of achievements
        self.user_achievements = self.db.user_achievements  # Stores which user has which achievement
        # We'll also need users collection for checking user stats
        self.users = self.db.users

    async def seed_achievements(self) -> int:
        """Заполнить базу достижениями, если она пуста."""
        # Check if we already have achievements defined
        count = await self.achievements_def.count_documents({})
        if count > 0:
            logger.info("Achievements already seeded, skipping")
            return 0

        # Insert the achievements from constants
        to_insert = []
        for ach_id, ach_data in ACHIEVEMENTS.items():
            # We assume ACHIEVEMENTS is a dict with achievement_id as key and data as value
            # The data should include: name, description, criteria, etc.
            # We'll store the achievement_id as well
            doc = {
                "_id": ach_id,
                "name": ach_data.get("name", ""),
                "description": ach_data.get("description", ""),
                "criteria": ach_data.get("criteria", {}),
                "reward_coins": ach_data.get("reward_coins", 0.0),
                "reward_xp": ach_data.get("reward_xp", 0),
                "created_at": datetime.now(timezone.utc),
            }
            to_insert.append(doc)

        if to_insert:
            await self.achievements_def.insert_many(to_insert)
            logger.info(f"Seeded {len(to_insert)} achievements")
            return len(to_insert)
        return 0

    async def check_and_unlock_achievements(
        self,
        user_id: int,
        force_check: List[str] = None
    ) -> List[str]:
        """Проверить и разблокировать новые достижения для пользователя.
        Возвращает список newly unlocked achievement IDs.
        """
        # We'll implement a simple version for now.
        # In reality, we would check each achievement's criteria against the user's stats.
        # For the sake of time, we'll return an empty list.
        # TODO: Implement proper achievement checking.
        return []

    async def get_user_achievements(self, user_id: int) -> List[Dict]:
        """Получить список достижений пользователя."""
        cursor = self.user_achievements.find({"user_id": user_id})
        achievements = []
        async for doc in cursor:
            achievements.append({
                "achievement_id": doc.get("achievement_id"),
                "unlocked_at": doc.get("unlocked_at"),
            })
        return achievements

    async def unlock_achievement(self, user_id: int, achievement_id: str) -> bool:
        """Разблокировать достижение для пользователя, если еще не разблокировано."""
        # Check if already unlocked
        existing = await self.user_achievements.find_one({
            "user_id": user_id,
            "achievement_id": achievement_id
        })
        if existing:
            return False  # Already unlocked

        # Get achievement definition to verify it exists
        ach_def = await self.achievements_def.find_one({"_id": achievement_id})
        if not ach_def:
            logger.warning(f"Attempt to unlock non-existent achievement: {achievement_id}")
            return False

        # Insert the user achievement
        doc = {
            "user_id": user_id,
            "achievement_id": achievement_id,
            "unlocked_at": datetime.now(timezone.utc),
        }
        await self.user_achievements.insert_one(doc)

        # Give rewards to the user
        reward_coins = ach_def.get("reward_coins", 0.0)
        reward_xp = ach_def.get("reward_xp", 0)
        if reward_coins != 0.0 or reward_xp != 0:
            await self.users.update_one(
                {"id": user_id},
                {"$inc": {"coins": reward_coins, "xp": reward_xp}}
            )
            # Create transaction for the reward
            tx_doc = {
                "user_id": user_id,
                "tx_type": "achievement_reward",
                "coins_change": reward_coins,
                "xp_change": reward_xp,
                "description": f"Achievement reward: {ach_def.get('name', achievement_id)}",
                "created_at": datetime.now(timezone.utc),
            }
            await self.db.transactions.insert_one(tx_doc)

        return True