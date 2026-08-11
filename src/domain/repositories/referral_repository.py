from typing import Optional, List, Tuple
from sqlalchemy import select, func, desc, case
from sqlalchemy.ext.asyncio import AsyncSession
from src.domain.repositories.base import BaseRepository
from src.infra.database.models.referral import Referral
from src.infra.database.models.user import User
from src.domain.entities.referral import ReferralStats

class ReferralRepository(BaseRepository[Referral, int]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Referral)

    async def get_referrer_id(self, user_id: int) -> Optional[int]:
        """Получить ID реферера (того, кто пригласил user_id)."""
        result = await self.session.execute(
            select(Referral.referrer_id)
            .where(Referral.referred_id == user_id, Referral.level == 1)
        )
        return result.scalar_one_or_none()

    async def is_already_referred(self, user_id: int) -> bool:
        """Проверить, был ли пользователь уже приглашен кем-то."""
        result = await self.session.execute(
            select(Referral.id).where(Referral.referred_id == user_id).limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def get_stats(self, user_id: int) -> ReferralStats:
        """Получить статистику рефералов."""
        stats = ReferralStats(user_id=user_id)
        
        # Level 1 stats
        # count, sum(coins), sum(xp), sum(active)
        q1 = select(
            func.count(Referral.id),
            func.sum(Referral.coins_earned),
            func.sum(Referral.xp_earned),
            func.sum(case((Referral.is_active == True, 1), else_=0))
        ).where(Referral.referrer_id == user_id, Referral.level == 1)
        
        row1 = (await self.session.execute(q1)).fetchone()
        if row1:
            stats.level_1_count = row1[0] or 0
            stats.total_coins_earned = float(row1[1] or 0.0)
            stats.total_xp_earned = row1[2] or 0
            stats.level_1_active = row1[3] or 0

        # Level 2 stats
        q2 = select(
            func.count(Referral.id),
            func.sum(Referral.coins_earned),
            func.sum(Referral.xp_earned),
            func.sum(case((Referral.is_active == True, 1), else_=0))
        ).where(Referral.referrer_id == user_id, Referral.level == 2)
        
        row2 = (await self.session.execute(q2)).fetchone()
        if row2:
            stats.level_2_count = row2[0] or 0
            stats.total_coins_earned += float(row2[1] or 0.0)
            stats.total_xp_earned += row2[2] or 0
            stats.level_2_active = row2[3] or 0
            
        return stats

    async def get_referrals_list(self, user_id: int, level: int = 1, limit: int = 10) -> List[Referral]:
        result = await self.session.execute(
            select(Referral)
            .where(Referral.referrer_id == user_id, Referral.level == level)
            .order_by(desc(Referral.created_at))
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_top_referrers(self, limit: int = 10) -> List[Tuple[int, int, Optional[str], str]]:
        """Топ рефереров по количеству приглашенных (Level 1). Возвращает (referrer_id, count, username, first_name)."""
        result = await self.session.execute(
            select(Referral.referrer_id, func.count(Referral.id).label('count'), User.username, User.first_name)
            .join(User, User.id == Referral.referrer_id)
            .where(Referral.level == 1)
            .group_by(Referral.referrer_id, User.username, User.first_name)
            .order_by(desc('count'))
            .limit(limit)
        )
        return result.all()
