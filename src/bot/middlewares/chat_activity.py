"""
⏱️ Middleware для обновления времени последней активности в чате.
"""

import logging
import time
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message

from src.core.container import Container

logger = logging.getLogger(__name__)

class ChatActivityMiddleware(BaseMiddleware):
    """Middleware для отслеживания времени последнего сообщения в чате."""

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        start = time.time()
        logger.info(f"[CHAT_ACTIVITY] Start processing chat_id={event.chat.id}")
        if isinstance(event, Message):
            # Only track groups and supergroups
            if event.chat.type in ("group", "supergroup"):
                container: Container = data.get("container")
                if container:
                    # Обновляем время активности в фоне, чтобы не блокировать обработку
                    await container.chat_activity_service.update_activity(event.chat.id)
                    # Также обновляем активность для игры БАНЗАЙ
                    await container.banzai_service.update_user_activity(event.chat.id, event.from_user.id)
        duration_ms = (time.time() - start) * 1000
        logger.info(f"[CHAT_ACTIVITY] Finished processing chat_id={event.chat.id} in {duration_ms:.2f} ms")
        return await handler(event, data)
