"""
🛡️ Сервис модерации.
"""

from typing import List, Optional
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.domain.repositories import BankRepository, TransactionRepository, UserRepository
from src.infra.database.models import TransactionType, MutedUser
from src.infra.database.uow import UnitOfWork


class ModerationService:
    """Сервис для модерации пользователей."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self.session_factory = session_factory
        # Кэш для быстрой проверки: user_id -> muted_until
        # Если muted_until is None, то мьют вечный.
        self._muted_cache: dict[int, Optional[datetime]] = {}

    async def load_muted_users_cache(self):
        """Загрузить кэш замьюченных пользователей при старте."""
        async with self.session_factory() as session:
            result = await session.execute(select(MutedUser))
            self._muted_cache = {
                user.user_id: user.muted_until
                for user in result.scalars().all()
            }

    async def handle_user_left(self, user_id: int) -> dict:
        """Обработать выход пользователя (автобан и конфискация)."""
        return await self.ban_user(
            user_id=user_id,
            reason="Выход из чата (AutoBan)",
            confiscate_coins=True
        )

    async def ban_user(
        self,
        user_id: int,
        reason: str = "Нарушение правил",
        confiscate_coins: bool = True
    ) -> dict:
        """Забанить пользователя."""
        uow = UnitOfWork(self.session_factory)
        
        async with uow:
            user_repo = UserRepository(uow.session)
            
            user = await user_repo.get_by_id(user_id)
            if not user:
                return {"success": False, "error": "User not found"}
            
            if user.is_banned:
                return {"success": False, "error": "Already banned"}
            
            confiscated = 0.0
            if confiscate_coins and user.coins > 0:
                bank_repo = BankRepository(uow.session)
                tx_repo = TransactionRepository(uow.session)
                
                confiscated = user.coins
                user.coins = 0
                await bank_repo.deposit(confiscated)
                
                await tx_repo.create(
                    user_id=user.id,
                    tx_type=TransactionType.BAN_CONFISCATION.value,
                    coins_change=-confiscated,
                    description=f"Ban confiscation: {reason}"
                )
            
            user.is_banned = True
            user.ban_reason = reason
            
            await uow.commit()
            
            return {
                "success": True,
                "user_id": user.id,
                "username": user.username or user.first_name,
                "reason": reason,
                "confiscated": confiscated,
            }

    async def unban_user(self, user_id: int) -> dict:
        """Разбанить пользователя."""
        uow = UnitOfWork(self.session_factory)
        
        async with uow:
            user_repo = UserRepository(uow.session)
            
            success = await user_repo.unban_user(user_id)
            
            if success:
                await uow.commit()
                return {"success": True, "user_id": user_id}
            
            return {"success": False, "error": "User not found or not banned"}

    async def get_banned_users(self) -> List[dict]:
        """Получить список забаненных."""
        uow = UnitOfWork(self.session_factory)
        
        async with uow:
            user_repo = UserRepository(uow.session)
            users = await user_repo.get_banned_users()
            
            return [
                {
                    "user_id": u.id,
                    "username": u.username or u.first_name or f"User {u.id}",
                    "reason": u.ban_reason or "Не указана",
                }
                for u in users
            ]

    async def unban_all_users(self) -> dict:
        """Амнистия: разбанить всех пользователей."""
        uow = UnitOfWork(self.session_factory)
        async with uow:
            user_repo = UserRepository(uow.session)
            affected = await user_repo.unban_all_users()
            await uow.commit()
            return {"success": True, "affected": affected}

    async def mute_user(
        self,
        user_id: int,
        muted_by: int = None,
        reason: str = None,
        until: datetime = None
    ) -> dict:
        """Замьютить пользователя."""
        async with self.session_factory() as session:
            try:
                # Проверяем, не замьючен ли уже
                existing = await session.execute(
                    select(MutedUser).where(MutedUser.user_id == user_id)
                )
                if existing.scalar_one_or_none():
                    return {"success": False, "error": "Пользователь уже замьючен"}
                
                muted_user = MutedUser(
                    user_id=user_id,
                    muted_by=muted_by,
                    reason=reason,
                    muted_at=datetime.utcnow(),
                    muted_until=until
                )
                session.add(muted_user)
                await session.commit()
                
                # Обновляем кэш
                self._muted_cache[user_id] = until
                
                return {"success": True}
            except Exception as e:
                await session.rollback()
                return {"success": False, "error": str(e)}

    async def unmute_user(self, user_id: int) -> dict:
        """Снять мьют с пользователя."""
        async with self.session_factory() as session:
            try:
                result = await session.execute(
                    delete(MutedUser).where(MutedUser.user_id == user_id)
                )
                await session.commit()
                
                if result.rowcount == 0:
                    return {"success": False, "error": "Пользователь не был замьючен"}
                
                # Обновляем кэш
                self._muted_cache.pop(user_id, None)
                
                return {"success": True}
            except Exception as e:
                await session.rollback()
                return {"success": False, "error": str(e)}

    async def is_muted(self, user_id: int) -> bool:
        """Проверить, замьючен ли пользователь."""
        # Быстрая проверка через кэш
        if user_id not in self._muted_cache:
            return False
            
        until = self._muted_cache[user_id]
        if until and datetime.utcnow() > until:
            # Срок действия истек
            await self.unmute_user(user_id)
            return False
            
        return True

    async def get_muted_users(self) -> List[MutedUser]:
        """Получить список всех замьюченных пользователей."""
        async with self.session_factory() as session:
            result = await session.execute(select(MutedUser))
            return result.scalars().all()

    async def mute_user_by_username(
        self, 
        username: str, 
        hours: float = 0, 
        muted_by: int = None, 
        reason: str = None
    ) -> dict:
        """Замьютить пользователя по нику."""
        uow = UnitOfWork(self.session_factory)
        async with uow:
            user_repo = UserRepository(uow.session)
            user = await user_repo.get_by_username(username)
            if not user:
                return {"success": False, "error": "Пользователь не найден", "username": username}
            user_id = user.id
            
        until = None
        if hours > 0:
            until = datetime.utcnow() + timedelta(hours=hours)
            
        result = await self.mute_user(user_id, muted_by, reason, until)
        if result["success"]:
            result["username"] = user.username or user.first_name
        return result

    async def unmute_user_by_username(self, username: str) -> dict:
        """Снять мьют по нику."""
        uow = UnitOfWork(self.session_factory)
        async with uow:
            user_repo = UserRepository(uow.session)
            user = await user_repo.get_by_username(username)
            if not user:
                return {"success": False, "error": "Пользователь не найден", "username": username}
            user_id = user.id
            
        result = await self.unmute_user(user_id)
        if result["success"]:
            result["username"] = user.username or user.first_name
        return result
