"""
👤 Сервис пользователей.
"""

from typing import List, Optional

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.domain.repositories import (
    AchievementRepository,
    TicketRepository,
    UserRepository,
    BankRepository,
    TransactionRepository,
)
from src.infra.database.models import TransactionType
from src.infra.database.uow import UnitOfWork
from src.infra.redis.cache import CacheManager
from src.services.level_service import LevelService


class UserService:
    """Сервис для работы с пользователями."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession], redis: Redis):
        self.session_factory = session_factory
        self.cache_manager = CacheManager(redis)
        self.level_service = LevelService()

    async def get_profile(self, user_id: int) -> Optional[dict]:
        """Получить профиль пользователя (кэшируется на 1 минуту)."""
        async def factory():
            uow = UnitOfWork(self.session_factory)
            
            async with uow:
                user_repo = UserRepository(uow.session)
                ticket_repo = TicketRepository(uow.session)
                achievement_repo = AchievementRepository(uow.session)
                
                user = await user_repo.get_by_id(user_id)
                if not user:
                    return None
                
                tickets_count = await ticket_repo.count_user_tickets(user_id)
                achievements_count = await achievement_repo.count_user_achievements(user_id)
                
                # Check for special roles based on achievements
                role = None
                if await achievement_repo.has_achievement(user_id, "duel_master"):
                    role = "Ронин"
                
                level = self.level_service.get_level(user.xp)
                level_name = self.level_service.get_level_name(level)
                xp_next = self.level_service.get_xp_for_next_level(level)
                
                return {
                    "id": user.id,
                    "username": user.username or user.first_name or f"User {user.id}",
                    "xp": user.xp,
                    "level": level,
                    "level_name": level_name,
                    "xp_next": xp_next,
                    "coins": user.coins,
                    "tickets": tickets_count,
                    "messages": user.messages_count,
                    "streak": user.daily_streak,
                    "has_katana": user.has_katana,
                    "katana_length": user.katana_length,
                    "achievements_count": achievements_count,
                    "wins": user.wins,
                    "losses": user.losses,
                    "is_banned": user.is_banned,
                    "created_at": user.created_at.isoformat() if user.created_at else None,
                    "referrer_id": user.referrer_id,
                    "referral_count": user.referral_count,
                    "role": role,
                }

        return await self.cache_manager.get_or_set(
            f"user:profile:{user_id}",
            factory,
            ttl=60
        )

    async def get_or_create(
        self,
        user_id: int,
        username: Optional[str] = None,
        first_name: str = "",
        last_name: Optional[str] = None,
        is_bot: bool = False
    ) -> dict:
        """Получить или создать пользователя."""
        uow = UnitOfWork(self.session_factory)
        
        async with uow:
            user_repo = UserRepository(uow.session)
            user, created = await user_repo.get_or_create(
                user_id, username, first_name, last_name, is_bot=is_bot
            )
            await uow.commit()
            
            return {
                "user": user,
                "created": created,
            }

    async def get_user_by_username(self, username: str) -> Optional[dict]:
        """Получить пользователя по username."""
        uow = UnitOfWork(self.session_factory)
        
        async with uow:
            user_repo = UserRepository(uow.session)
            user = await user_repo.get_by_username(username)
            
            if not user:
                return None
                
            return {
                "id": user.id,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "is_banned": user.is_banned
            }

    async def get_random_user(self) -> Optional[dict]:
        """Получить случайного пользователя."""
        uow = UnitOfWork(self.session_factory)
        
        async with uow:
            user_repo = UserRepository(uow.session)
            user = await user_repo.get_random_user()
            
            if not user:
                return None
                
            return {
                "id": user.id,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name
            }

    async def process_referral(self, user_id: int, referrer_id: int) -> dict:
        """Обработать реферальную систему."""
        uow = UnitOfWork(self.session_factory)
        
        async with uow:
            user_repo = UserRepository(uow.session)
            bank_repo = BankRepository(uow.session)
            tx_repo = TransactionRepository(uow.session)
            
            # 1. Проверяем пользователя (реферала)
            user = await user_repo.get_for_update(user_id)
            if not user:
                return {"success": False, "error": "User not found"}
            
            # 2. Проверяем, есть ли уже реферер
            if user.referrer_id:
                return {"success": False, "error": "Already has referrer"}
            
            # 3. Проверяем само-реферал
            if user_id == referrer_id:
                return {"success": False, "error": "Self referral"}
                
            # 4. Проверяем реферера
            referrer = await user_repo.get_for_update(referrer_id)
            if not referrer:
                return {"success": False, "error": "Referrer not found"}
            
            # 5. Устанавливаем связь
            user.referrer_id = referrer.id
            referrer.referral_count += 1
            
            # 6. Награды
            # Реферер: 200 монет, 100 XP
            referrer_coins = 200.0
            referrer_xp = 100
            
            referrer.coins += referrer_coins
            referrer.xp += referrer_xp
            
            # Реферал: 100 монет, 100 XP
            referral_coins = 100.0
            referral_xp = 100
            
            user.coins += referral_coins
            user.xp += referral_xp
            
            # 7. Транзакции
            # Списываем общую сумму монет из банка
            total_coins = referrer_coins + referral_coins
            await bank_repo.withdraw(total_coins)
            
            # Логируем для реферера
            await tx_repo.create(
                user_id=referrer.id,
                tx_type=TransactionType.REFERRAL_BONUS.value,
                coins_change=referrer_coins,
                xp_change=referrer_xp,
                description=f"Referral reward for user {user.username or user_id}"
            )
            
            # Логируем для реферала
            await tx_repo.create(
                user_id=user.id,
                tx_type=TransactionType.REFERRAL_BONUS.value,
                coins_change=referral_coins,
                xp_change=referral_xp,
                description=f"Referral bonus from user {referrer.username or referrer_id}"
            )
            
            await uow.commit()
            
            return {
                "success": True,
                "referrer_id": referrer.id,
                "referrer_username": referrer.username,
                "referrer_reward": {"coins": referrer_coins, "xp": referrer_xp},
                "referral_reward": {"coins": referral_coins, "xp": referral_xp}
            }

    async def get_active_users(self, since_hours: int = 720, limit: int = 10000) -> List[dict]:
        """Получить активных пользователей (кэшируется на 1 час)."""
        async def factory():
            uow = UnitOfWork(self.session_factory)
            async with uow:
                user_repo = UserRepository(uow.session)
                users = await user_repo.get_active_users(since_hours=since_hours, limit=limit)
                return [
                    {
                        "user_id": u.id,
                        "username": u.username,
                        "first_name": u.first_name,
                    }
                    for u in users
                ]

        return await self.cache_manager.get_or_set(
            f"users:active:{since_hours}:{limit}",
            factory,
            ttl=3600
        )

    async def get_top_by_xp(self, limit: int = 10) -> List[dict]:
        """Топ по XP (кэшируется на 5 минут)."""
        async def factory():
            uow = UnitOfWork(self.session_factory)
            async with uow:
                user_repo = UserRepository(uow.session)
                users = await user_repo.get_top_by_xp(limit)
                return [
                    {
                        "user_id": u.id,
                        "username": u.username or u.first_name or f"User {u.id}",
                        "xp": u.xp,
                        "level": self.level_service.get_level(u.xp),
                    }
                    for u in users
                ]

        return await self.cache_manager.get_or_set(
            f"top:xp:{limit}",
            factory,
            ttl=300
        )

    async def get_top_by_coins(self, limit: int = 10) -> List[dict]:
        """Топ по монетам (кэшируется на 5 минут)."""
        async def factory():
            uow = UnitOfWork(self.session_factory)
            async with uow:
                user_repo = UserRepository(uow.session)
                users = await user_repo.get_top_by_coins(limit)
                return [
                    {
                        "user_id": u.id,
                        "username": u.username or u.first_name or f"User {u.id}",
                        "coins": u.coins,
                    }
                    for u in users
                ]
                
        return await self.cache_manager.get_or_set(
            f"top:coins:{limit}",
            factory,
            ttl=300
        )

    async def get_top_by_messages(self, limit: int = 10) -> List[dict]:
        """Топ по сообщениям (кэшируется на 5 минут)."""
        async def factory():
            uow = UnitOfWork(self.session_factory)
            async with uow:
                user_repo = UserRepository(uow.session)
                users = await user_repo.get_top_by_messages(limit)
                return [
                    {
                        "user_id": u.id,
                        "username": u.username or u.first_name or f"User {u.id}",
                        "messages": u.messages_count,
                    }
                    for u in users
                ]
                
        return await self.cache_manager.get_or_set(
            f"top:messages:{limit}",
            factory,
            ttl=300
        )

    async def get_top_by_tickets(self, limit: int = 10) -> List[dict]:
        """Топ по билетам (кэшируется на 5 минут)."""
        async def factory():
            uow = UnitOfWork(self.session_factory)
            async with uow:
                ticket_repo = TicketRepository(uow.session)
                return await ticket_repo.get_top_by_tickets(limit)
                
        return await self.cache_manager.get_or_set(
            f"top:tickets:{limit}",
            factory,
            ttl=300
        )

    async def get_ticket_holders_paginated(self, page: int = 0, page_size: int = 20) -> dict:
        """Пагинированный список держателей билетов (без кэша)."""
        uow = UnitOfWork(self.session_factory)
        async with uow:
            ticket_repo = TicketRepository(uow.session)
            offset = max(0, page) * max(1, page_size)
            items, total = await ticket_repo.get_ticket_holders_paginated(offset, page_size)
            return {"items": items, "total": total}

    async def get_top_by_streak(self, limit: int = 10) -> List[dict]:
        """Топ по страйку (кэшируется на 5 минут)."""
        async def factory():
            uow = UnitOfWork(self.session_factory)
            async with uow:
                user_repo = UserRepository(uow.session)
                users = await user_repo.get_top_by_streak(limit)
                return [
                    {
                        "user_id": u.id,
                        "username": u.username or u.first_name or f"User {u.id}",
                        "streak": u.daily_streak,
                    }
                    for u in users
                ]
                
        return await self.cache_manager.get_or_set(
            f"top:streak:{limit}",
            factory,
            ttl=300
        )

    async def get_top_by_katana(self, limit: int = 10, offset: int = 0) -> dict:
        """Топ по длине катаны (кэшируется на 1 минуту для каждой страницы)."""
        async def factory():
            uow = UnitOfWork(self.session_factory)
            async with uow:
                user_repo = UserRepository(uow.session)
                users = await user_repo.get_top_by_katana(limit, offset)
                total = await user_repo.count_with_katana()
                
                items = [
                    {
                        "user_id": u.id,
                        "username": u.username or u.first_name or f"User {u.id}",
                        "katana_length": u.katana_length,
                    }
                    for u in users
                ]
                return {"items": items, "total": total}
                
        return await self.cache_manager.get_or_set(
            f"top:katana:{limit}:{offset}",
            factory,
            ttl=60
        )

    async def get_all_for_broadcast(self) -> List[int]:
        """Получить ID всех пользователей для рассылки."""
        # Рассылка редко нужна, но список может быть большим. Не кэшируем или кэшируем ненадолго.
        # Лучше брать свежий.
        uow = UnitOfWork(self.session_factory)
        async with uow:
            user_repo = UserRepository(uow.session)
            users = await user_repo.get_all_for_broadcast()
            return [u.id for u in users]

    async def admin_add_katana(self, user_id: int, length: float, admin_id: int) -> dict:
        """Админ: выдать катану."""
        uow = UnitOfWork(self.session_factory)
        
        async with uow:
            user_repo = UserRepository(uow.session)
            tx_repo = TransactionRepository(uow.session)
            
            user = await user_repo.get_for_update(user_id)
            if not user:
                return {"success": False, "error": "Пользователь не найден"}
            
            user.has_katana = True
            user.katana_length = length
            
            # Лог транзакции
            await tx_repo.create(
                user_id=user.id,
                tx_type=TransactionType.ADMIN_GRANT.value,
                description=f"Admin {admin_id} set katana length to {length}"
            )
            
            await uow.commit()
            
            # Инвалидируем кэш
            await self.cache_manager.delete(f"user:profile:{user_id}")
            
            return {"success": True}
