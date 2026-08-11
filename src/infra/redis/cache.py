"""
💾 Кэширование через Redis.
"""

import asyncio
import json
from typing import Any, Callable, Optional

from redis.asyncio import Redis


class CacheManager:
    """Управление кэшем через Redis."""

    def __init__(self, redis: Redis):
        self.redis = redis
        self.prefix = "cache:"

    async def get(self, key: str) -> Optional[Any]:
        """Получить значение из кэша."""
        full_key = f"{self.prefix}{key}"
        data = await self.redis.get(full_key)
        if data:
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                return data
        return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int = 300
    ) -> None:
        """Установить значение в кэш."""
        full_key = f"{self.prefix}{key}"
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)
        await self.redis.set(full_key, value, ex=ttl)

    async def delete(self, key: str) -> None:
        """Удалить значение из кэша."""
        full_key = f"{self.prefix}{key}"
        await self.redis.delete(full_key)

    async def delete_pattern(self, pattern: str) -> int:
        """Удалить все ключи по паттерну."""
        full_pattern = f"{self.prefix}{pattern}"
        keys = []
        async for key in self.redis.scan_iter(match=full_pattern):
            keys.append(key)
        
        if keys:
            return await self.redis.delete(*keys)
        return 0

    async def get_or_set(
        self,
        key: str,
        factory: Callable,
        ttl: int = 300
    ) -> Any:
        """Получить из кэша или вычислить и сохранить."""
        value = await self.get(key)
        if value is None:
            if asyncio.iscoroutinefunction(factory):
                value = await factory()
            else:
                value = factory()
            await self.set(key, value, ttl)
        return value