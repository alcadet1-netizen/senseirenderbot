"""
⏱️ Middleware для обновления времени последней активности в чате.
"""

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message

from src.core.container import Container

class ChatActivityMiddleware(BaseMiddleware):
    """Middleware для отслеживания времени последнего сообщения в чате."""

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        if isinstance(event, Message):
            # Only track groups and supergroups
            if event.chat.type in ("group", "supergroup"):
                container: Container = data.get("container")
                if container:
                    # Обновляем время активности в фоне, чтобы не блокировать обработку
                    await container.chat_activity_service.update_activity(event.chat.id)
        
        return await handler(event, data)
