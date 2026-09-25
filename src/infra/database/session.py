"""
🔌 Настройка асинхронной сессии SQLAlchemy.
"""

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.core.config import settings


def create_engine() -> AsyncEngine:
    """Создание асинхронного движка."""
    return create_async_engine(
        settings.database_url,
        echo=settings.database_echo,
        pool_size=20,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=3600,  # Recycle connections every hour to prevent staleness
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Создание фабрики сессий."""
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


engine = create_engine()
session_factory = create_session_factory(engine)


async def get_session() -> AsyncSession:
    """Получить сессию."""
    async with session_factory() as session:
        yield session