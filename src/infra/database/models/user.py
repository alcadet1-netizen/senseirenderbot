"""
👤 Модель пользователя.
"""

from datetime import datetime
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, Float, Integer, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infra.database.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from src.infra.database.models.ticket import Ticket
    from src.infra.database.models.transaction import Transaction
    from src.infra.database.models.achievement import UserAchievement
    from src.infra.database.models.daily import DailyClaim


class User(Base, TimestampMixin):
    """Модель пользователя бота."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    first_name: Mapped[str] = mapped_column(String(128), default="")
    last_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    # Экономика
    xp: Mapped[int] = mapped_column(Integer, default=0)
    coins: Mapped[float] = mapped_column(Float, default=0.0)
    messages_count: Mapped[int] = mapped_column(Integer, default=0)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    losses: Mapped[int] = mapped_column(Integer, default=0)

    # Daily
    daily_streak: Mapped[int] = mapped_column(Integer, default=0)
    last_daily: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Статус
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    ban_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_muted: Mapped[bool] = mapped_column(Boolean, default=False)
    mute_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_bot: Mapped[bool] = mapped_column(Boolean, default=False)

    # Особые предметы
    has_katana: Mapped[bool] = mapped_column(Boolean, default=False)
    katana_length: Mapped[float] = mapped_column(Float, default=0.0, server_default="0.0")
    last_katana_up: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Реферал
    referrer_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)
    referral_count: Mapped[int] = mapped_column(Integer, default=0)

    # Для рассылки
    can_receive_broadcast: Mapped[bool] = mapped_column(Boolean, default=True)

    # Связи
    tickets: Mapped[List["Ticket"]] = relationship(
        "Ticket", back_populates="user"
    )
    transactions: Mapped[List["Transaction"]] = relationship(
        "Transaction", back_populates="user"
    )
    achievements: Mapped[List["UserAchievement"]] = relationship(
        "UserAchievement", back_populates="user"
    )
    daily_claims: Mapped[List["DailyClaim"]] = relationship(
        "DailyClaim", back_populates="user"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username})>"