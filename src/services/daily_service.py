"""
📅 Сервис ежедневных бонусов.
"""

from datetime import date, datetime, timedelta
from typing import Optional

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.core.constants import (
    DAILY_BASE_COINS,
    DAILY_BASE_XP,
    DAILY_STREAK_BONUSES,
)
from src.core.exceptions import DailyAlreadyClaimedError
from src.domain.repositories import BankRepository, TransactionRepository, UserRepository
from src.infra.database.models import DailyClaim, TransactionType
from src.infra.database.uow import UnitOfWork
from src.infra.redis.locks import DistributedLock


class DailyService:
    """Сервис ежедневных бонусов."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        redis: Redis
    ):
        self.session_factory = session_factory
        self.redis = redis

    async def claim_daily(
        self,
        user_id: int,
        username: Optional[str] = None,
        first_name: str = "",
        is_bot: bool = False
    ) -> dict:
        """Получить ежедневный бонус."""
        lock = DistributedLock(self.redis)
        
        async with lock.acquire(f"daily:{user_id}"):
            uow = UnitOfWork(self.session_factory)
            
            async with uow:
                user_repo = UserRepository(uow.session)
                bank_repo = BankRepository(uow.session)
                tx_repo = TransactionRepository(uow.session)
                
                user, _ = await user_repo.get_or_create(
                    user_id, username, first_name, is_bot=is_bot, with_lock=True
                )
                
                if user.is_banned:
                    return {"success": False, "error": "banned"}
                
                today = datetime.utcnow().date()
                
                existing = await uow.session.execute(
                    select(DailyClaim)
                    .where(DailyClaim.user_id == user_id)
                    .where(DailyClaim.claim_date == today)
                )
                if existing.scalar_one_or_none():
                    now = datetime.utcnow()
                    tomorrow = datetime.combine(
                        today + timedelta(days=1),
                        datetime.min.time()
                    )
                    delta = tomorrow - now
                    hours, remainder = divmod(int(delta.total_seconds()), 3600)
                    minutes, _ = divmod(remainder, 60)
                    
                    time_str = f"через {hours} ч. {minutes} мин."
                    raise DailyAlreadyClaimedError(time_str)
                
                yesterday = today - timedelta(days=1)
                if user.last_daily and user.last_daily.date() == yesterday:
                    user.daily_streak += 1
                elif user.last_daily and user.last_daily.date() == today:
                    pass
                else:
                    user.daily_streak = 1
                
                user.last_daily = datetime.utcnow()
                
                xp_reward = DAILY_BASE_XP
                coins_reward = DAILY_BASE_COINS
                
                bonus_xp = 0
                bonus_coins = 0
                
                for streak_days, (b_xp, b_coins) in DAILY_STREAK_BONUSES.items():
                    if user.daily_streak >= streak_days:
                        bonus_xp = b_xp
                        bonus_coins = b_coins
                
                total_xp = xp_reward + bonus_xp
                total_coins = coins_reward + bonus_coins
                
                bank_balance = await bank_repo.get_balance()
                if bank_balance < total_coins:
                    total_coins = min(total_coins, int(bank_balance))
                
                if total_coins > 0:
                    await bank_repo.withdraw(total_coins)
                
                user.xp += total_xp
                user.coins += total_coins
                
                await tx_repo.create(
                    user_id=user.id,
                    tx_type=TransactionType.DAILY_BONUS.value,
                    xp_change=total_xp,
                    coins_change=total_coins,
                    description=f"Daily bonus, streak {user.daily_streak}"
                )
                
                claim = DailyClaim(
                    user_id=user.id,
                    claim_date=today,
                    xp_received=total_xp,
                    coins_received=int(total_coins),
                    streak_at_claim=user.daily_streak,
                )
                uow.session.add(claim)
                
                await uow.commit()
                
                return {
                    "success": True,
                    "xp": xp_reward,
                    "coins": coins_reward,
                    "bonus_xp": bonus_xp,
                    "bonus_coins": bonus_coins,
                    "total_xp": total_xp,
                    "total_coins": total_coins,
                    "streak": user.daily_streak,
                }

    async def can_claim(self, user_id: int) -> tuple[bool, Optional[str]]:
        """Проверить, может ли пользователь получить бонус."""
        uow = UnitOfWork(self.session_factory)
        
        async with uow:
            today = datetime.utcnow().date()
            
            existing = await uow.session.execute(
                select(DailyClaim)
                .where(DailyClaim.user_id == user_id)
                .where(DailyClaim.claim_date == today)
            )
            
            if existing.scalar_one_or_none():
                now = datetime.utcnow()
                tomorrow = datetime.combine(
                    today + timedelta(days=1),
                    datetime.min.time()
                )
                delta = tomorrow - now
                hours, remainder = divmod(int(delta.total_seconds()), 3600)
                minutes, _ = divmod(remainder, 60)
                return False, f"через {hours} ч. {minutes} мин."
            
            return True, None