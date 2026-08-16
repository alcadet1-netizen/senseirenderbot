import logging
import time
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message

logger = logging.getLogger(__name__)

class CommandCleanupMiddleware(BaseMiddleware):
    """Middleware для удаления сообщений с командами."""

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        start = time.time()
        logger.info(f"[CLEANUP] Start processing message from user {event.from_user.id if event.from_user else 'Unknown'}")
        # Выполняем хендлер
        result = await handler(event, data)

        # Если это сообщение и оно начинается с /, пытаемся удалить
        if isinstance(event, Message) and event.text and event.text.startswith('/'):
            logger.info(f"[CLEANUP] Attempting to delete command message: {event.text}")
            try:
                await event.delete()
                logger.info(f"[CLEANUP] Deleted command message")
            except Exception as e:
                logger.error(f"[CLEANUP] Failed to delete command message: {e}")

        duration_ms = (time.time() - start) * 1000
        logger.info(f"[CLEANUP] Finished processing message in {duration_ms:.2f} ms")
        return result
