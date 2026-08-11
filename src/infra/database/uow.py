"""
🔄 Unit of Work паттерн для атомарных транзакций.
"""

from types import TracebackType
from typing import Optional, Type

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class UnitOfWork:
    """Unit of Work для управления транзакциями."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory
        self._session: Optional[AsyncSession] = None

    @property
    def session(self) -> AsyncSession:
        """Получить текущую сессию."""
        if self._session is None:
            raise RuntimeError("UoW not started. Use 'async with uow:'")
        return self._session

    async def __aenter__(self) -> "UnitOfWork":
        """Начало транзакции."""
        self._session = self._session_factory()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        """Завершение транзакции."""
        if exc_type is not None:
            await self.rollback()
        await self.close()

    async def commit(self) -> None:
        """Коммит транзакции."""
        if self._session:
            await self._session.commit()

    async def rollback(self) -> None:
        """Откат транзакции."""
        if self._session:
            await self._session.rollback()

    async def close(self) -> None:
        """Закрытие сессии."""
        if self._session:
            await self._session.close()
            self._session = None