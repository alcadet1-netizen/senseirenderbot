"""
📅 Модель ежедневных наград.
"""

from datetime import datetime, date as date_type
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infra.database.models.base import Base

if TYPE_CHECKING:
    from src.infra.database.models.user import User


class DailyClaim(Base):
    """История получения ежедневных бонусов."""

    __tablename__ = "daily_claims"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    
    claim_date: Mapped[date_type] = mapped_column(Date, nullable=False)
    
    xp_received: Mapped[int] = mapped_column(Integer, default=0)
    coins_received: Mapped[int] = mapped_column(Integer, default=0)
    streak_at_claim: Mapped[int] = mapped_column(Integer, default=1)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    
    user: Mapped["User"] = relationship("User", back_populates="daily_claims")

    def __repr__(self) -> str:
        return f"<DailyClaim(user={self.user_id}, date={self.claim_date})>"