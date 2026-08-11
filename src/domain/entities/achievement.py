"""
🏆 Domain entity: Achievement.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class AchievementEntity:
    """Доменная сущность достижения."""

    id: str = ""
    name: str = ""
    description: str = ""
    xp_reward: int = 0
    coin_reward: int = 0


@dataclass
class UserAchievementEntity:
    """Достижение пользователя."""

    id: Optional[int] = None
    user_id: int = 0
    achievement_id: str = ""
    unlocked_at: Optional[datetime] = None
    achievement: Optional[AchievementEntity] = None