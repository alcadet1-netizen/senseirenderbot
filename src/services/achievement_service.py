"""
🏆 Сервис достижений.
"""

from typing import List, Dict, Optional, Any
from motor.motor_asyncio import AsyncIOMotorDatabase
from src.infra.mongo.client import MongoClient
from src.domain.repositories import (
    AchievementRepository,
    UserRepository,
    TransactionRepository,
)
from src.services.level_service import LevelService
from src.core.constants import ACHIEVEMENTS
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class AchievementService:
    """Сервис для работы с достижениями."""

    def __init__(
        self,
        mongo_client: MongoClient,
        achievement_repo: AchievementRepository = None,
        user_repo: UserRepository = None,
        tx_repo: TransactionRepository = None,
    ):
        self.mongo_client = mongo_client
        self.db: AsyncIOMotorDatabase = mongo_client.database
        self.achievement_repo = achievement_repo or AchievementRepository(
            self.db.achievements_def,
            self.db.user_achievements,
        )
        self.user_repo = user_repo or UserRepository(self.db.users)
        self.tx_repo = tx_repo or TransactionRepository(self.db.transactions)
        self.level_service = LevelService()

    async def check_and_unlock_achievements(
        self,
        user_id: int,
        force_check: List[str] = None,
        context: Dict[str, Any] = None
    ) -> List[Dict]:
        """Проверить и разблокировать достижения для пользователя.
        Возвращает список newly unlocked достижений.
        """
        newly_unlocked = []

        # Get user profile
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            return newly_unlocked

        # If force_check is provided, only check those achievements
        if force_check:
            achievements_to_check = {}
            for ach_id in force_check:
                if ach_id in ACHIEVEMENTS:
                    # We'll evaluate the condition below
                    achievements_to_check[ach_id] = False  # placeholder
            # We'll evaluate conditions in the loop below
        else:
            # Build dynamic counters from user profile
            messages_count = user.get("messages_count", 0)
            xp_value = user.get("xp", 0)
            coins_value = user.get("coins", 0.0)
            streak_value = user.get("streak", 0)
            tickets_value = user.get("tickets", 0)
            wins_value = user.get("wins", 0)
            has_katana = user.get("has_katana", False)

            achievements_to_check = {
                "first_message": messages_count >= 1,
                "messages_100": messages_count >= 100,
                "messages_1000": messages_count >= 1000,
                "messages_10000": messages_count >= 10000,
                "level_5": self.level_service.get_level(xp_value) >= 5,
                "level_10": self.level_service.get_level(xp_value) >= 10,
                "level_15": self.level_service.get_level(xp_value) >= 15,
                "level_20": self.level_service.get_level(xp_value) >= 20,
                "daily_7": streak_value >= 7,
                "daily_30": streak_value >= 30,
                "first_ticket": tickets_value >= 1,
                "tickets_10": tickets_value >= 10,
                "rich_1000": coins_value >= 1000,
                "rich_10000": coins_value >= 10000,
                "katana_owner": has_katana,
                "duel_winner": wins_value >= 1,
                "duel_master": wins_value >= 50,
            }

        # Check each achievement
        for ach_id, condition in achievements_to_check.items():
            if force_check:
                # For force_check, we need to evaluate the condition based on context or user stats
                # For simplicity, we'll just check if the achievement exists and force unlock if requested
                # But the original service only processed force_check for testing, so we'll just check if it's in ACHIEVEMENTS
                if ach_id not in ACHIEVEMENTS:
                    continue
                # Evaluate condition based on user stats (same as above)
                messages_count = user.get("messages_count", 0)
                xp_value = user.get("xp", 0)
                coins_value = user.get("coins", 0.0)
                streak_value = user.get("streak", 0)
                tickets_value = user.get("tickets", 0)
                wins_value = user.get("wins", 0)
                has_katana = user.get("has_katana", False)

                if ach_id == "first_message":
                    condition = messages_count >= 1
                elif ach_id == "messages_100":
                    condition = messages_count >= 100
                elif ach_id == "messages_1000":
                    condition = messages_count >= 1000
                elif ach_id == "messages_10000":
                    condition = messages_count >= 10000
                elif ach_id == "level_5":
                    condition = self.level_service.get_level(xp_value) >= 5
                elif ach_id == "level_10":
                    condition = self.level_service.get_level(xp_value) >= 10
                elif ach_id == "level_15":
                    condition = self.level_service.get_level(xp_value) >= 15
                elif ach_id == "level_20":
                    condition = self.level_service.get_level(xp_value) >= 20
                elif ach_id == "daily_7":
                    condition = streak_value >= 7
                elif ach_id == "daily_30":
                    condition = streak_value >= 30
                elif ach_id == "first_ticket":
                    condition = tickets_value >= 1
                elif ach_id == "tickets_10":
                    condition = tickets_value >= 10
                elif ach_id == "rich_1000":
                    condition = coins_value >= 1000
                elif ach_id == "rich_10000":
                    condition = coins_value >= 10000
                elif ach_id == "katana_owner":
                    condition = has_katana
                elif ach_id == "duel_winner":
                    condition = wins_value >= 1
                elif ach_id == "duel_master":
                    condition = wins_value >= 50
                else:
                    condition = False

            if not condition:
                continue

            # Check if already unlocked
            if await self.achievement_repo.has_achievement(user_id, ach_id):
                continue

            # Get achievement definition
            ach_def = await self.achievement_repo.get_achievement(ach_id)
            if not ach_def:
                logger.warning(f"Achievement definition not found: {ach_id}")
                continue

            # Unlock the achievement
            success = await self.achievement_repo.unlock_achievement(user_id, ach_id)
            if not success:
                continue

            # Give rewards
            reward_coins = ach_def.get("reward_coins", 0.0)
            reward_xp = ach_def.get("reward_xp", 0)
            if reward_coins != 0.0 or reward_xp != 0:
                # Update user in-place
                user["coins"] = user.get("coins", 0.0) + reward_coins
                user["xp"] = user.get("xp", 0) + reward_xp
                user["updated_at"] = datetime.now(timezone.utc)
                await self.user_repo.update(user)
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

            # Add to unlocked list
            newly_unlocked.append({
                "id": ach_id,
                "name": ach_def.get("name", ""),
                "description": ach_def.get("description", ""),
                "xp_reward": reward_xp,
                "coin_reward": reward_coins,
                "rarity": ach_def.get("rarity", "common"),
                "icon": ach_def.get("icon", "🏆"),
            })

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
            # Get fresh user dict
            user = await self.user_repo.get_by_id(user_id)
            if user:
                user["coins"] = user.get("coins", 0.0) + reward_coins
                user["xp"] = user.get("xp", 0) + reward_xp
                user["updated_at"] = datetime.now(timezone.utc)
                await self.user_repo.update(user)
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