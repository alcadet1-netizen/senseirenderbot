"""
🏆 Сервис достижений.
"""

from typing import List

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.core.constants import ACHIEVEMENTS
from src.domain.repositories import (
    AchievementRepository,
    BankRepository,
    TransactionRepository,
    UserRepository,
)
from src.infra.database.models import TransactionType
from src.infra.database.uow import UnitOfWork
from src.services.level_service import LevelService


class AchievementService:
    """Сервис для работы с достижениями."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self.session_factory = session_factory
        self.level_service = LevelService()

    async def check_and_unlock_achievements(
        self,
        user_id: int,
        context: dict
    ) -> List[dict]:
        """Проверить и разблокировать достижения."""
        uow = UnitOfWork(self.session_factory)
        unlocked = []
        
        async with uow:
            user_repo = UserRepository(uow.session)
            achievement_repo = AchievementRepository(uow.session)
            bank_repo = BankRepository(uow.session)
            tx_repo = TransactionRepository(uow.session)
            
            user = await user_repo.get_by_id(user_id)
            if not user:
                return []
            
            unlocked_ids = await achievement_repo.get_user_achievement_ids(user_id)
            
            achievements_to_check = {
                "first_message": context.get("messages_count", user.messages_count) >= 1,
                "messages_100": context.get("messages_count", user.messages_count) >= 100,
                "messages_1000": context.get("messages_count", user.messages_count) >= 1000,
                "messages_10000": context.get("messages_count", user.messages_count) >= 10000,
                "level_5": self.level_service.get_level(context.get("xp", user.xp)) >= 5,
                "level_10": self.level_service.get_level(context.get("xp", user.xp)) >= 10,
                "level_15": self.level_service.get_level(context.get("xp", user.xp)) >= 15,
                "level_20": self.level_service.get_level(context.get("xp", user.xp)) >= 20,
                "daily_7": context.get("streak", user.daily_streak) >= 7,
                "daily_30": context.get("streak", user.daily_streak) >= 30,
                "first_ticket": context.get("tickets", 0) >= 1,
                "tickets_10": context.get("tickets", 0) >= 10,
                "rich_1000": context.get("coins", user.coins) >= 1000,
                "rich_10000": context.get("coins", user.coins) >= 10000,
                "katana_owner": user.has_katana,
                "duel_winner": context.get("wins", user.wins) >= 1,
                "duel_master": context.get("wins", user.wins) >= 50,
            }
            
            for achievement_id, condition in achievements_to_check.items():
                if condition and achievement_id not in unlocked_ids:
                    user_achievement = await achievement_repo.unlock_achievement(
                        user_id, achievement_id
                    )
                    
                    if user_achievement and achievement_id in ACHIEVEMENTS:
                        ach_data = ACHIEVEMENTS[achievement_id]
                        
                        xp_reward = ach_data.get("xp_reward", 0)
                        coin_reward = ach_data.get("coin_reward", 0)
                        
                        if xp_reward > 0:
                            user.xp += xp_reward
                        if coin_reward > 0:
                            try:
                                await bank_repo.withdraw(coin_reward)
                                user.coins += coin_reward
                            except Exception:
                                coin_reward = 0
                        
                        if xp_reward > 0 or coin_reward > 0:
                            await tx_repo.create(
                                user_id=user.id,
                                tx_type=TransactionType.ACHIEVEMENT_REWARD.value,
                                xp_change=xp_reward,
                                coins_change=coin_reward,
                                description=f"Achievement: {achievement_id}"
                            )
                        
                        unlocked.append({
                            "id": achievement_id,
                            "name": ach_data["name"],
                            "description": ach_data["description"],
                            "xp_reward": xp_reward,
                            "coin_reward": coin_reward,
                        })
            
            if unlocked:
                await uow.commit()
        
        return unlocked

    async def get_user_achievements(self, user_id: int) -> dict:
        """Получить достижения пользователя."""
        uow = UnitOfWork(self.session_factory)
        
        async with uow:
            achievement_repo = AchievementRepository(uow.session)
            
            unlocked_ids = await achievement_repo.get_user_achievement_ids(user_id)
            
            result = {
                "unlocked": [],
                "locked": [],
                "total": len(ACHIEVEMENTS),
                "unlocked_count": len(unlocked_ids),
            }
            
            for ach_id, ach_data in ACHIEVEMENTS.items():
                item = {
                    "id": ach_id,
                    "name": ach_data["name"],
                    "description": ach_data["description"],
                    "xp_reward": ach_data.get("xp_reward", 0),
                    "coin_reward": ach_data.get("coin_reward", 0),
                }
                
                if ach_id in unlocked_ids:
                    result["unlocked"].append(item)
                else:
                    result["locked"].append(item)
            
            return result

    async def seed_achievements(self) -> int:
        """Заполнить таблицу достижений из констант."""
        uow = UnitOfWork(self.session_factory)
        count = 0
        
        async with uow:
            achievement_repo = AchievementRepository(uow.session)
            
            for ach_id, ach_data in ACHIEVEMENTS.items():
                existing = await achievement_repo.get_achievement(ach_id)
                if not existing:
                    await achievement_repo.create_achievement(
                        achievement_id=ach_id,
                        name=ach_data["name"],
                        description=ach_data["description"],
                        xp_reward=ach_data.get("xp_reward", 0),
                        coin_reward=ach_data.get("coin_reward", 0),
                    )
                    count += 1
            
            await uow.commit()
        
        return count