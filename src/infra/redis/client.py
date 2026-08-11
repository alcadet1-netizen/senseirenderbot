"""
🔴 Redis клиент.
"""

from typing import Optional

import redis.asyncio as redis

from src.core.config import settings


class RedisClient:
    """Обёртка над Redis клиентом."""

    def __init__(self, url: Optional[str] = None):
        self.url = url or settings.redis_url
        self._client: Optional[redis.Redis] = None

    async def connect(self) -> redis.Redis:
        """Подключение к Redis."""
        if self._client is None:
            self._client = redis.from_url(
                self.url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._client

    async def disconnect(self) -> None:
        """Отключение от Redis."""
        if self._client:
            await self._client.close()
            self._client = None

    @property
    def client(self) -> redis.Redis:
        """Получить клиент."""
        if self._client is None:
            raise RuntimeError("Redis not connected. Call connect() first.")
        return self._client


redis_client = RedisClient()


async def get_redis() -> redis.Redis:
    """Получить Redis клиент."""
    return await redis_client.connect()