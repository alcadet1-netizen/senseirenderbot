"""
👤 Репозиторий пользователей.
"""

from typing import List, Optional

from sqlalchemy import desc, select, update, func
from sqlalchemy.orm import load_only
from sqlalchemy.ext.asyncio import AsyncSession

from src.infra.database.models import User


class UserRepository:
    """Репозиторий для работы с пользователями."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, user_id: int) -> Optional[User]:
        """Получить пользователя по ID."""
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_for_update(self, user_id: int) -> Optional[User]:
        """Получить пользователя по ID с блокировкой строки (для транзакций)."""
        result = await self.session.execute(
            select(User).where(User.id == user_id).with_for_update()
        )
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> Optional[User]:
        """Получить пользователя по username."""
        username = username.lstrip("@")
        result = await self.session.execute(
            select(User).where(func.lower(User.username) == func.lower(username))
        )
        return result.scalar_one_or_none()

    async def get_or_create(
        self,
        user_id: int,
        username: Optional[str] = None,
        first_name: str = "",
        last_name: Optional[str] = None,
        is_bot: bool = False,
        with_lock: bool = False
    ) -> tuple[User, bool]:
        """Получить или создать пользователя."""
        if with_lock:
            user = await self.get_for_update(user_id)
        else:
            user = await self.get_by_id(user_id)
            
        created = False
        
        if user is None:
            user = User(
                id=user_id,
                username=username,
                first_name=first_name or "",
                last_name=last_name,
                is_bot=is_bot,
            )
            self.session.add(user)
            await self.session.flush()
            created = True
        else:
            if username and user.username != username:
                user.username = username
            if first_name and user.first_name != first_name:
                user.first_name = first_name
            if last_name and user.last_name != last_name:
                user.last_name = last_name
            if user.is_bot != is_bot:
                user.is_bot = is_bot
        
        return user, created

    async def update(self, user: User) -> User:
        """Обновить пользователя."""
        await self.session.flush()
        return user

    async def get_top_by_xp(self, limit: int = 10) -> List[User]:
        """Топ по XP."""
        result = await self.session.execute(
            select(User)
            .where(User.is_banned == False)
            .order_by(desc(User.xp))
            .limit(limit)
            .options(load_only(User.id, User.username, User.first_name, User.xp))
        )
        return list(result.scalars().all())

    async def get_top_by_coins(self, limit: int = 10) -> List[User]:
        """Топ по монетам."""
        result = await self.session.execute(
            select(User)
            .where(User.is_banned == False)
            .order_by(desc(User.coins))
            .limit(limit)
            .options(load_only(User.id, User.username, User.first_name, User.coins))
        )
        return list(result.scalars().all())

    async def get_top_by_messages(self, limit: int = 10) -> List[User]:
        """Топ по сообщениям."""
        result = await self.session.execute(
            select(User)
            .where(User.is_banned == False)
            .order_by(desc(User.messages_count))
            .limit(limit)
            .options(load_only(User.id, User.username, User.first_name, User.messages_count))
        )
        return list(result.scalars().all())

    async def get_top_by_streak(self, limit: int = 10) -> List[User]:
        """Топ по страйку."""
        result = await self.session.execute(
            select(User)
            .where(User.is_banned == False)
            .order_by(desc(User.daily_streak))
            .limit(limit)
            .options(load_only(User.id, User.username, User.first_name, User.daily_streak))
        )
        return list(result.scalars().all())

    async def get_top_by_katana(self, limit: int = 10, offset: int = 0) -> List[User]:
        """Топ по длине катаны."""
        result = await self.session.execute(
            select(User)
            .where(User.is_banned == False)
            .where(User.is_bot == False)
            .where(User.has_katana == True)
            .order_by(desc(User.katana_length))
            .limit(limit)
            .offset(offset)
            .options(load_only(User.id, User.username, User.first_name, User.katana_length))
        )
        return list(result.scalars().all())

    async def count_with_katana(self) -> int:
        """Подсчитать пользователей с катаной."""
        result = await self.session.execute(
            select(func.count(User.id))
            .where(User.is_banned == False)
            .where(User.is_bot == False)
            .where(User.has_katana == True)
        )
        return result.scalar() or 0

    async def get_active_users(self, since_hours: int = 720, limit: int = 10000) -> List[User]:
        """Получить активных пользователей."""
        from datetime import datetime, timedelta
        
        since = datetime.now() - timedelta(hours=since_hours)
        
        result = await self.session.execute(
            select(User)
            .where(User.is_banned == False)
            .where(User.updated_at >= since)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_all_for_broadcast(self) -> List[User]:
        """Получить всех пользователей для рассылки."""
        result = await self.session.execute(
            select(User)
            .where(User.is_banned == False)
            .where(User.can_receive_broadcast == True)
        )
        return list(result.scalars().all())

    async def get_banned_users(self) -> List[User]:
        """Получить забаненных пользователей."""
        result = await self.session.execute(
            select(User).where(User.is_banned == True)
        )
        return list(result.scalars().all())

    async def ban_user(self, user_id: int, reason: str = "") -> bool:
        """Забанить пользователя."""
        result = await self.session.execute(
            update(User)
            .where(User.id == user_id)
            .values(is_banned=True, ban_reason=reason)
        )
        return result.rowcount > 0

    async def unban_user(self, user_id: int) -> bool:
        """Разбанить пользователя."""
        result = await self.session.execute(
            update(User)
            .where(User.id == user_id)
            .values(is_banned=False, ban_reason=None)
        )
        return result.rowcount > 0

    async def unban_all_users(self) -> int:
        """Разбанить всех пользователей."""
        result = await self.session.execute(
            update(User)
            .where(User.is_banned == True)
            .values(is_banned=False, ban_reason=None)
        )
        return result.rowcount

    async def count_all(self) -> int:
        """Подсчитать всех пользователей."""
        result = await self.session.execute(
            select(func.count(User.id))
        )
        return result.scalar() or 0

    async def reset_season_data(self, keep_katana: bool = True) -> int:
        """Сброс сезонных данных."""
        values = {
            "xp": 0,
            "coins": 0.0,
            "messages_count": 0,
            "daily_streak": 0,
            "last_daily": None,
        }
        if not keep_katana:
            values["has_katana"] = False
        
        result = await self.session.execute(
            update(User).values(**values)
        )
        return result.rowcount

    async def get_random_user(self) -> Optional[User]:
        """Получить случайного пользователя."""
        result = await self.session.execute(
            select(User)
            .where(User.is_banned == False)
            .order_by(func.random())
            .limit(1)
        )
        return result.scalar_one_or_none()
