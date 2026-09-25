"""
🏆 Модели достижений.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infra.database.models.base import Base

if TYPE_CHECKING:
    from src.infra.database.models.user import User


class Achievement(Base):
    """Справочник достижений."""

    __tablename__ = "achievements"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    xp_reward: Mapped[int] = mapped_column(Integer, default=0)
    coin_reward: Mapped[int] = mapped_column(Integer, default=0)

    def __repr__(self) -> str:
        return f"<Achievement(id={self.id}, name={self.name})>"


class UserAchievement(Base):
    """Достижения пользователя."""

    __tablename__ = "user_achievements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    achievement_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("achievements.id"), nullable=False
    )
    
    unlocked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    
    user: Mapped["User"] = relationship("User", back_populates="achievements")
    achievement: Mapped[Optional[Achievement]] = relationship("Achievement", lazy="joined")

    def __repr__(self) -> str:
        return f"<UserAchievement(user={self.user_id}, achievement={self.achievement_id})>"