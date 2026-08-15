"""
📢 Сервис рассылки.
"""

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Callable, List, Optional
from datetime import datetime, timezone

from src.core.config import settings
from src.infra.mongo.client import MongoClient
import logging

logger = logging.getLogger(__name__)


class MediaType(Enum):
    NONE = "none"
    PHOTO = "photo"
    GIF = "gif"
    VIDEO = "video"
    DOCUMENT = "document"


@dataclass
class BroadcastMessage:
    text: Optional[str] = None
    media_type: MediaType = MediaType.NONE
    media_id: Optional[str] = None

    def is_valid(self) -> bool:
        return bool(self.text) or (self.media_type != MediaType.NONE and self.media_id)


@dataclass
class BroadcastResult:
    total: int = 0
    success: int = 0
    failed: int = 0
    blocked: int = 0

    @property
    def success_rate(self) -> float:
        return (self.success / self.total * 100) if self.total > 0 else 0


class BroadcastService:
    """Сервис для рассылки сообщений."""

    def __init__(self, mongo_client: MongoClient):
        self.mongo_client = mongo_client
        self.db = mongo_client.database
        self.users = self.db.users
        self._pending: Optional[BroadcastMessage] = None

    async def get_users(self) -> List[int]:
        """Получить список пользователей для рассылки."""
        # Get all non-banned users (or all users? Original got all for broadcast)
        # We'll get all users that are not banned
        cursor = self.users.find({"is_banned": {"$ne": True}})
        users = await cursor.to_list(length=None)
        return [u["id"] for u in users]

    async def get_count(self) -> int:
        """Получить количество пользователей для рассылки."""
        return len(await self.get_users())

    def set_pending(self, msg: BroadcastMessage):
        self._pending = msg

    def get_pending(self) -> Optional[BroadcastMessage]:
        return self._pending

    def clear_pending(self):
        self._pending = None

    async def broadcast(
        self,
        message: BroadcastMessage,
        send_func: Callable,
        delay: float = 0.05,
        on_progress: Optional[Callable] = None
    ) -> BroadcastResult:
        """Рассылка сообщений."""
        user_ids = await self.get_users()
        result = BroadcastResult(total=len(user_ids))
        step = max(1, result.total // 10)

        for i, uid in enumerate(user_ids):
            try:
                if await send_func(uid, message):
                    result.success += 1
                else:
                    result.failed += 1
            except Exception as e:
                err = str(e).lower()
                if "blocked" in err or "deactivated" in err:
                    result.blocked += 1
                else:
                    result.failed += 1

            if on_progress and (i + 1) % step == 0:
                await on_progress(i + 1, result.total)
            await asyncio.sleep(delay)

        return result