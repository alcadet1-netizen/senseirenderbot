"""
💰 Модель транзакций (Ledger).
"""

from datetime import datetime
from enum import Enum
from typing import Optional, TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infra.database.models.base import Base

if TYPE_CHECKING:
    from src.infra.database.models.user import User


class TransactionType(str, Enum):
    """Типы транзакций."""
    MESSAGE_REWARD = "message_reward"
    DAILY_BONUS = "daily_bonus"
    ACHIEVEMENT_REWARD = "achievement_reward"
    ADMIN_GRANT = "admin_grant"
    EXCHANGE_IN = "exchange_in"
    EXCHANGE_OUT = "exchange_out"
    LOTTERY_WIN = "lottery_win"
    REFERRAL_BONUS = "referral_bonus"
    BAN_CONFISCATION = "ban_confiscation"
    STREAK_BONUS = "streak_bonus"
    LEVEL_UP_BONUS = "level_up_bonus"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"
    PURCHASE = "purchase"
    SHOP_PURCHASE = "shop_purchase"
    GAME_WIN = "game_win"
    CASINO_BET = "casino_bet"
    QUIZ_WIN = "quiz_win"
    BOSS_LOSS = "boss_loss"
    BOSS_WIN = "boss_win"
    DUEL_BET = "duel_bet"
    DUEL_WIN = "duel_win"
    REFUND = "refund"


class Transaction(Base):
    """Ledger транзакций для аудита."""

    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    
    type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    
    xp_change: Mapped[int] = mapped_column(Integer, default=0)
    coins_change: Mapped[float] = mapped_column(Float, default=0.0)
    
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    
    user: Mapped["User"] = relationship("User", back_populates="transactions")

    def __repr__(self) -> str:
        return f"<Transaction(id={self.id}, user={self.user_id}, type={self.type})>"