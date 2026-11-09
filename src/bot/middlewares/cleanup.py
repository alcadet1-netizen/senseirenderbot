import logging
import time
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message
from src.bot.middlewares.comment_campaign import campaign_message_deleted

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

        # Delete only the user's invocation, never the bot's result. Exact
        # aliases must not match ordinary conversation mentioning a hedgehog.
        daily_aliases = {"ежа", "фарм", "фармить", "фарма", "ферма"}
        if (isinstance(event, Message) and event.text
                and (event.text.startswith('/') or (
                    event.from_user and not event.from_user.is_bot
                    and event.text.lower() in daily_aliases))):
            logger.info(f"[CLEANUP] Attempting to delete command message: {event.text}")
            try:
                await event.delete()
                await campaign_message_deleted(data.get("container"), event.chat.id, event.message_id)
                logger.info(f"[CLEANUP] Deleted command message")
            except Exception as e:
                logger.error(f"[CLEANUP] Failed to delete command message: {e}")

        duration_ms = (time.time() - start) * 1000
        logger.info(f"[CLEANUP] Finished processing message in {duration_ms:.2f} ms")
        return result
