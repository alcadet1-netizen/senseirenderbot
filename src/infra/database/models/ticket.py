"""
🎫 Модель билетов.
"""

from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infra.database.models.base import Base

if TYPE_CHECKING:
    from src.infra.database.models.user import User


class Ticket(Base):
    """Билет пользователя для розыгрышей."""

    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    
    is_burned: Mapped[bool] = mapped_column(Boolean, default=False)
    burned_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    burn_reason: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    
    user: Mapped["User"] = relationship("User", back_populates="tickets")

    def __repr__(self) -> str:
        return f"<Ticket(id={self.id}, code={self.code}, burned={self.is_burned})>"