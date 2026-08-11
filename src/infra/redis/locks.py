"""
🔒 Распределённые блокировки через Redis.
"""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator
import uuid

from redis.asyncio import Redis


class DistributedLock:
    """Распределённая блокировка через Redis."""

    def __init__(self, redis: Redis):
        self.redis = redis
        self.prefix = "lock:"

    @asynccontextmanager
    async def acquire(
        self,
        key: str,
        timeout: int = 10,
        retry_interval: float = 0.1,
        max_retries: int = 50
    ) -> AsyncGenerator[bool, None]:
        """Асинхронный контекстный менеджер для блокировки."""
        full_key = f"{self.prefix}{key}"
        lock_id = str(uuid.uuid4())
        acquired = False
        
        for _ in range(max_retries):
            result = await self.redis.set(full_key, lock_id, ex=timeout, nx=True)
            if result:
                acquired = True
                break
            await asyncio.sleep(retry_interval)
        
        try:
            yield acquired
        finally:
            if acquired:
                current = await self.redis.get(full_key)
                if current == lock_id:
                    await self.redis.delete(full_key)

    async def is_locked(self, key: str) -> bool:
        """Проверить, заблокирован ли ресурс."""
        full_key = f"{self.prefix}{key}"
        return bool(await self.redis.exists(full_key))