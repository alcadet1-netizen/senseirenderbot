"""
🏆 Репозиторий достижений.
"""

from typing import List, Optional, Set

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.infra.database.models import Achievement, UserAchievement


class AchievementRepository:
    """Репозиторий для работы с достижениями."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all_achievements(self) -> List[Achievement]:
        """Получить все достижения."""
        result = await self.session.execute(select(Achievement))
        return list(result.scalars().all())

    async def get_achievement(self, achievement_id: str) -> Optional[Achievement]:
        """Получить достижение по ID."""
        result = await self.session.execute(
            select(Achievement).where(Achievement.id == achievement_id)
        )
        return result.scalar_one_or_none()

    async def get_user_achievements(self, user_id: int) -> List[UserAchievement]:
        """Получить достижения пользователя."""
        result = await self.session.execute(
            select(UserAchievement)
            .where(UserAchievement.user_id == user_id)
        )
        return list(result.scalars().all())

    async def get_user_achievement_ids(self, user_id: int) -> Set[str]:
        """Получить ID достижений пользователя."""
        result = await self.session.execute(
            select(UserAchievement.achievement_id)
            .where(UserAchievement.user_id == user_id)
        )
        return {row[0] for row in result.all()}

    async def has_achievement(self, user_id: int, achievement_id: str) -> bool:
        """Проверить наличие достижения у пользователя."""
        result = await self.session.execute(
            select(UserAchievement)
            .where(UserAchievement.user_id == user_id)
            .where(UserAchievement.achievement_id == achievement_id)
        )
        return result.scalar_one_or_none() is not None

    async def unlock_achievement(
        self,
        user_id: int,
        achievement_id: str
    ) -> Optional[UserAchievement]:
        """Разблокировать достижение."""
        if await self.has_achievement(user_id, achievement_id):
            return None
        
        user_achievement = UserAchievement(
            user_id=user_id,
            achievement_id=achievement_id
        )
        self.session.add(user_achievement)
        await self.session.flush()
        return user_achievement

    async def count_user_achievements(self, user_id: int) -> int:
        """Подсчитать количество достижений пользователя."""
        result = await self.session.execute(
            select(func.count(UserAchievement.id))
            .where(UserAchievement.user_id == user_id)
        )
        return result.scalar() or 0

    async def create_achievement(
        self,
        achievement_id: str,
        name: str,
        description: str,
        xp_reward: int = 0,
        coin_reward: int = 0
    ) -> Achievement:
        """Создать достижение."""
        achievement = Achievement(
            id=achievement_id,
            name=name,
            description=description,
            xp_reward=xp_reward,
            coin_reward=coin_reward
        )
        self.session.add(achievement)
        await self.session.flush()
        return achievement