"""
📊 Сервис статистики.
"""

from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.core.config import settings
from src.domain.repositories import BankRepository, TicketRepository, TransactionRepository, UserRepository
from src.infra.database.models import User
from src.infra.database.uow import UnitOfWork
from src.infra.redis.cache import CacheManager


class StatsService:
    """Сервис для сбора статистики."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        redis: Redis
    ):
        self.session_factory = session_factory
        self.cache = CacheManager(redis)

    async def get_admin_stats(self) -> dict:
        """Получить полную статистику для админа."""
        cache_key = "stats:admin"
        
        cached = await self.cache.get(cache_key)
        if cached:
            return cached
        
        uow = UnitOfWork(self.session_factory)
        
        async with uow:
            user_repo = UserRepository(uow.session)
            bank_repo = BankRepository(uow.session)
            tx_repo = TransactionRepository(uow.session)
            ticket_repo = TicketRepository(uow.session)
            
            total_users = await user_repo.count_all()
            bank_stats = await bank_repo.get_stats()
            circulation = await tx_repo.get_total_coins_in_circulation()
            total_tickets = await ticket_repo.get_total_active_tickets()
            tx_stats = await tx_repo.get_stats_by_type()
            
            result = await uow.session.execute(
                select(func.sum(User.messages_count))
            )
            total_messages = result.scalar() or 0
            
            stats = {
                "users": {"total": total_users},
                "bank": bank_stats,
                "circulation": circulation,
                "tickets": {"active": total_tickets},
                "messages": {"total": total_messages},
                "transactions": tx_stats,
            }
            
            await self.cache.set(cache_key, stats, ttl=60)
            
            return stats

    async def reset_new_season(self) -> dict:
        """Сброс сезона."""
        uow = UnitOfWork(self.session_factory)
        
        async with uow:
            user_repo = UserRepository(uow.session)
            ticket_repo = TicketRepository(uow.session)
            bank_repo = BankRepository(uow.session)
            
            tickets_burned = await ticket_repo.burn_all_tickets("season_reset")
            users_reset = await user_repo.reset_season_data(keep_katana=True)
            await bank_repo.reset_balance(settings.bank_initial_coins)
            
            await uow.commit()
            
            return {
                "success": True,
                "tickets_burned": tickets_burned,
                "users_reset": users_reset,
            }

    async def reset_sansara(self) -> dict:
        """Полный сброс."""
        return await self.reset_new_season()