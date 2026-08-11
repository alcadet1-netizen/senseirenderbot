"""
📅 Domain entity: Daily Claim.
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional


@dataclass
class DailyClaimEntity:
    """Доменная сущность ежедневного бонуса."""

    id: Optional[int] = None
    user_id: int = 0
    claim_date: Optional[date] = None
    xp_received: int = 0
    coins_received: int = 0
    streak_at_claim: int = 1
    created_at: Optional[datetime] = None