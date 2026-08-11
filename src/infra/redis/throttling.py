"""
⏱️ Throttling через Redis.
"""

from redis.asyncio import Redis


class ThrottleManager:
    """Управление throttling через Redis."""

    def __init__(self, redis: Redis):
        self.redis = redis
        self.prefix = "throttle:"

    async def is_throttled(
        self,
        key: str,
        limit_seconds: int,
        scope: str = "default"
    ) -> bool:
        """Проверить, заблокирован ли ключ."""
        full_key = f"{self.prefix}{scope}:{key}"
        exists = await self.redis.exists(full_key)
        return bool(exists)

    async def throttle(
        self,
        key: str,
        limit_seconds: int,
        scope: str = "default"
    ) -> bool:
        """
        Попытаться установить throttle.
        Возвращает True если успешно, False если заблокирован.
        """
        full_key = f"{self.prefix}{scope}:{key}"
        result = await self.redis.set(full_key, "1", ex=limit_seconds, nx=True)
        return result is not None

    async def get_ttl(self, key: str, scope: str = "default") -> int:
        """Получить оставшееся время блокировки."""
        full_key = f"{self.prefix}{scope}:{key}"
        ttl = await self.redis.ttl(full_key)
        return max(0, ttl)

    async def clear(self, key: str, scope: str = "default") -> None:
        """Снять throttle."""
        full_key = f"{self.prefix}{scope}:{key}"
        await self.redis.delete(full_key)