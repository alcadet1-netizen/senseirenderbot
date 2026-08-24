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
from src.core.config import settings
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

    async def _get_bank_balance(self) -> float:
        """Получить текущий баланс банка."""
        doc = await self.db.bank.find_one({"_id": "single"})
        if doc:
            balance = doc.get("coins", 0.0)
            if balance == 0.0:
                # Reset bank to initial balance if empty
                initial_balance = settings.bank_initial_coins
                await self._set_bank_balance(initial_balance)
                logger.info(f"[ACHIEVEMENT SERVICE] Bank balance was zero, reset to {initial_balance}")
                return initial_balance
            logger.info(f"[ACHIEVEMENT SERVICE] Found bank document with balance {balance}")
            return balance
        else:
            # Initialize bank with initial coins from settings
            initial_balance = settings.bank_initial_coins
            await self.db.bank.insert_one({"_id": "single", "coins": initial_balance})
            logger.info(f"[ACHIEVEMENT SERVICE] Initialized bank with balance {initial_balance}")
            return initial_balance

    async def _set_bank_balance(self, balance: float) -> None:
        """Установить баланс банка."""
        await self.db.bank.update_one(
            {"_id": "single"},
            {"$set": {"coins": balance}},
            upsert=True
        )
        logger.info(f"[ACHIEVEMENT SERVICE] Bank balance set to {balance:,.2f}")

    async def _withdraw_from_bank(self, amount: float) -> bool:
        """Снять amount с банка. Возвращает True если успешно."""
        # We'll do this in a transaction-like manner by finding and updating.
        # For simplicity, we'll do it without transaction and hope for the best.
        # In production, we should use a transaction.
        doc = await self.db.bank.find_one({"_id": "single"})
        if not doc:
            # Initialize if not exists
            await self._set_bank_balance(settings.bank_initial_coins)
            doc = await self.db.bank.find_one({"_id": "single"})
        current_balance = doc.get("coins", 0.0)
        if current_balance < amount:
            return False
        new_balance = current_balance - amount
        await self._set_bank_balance(new_balance)
        return True

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
                # Check bank balance and withdraw if possible
                bank_balance = await self._get_bank_balance()
                if bank_balance >= reward_coins:
                    await self._withdraw_from_bank(reward_coins)
                else:
                    reward_coins = 0  # Not enough in bank

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

    async def get_user_achievements(self, user_id: int) -> Dict:
        """Получить достижения пользователя, разделенные на открытые и закрытые."""
        # Get all achievement definitions
        all_achievements = ACHIEVEMENTS

        # Get user's unlocked achievement IDs
        unlocked_ids = await self.achievement_repo.get_user_achievement_ids(user_id)

        # Separate into unlocked and locked
        unlocked = []
        locked = []

        for ach_id, ach_def in all_achievements.items():
            # Create achievement dict for display
            ach_display = {
                "id": ach_id,
                "name": ach_def["name"],
                "description": ach_def["description"],
                "xp_reward": ach_def["xp_reward"],
                "coin_reward": ach_def["coin_reward"],
                "rarity": ach_def["rarity"],
                "icon": ach_def["icon"]
            }

            if ach_id in unlocked_ids:
                unlocked.append(ach_display)
            else:
                locked.append(ach_display)

        # Sort by some criteria (e.g., rarity, then ID) for consistent display
        # For now, we'll keep the order from ACHIEVEMENTS

        return {
            "unlocked": unlocked,
            "locked": locked,
            "total": len(all_achievements),
            "unlocked_count": len(unlocked)
        }

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
            # Check bank balance and withdraw if possible
            bank_balance = await self._get_bank_balance()
            if bank_balance >= reward_coins:
                await self._withdraw_from_bank(reward_coins)
            else:
                reward_coins = 0  # Not enough in bank

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

    async def seed_achievements(self) -> int:
        """Заполнить базу данных определениями достижений, если они еще не существуют.
        Возвращает количество newly созданных достижений.
        """
        seeded_count = 0

        for ach_id, ach_def in ACHIEVEMENTS.items():
            # Check if achievement already exists
            existing = await self.achievement_repo.get_achievement(ach_id)
            if not existing:
                # Insert the achievement definition
                await self.achievement_repo.add_achievement(ach_id, ach_def)
                seeded_count += 1
                logger.info(f"Seeded achievement: {ach_id}")

        if seeded_count > 0:
            logger.info(f"✅ Seeded {seeded_count} achievements")
        else:
            logger.info("✅ All achievements already seeded")

        return seeded_count