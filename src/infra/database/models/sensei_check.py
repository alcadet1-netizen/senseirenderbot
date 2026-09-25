"""\
✅ Модели чеков SenseiCheck.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infra.database.models.base import Base

if TYPE_CHECKING:
    from src.infra.database.models.user import User


class SenseiCheck(Base):
    __tablename__ = "sensei_checks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)

    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)

    # Храним каналы как JSON список ID или юзернеймов: ["-100...", "@channel"]
    channels_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    
    amount_ton: Mapped[Decimal] = mapped_column(Numeric(20, 9), nullable=False)
    activation_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    activations_used: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    referral_percent: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    
    message_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    photo_file_id: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    video_file_id: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    password: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="1")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    creator: Mapped["User"] = relationship("User", lazy="joined")


class SenseiCheckActivation(Base):
    __tablename__ = "sensei_check_activations"
    __table_args__ = (
        UniqueConstraint("check_id", "user_id", name="uq_sensei_check_activation"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    check_id: Mapped[int] = mapped_column(Integer, ForeignKey("sensei_checks.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)

    # status: processing, success, failed
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="processing")
    
    # Флаг, что мы заняли место в лимите, но выплата еще идет
    slot_reserved: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="0")

    payout_amount_ton: Mapped[Decimal] = mapped_column(Numeric(20, 9), nullable=False)
    
    referral_amount_ton: Mapped[Decimal] = mapped_column(Numeric(20, 9), nullable=False, server_default="0")
    referral_user_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True, index=True)
    referral_paid: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="0")

    # ID транзакций в xRocket для отладки
    user_transfer_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    referral_transfer_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    check: Mapped["SenseiCheck"] = relationship("SenseiCheck", lazy="joined")
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id], lazy="joined")
    referral_user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[referral_user_id], lazy="joined")


# SenseiCheckChannelPreset REMOVED to avoid migrations

