"""
🏦 Модель банка.
"""

from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.infra.database.models.base import Base, TimestampMixin


class Bank(Base, TimestampMixin):
    """Системный банк для хранения монет."""

    __tablename__ = "bank"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    name: Mapped[str] = mapped_column(String(64), default="Sensei Bank")
    
    coins: Mapped[float] = mapped_column(Float, default=1_000_000_000.0)
    
    total_coins_distributed: Mapped[float] = mapped_column(Float, default=0.0)
    total_coins_collected: Mapped[float] = mapped_column(Float, default=0.0)

    def __repr__(self) -> str:
        return f"<Bank(coins={self.coins:,.2f})>"