"""
📢 Domain events.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class DomainEvent:
    """Базовый класс событий."""
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


@dataclass
class UserLeveledUpEvent(DomainEvent):
    """Событие повышения уровня."""
    user_id: int = 0
    old_level: int = 0
    new_level: int = 0
    level_name: str = ""


@dataclass
class AchievementUnlockedEvent(DomainEvent):
    """Событие разблокировки достижения."""
    user_id: int = 0
    achievement_id: str = ""
    achievement_name: str = ""
    xp_reward: int = 0
    coin_reward: int = 0


@dataclass
class DailyClaimedEvent(DomainEvent):
    """Событие получения ежедневного бонуса."""
    user_id: int = 0
    xp: int = 0
    coins: int = 0
    streak: int = 0


@dataclass
class TicketCreatedEvent(DomainEvent):
    """Событие создания билета."""
    user_id: int = 0
    ticket_code: str = ""


@dataclass
class ExchangeCompletedEvent(DomainEvent):
    """Событие обмена."""
    user_id: int = 0
    direction: str = ""  # "coins_to_ticket" or "ticket_to_coins"
    amount_from: float = 0
    amount_to: float = 0