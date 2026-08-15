"""
🏆 Сервис достижений.
"""

from typing import List, Dict, Optional, Any
from motor.motor_asyncio import AsyncIOMotorDatabase
from src.core.config import settings
from src.core.constants import ACHIEVEMENTS
from src.infra.mongo.client import MongoClient
from src.domain.repositories import AchievementRepository, UserRepository, TransactionRepository
from src.services.level_service import LevelService
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class AchievementService:
    """Сервис для работы с достижениями."""

    def __init__(self, mongo_client: MongoClient,
                 achievement_repo: AchievementRepository = None,
                 user_repo: UserRepository = None,
                 tx_repo: TransactionRepository = None):
        self.mongo_client = mongo_client
        self.db: AsyncIOMotorDatabase = mongo_client.database
        # Repositories
        self.achievement_repo = achievement_repo or AchievementRepository(
            self.db.achievements_def,   # achievements_def collection
            self.db.user_achievements   # user_achievements collection
        )
        self.user_repo = user_repo or UserRepository(self.db.users)
        self.tx_repo = tx_repo or TransactionRepository(self.db.transactions)
        self.level_service = LevelService()

    async def seed_achievements(self) -> int:
        """Заполнить базу достижениями, если она пуста."""
        # Check if we already have achievements defined
        count = await self.achievement_repo.get_all_achievements()
        if len(count) > 0:
            logger.info("Achievements already seeded, skipping")
            return 0

        # Insert the achievements from constants
        to_insert = []
        for ach_id, ach_data in ACHIEVEMENTS.items():
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
            # We'll use the achievement_repo's collection directly for insert_many
            # Alternatively, we can add a method to the repository for inserting many.
            # For now, we'll use the collection.
            await self.db.achievements_def.insert_many(to_insert)
            logger.info(f"Seeded {len(to_insert)} achievements")
            return len(to_insert)
        return 0

    async def check_and_unlock_achievements(
        self,
        user_id: int,
        force_check: List[str] = None,
        context: Dict[str, Any] = None
    ) -> List[str]:
        """Проверить и разблокировать новые достижения для пользователя.
        Возвращает список newly unlocked achievement IDs.
        """
        newly_unlocked = []
        if force_check:
            for ach_id in force_check:
                # Check if the user already has this achievement
                if not await self.achievement_repo.has_achievement(user_id, ach_id):
                    # Get the achievement definition
                    ach_def = await self.achievement_repo.get_achievement(ach_id)
                    if ach_def:
                        # Attempt to unlock
                        success = await self.achievement_repo.unlock_achievement(user_id, ach_id)
                        if success:
                            newly_unlocked.append(ach_id)
                            # Give rewards
                            reward_coins = ach_def.get("reward_coins", 0.0)
                            reward_xp = ach_def.get("reward_xp", 0)
                            if reward_coins != 0.0 or reward_xp != 0:
                                await self.user_repo.update(
                                    user_id,
                                    {"$inc": {"coins": reward_coins, "xp": reward_xp},
                                     "$set": {"updated_at": datetime.now(timezone.utc)}}
                                )
                                # Create transaction for the reward
                                tx_doc = {
                                    "user_id": user_id,
                                    "tx_type": "achievement_reward",
                                    "coins_change": reward_coins,
                                    "xp_change": reward_xp,
                                    "description": f"Achievement reward: {ach_def.get('name', ach_id)}",
                                    "created_at": datetime.now(timezone.utc),
                                }
                                await self.tx_repo.add(tx_doc)
        # TODO: Implement regular achievement checking based on user stats and context
        # For now, we only process force_check achievements
        return newly_unlocked

    async def get_user_achievements(self, user_id: int) -> List[Dict]:
        """Получить список достижений пользователя."""
        return await self.achievement_repo.get_user_achievements(user_id)

    async def unlock_achievement(self, user_id: int, achievement_id: str) -> bool:
        """Разблокировать достижение для пользователя, если еще не разблокировано."""
        # Check if already unlocked
        if await self.achievement_repo.has_achievement(user_id, achievement_id):
            return False  # Already unlocked

        # Get achievement definition to verify it exists
        ach_def = await self.achievement_repo.get_achievement(achievement_id)
        if not ach_def:
            logger.warning(f"Attempt to unlock non-existent achievement: {achievement_id}")
            return False

        # Insert the user achievement
        success = await self.achievement_repo.unlock_achievement(user_id, achievement_id)
        if not success:
            return False

        # Give rewards to the user
        reward_coins = ach_def.get("reward_coins", 0.0)
        reward_xp = ach_def.get("reward_xp", 0)
        if reward_coins != 0.0 or reward_xp != 0:
            # Update user
            await self.user_repo.update(
                user_id,
                {"$inc": {"coins": reward_coins, "xp": reward_xp},
                 "$set": {"updated_at": datetime.now(timezone.utc)}}
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
            await self.tx_repo.add(tx_doc)

        return True