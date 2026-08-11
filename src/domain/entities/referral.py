from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from enum import Enum

class ReferralRank(Enum):
    NOVICE = ("novice", "🥚", "Новичок", 0)
    BEGINNER = ("beginner", "🐣", "Ученик", 5)
    APPRENTICE = ("apprentice", "🐥", "Подмастерье", 15)
    ADEPT = ("adept", "🦅", "Адепт", 30)
    MASTER = ("master", "🦉", "Мастер", 50)
    SENSEI = ("sensei", "🐲", "Сенсей", 100)
    LEGEND = ("legend", "🐉", "Легенда", 250)
    EMPEROR = ("emperor", "👑", "Император", 500)
    GOD = ("god", "⚡", "Бог Рефералов", 1000)
    
    def __init__(self, id_: str, emoji: str, title: str, required: int):
        self.id_, self.emoji, self.title, self.required = id_, emoji, title, required
    
    @classmethod
    def from_count(cls, count: int) -> "ReferralRank":
        result = cls.NOVICE
        for rank in cls:
            if count >= rank.required:
                result = rank
        return result
    
    @classmethod
    def next_rank(cls, current: "ReferralRank") -> Optional["ReferralRank"]:
        ranks = list(cls)
        idx = ranks.index(current)
        return ranks[idx + 1] if idx < len(ranks) - 1 else None

@dataclass
class ReferralStats:
    user_id: int
    level_1_count: int = 0
    level_2_count: int = 0
    level_1_active: int = 0
    level_2_active: int = 0
    total_coins_earned: float = 0.0
    total_xp_earned: int = 0
    
    @property
    def rank(self) -> ReferralRank:
        return ReferralRank.from_count(self.level_1_count)
    
    @property
    def next_rank(self) -> Optional[ReferralRank]:
        return ReferralRank.next_rank(self.rank)
    
    @property
    def progress_to_next(self) -> float:
        next_r = self.next_rank
        if not next_r:
            return 100.0
        current_req = self.rank.required
        next_req = next_r.required
        # Prevent division by zero if current_req == next_req (should not happen)
        if next_req == current_req:
             return 100.0
             
        # Calculation based on user snippet logic
        # ((self.level_1_count - current_req) / (next_req - current_req)) * 100
        # However, simple percentage of total required might be clearer, but let's stick to user logic
        progress = ((self.level_1_count - current_req) / (next_req - current_req)) * 100
        return min(100.0, max(0.0, progress))

# Награды: level -> (referrer_coins, referrer_xp, referred_coins, referred_xp)
REWARDS = {1: (200, 100, 100, 100), 2: (50, 25, 0, 0)}
