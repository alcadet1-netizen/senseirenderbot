"""
🏛️ Базовый репозиторий.
"""

from abc import ABC
from typing import Generic, List, Optional, TypeVar, Type

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")
ID = TypeVar("ID")

class BaseRepository(ABC, Generic[T, ID]):
    """Базовый репозиторий с реализацией CRUD."""

    def __init__(self, session: AsyncSession, model: Type[T]):
        self.session = session
        self.model = model

    async def get_by_id(self, id: ID) -> Optional[T]:
        """Получить сущность по ID."""
        # Предполагаем, что у модели есть поле id
        result = await self.session.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()

    async def get_all(self, limit: int = 100, offset: int = 0) -> List[T]:
        """Получить все сущности."""
        result = await self.session.execute(
            select(self.model).limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    async def add(self, entity: T) -> T:
        """Добавить сущность."""
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def update(self, entity: T) -> T:
        """Обновить сущность."""
        # В SQLAlchemy ORM изменения отслеживаются автоматически для привязанных объектов.
        await self.session.flush()
        return entity

    async def delete(self, id: ID) -> bool:
        """Удалить сущность."""
        result = await self.session.execute(
            delete(self.model).where(self.model.id == id)
        )
        return result.rowcount > 0
