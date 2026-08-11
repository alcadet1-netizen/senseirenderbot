"""
👤 Domain entity: User.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

@dataclass
class UserEntity:
    """Доменная сущность пользователя."""

    id: int
    username: Optional[str] = None
    first_name: str = ""
    last_name: Optional[str] = None

    # Экономика
    xp: int = 0
    coins: float = 0.0
    messages_count: int = 0

    # Daily
    daily_streak: int = 0
    last_daily: Optional[datetime] = None

    # Статус
    is_banned: bool = False
    ban_reason: Optional[str] = None
    is_muted: bool = False

    # Особые предметы
    has_katana: bool = False
    katana_length: float = 0.0
    last_katana_up: Optional[datetime] = None

    # Реферал
    referrer_id: Optional[int] = None
    referral_count: int = 0

    # Билеты
    tickets_count: int = 0

    # Достижения
    achievements: List[str] = field(default_factory=list)

    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @property
    def display_name(self) -> str:
        """Отображаемое имя пользователя."""
        if self.username:
            return f"@{self.username}"
        return self.first_name or f"User {self.id}"

    @property
    def full_name(self) -> str:
        """Полное имя."""
        parts = [self.first_name]
        if self.last_name:
            parts.append(self.last_name)
        return " ".join(parts) or f"User {self.id}" 
