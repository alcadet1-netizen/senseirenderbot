from sqlalchemy import BigInteger, Integer, ForeignKey, Boolean, Float, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.infra.database.models.base import Base, TimestampMixin

class Referral(Base, TimestampMixin):
    __tablename__ = "referrals"
    __table_args__ = (
        UniqueConstraint("referred_id", "level", name="uq_referrals_referred_level"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    referrer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    referred_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    level: Mapped[int] = mapped_column(Integer, default=1)
    coins_earned: Mapped[float] = mapped_column(Float, default=0.0)
    xp_earned: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships can be added if needed, but for now we'll stick to foreign keys
