from datetime import datetime
from sqlalchemy import BigInteger, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from src.infra.database.models.base import Base


class MutedUser(Base):
    __tablename__ = "muted_users"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    muted_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    muted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    muted_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
