"""
🛡️ Middleware модерации.
"""
from typing import Any, Awaitable, Callable, Dict
import logging

from aiogram import BaseMiddleware
from aiogram.types import Update, TelegramObject

from src.core.container import Container
from src.bot.middlewares.comment_campaign import campaign_message_deleted

logger = logging.getLogger(__name__)


class ModerationMiddleware(BaseMiddleware):
    """Middleware для автоматического удаления сообщений замьюченных пользователей."""

    def __init__(self, container: Container):
        self.container = container

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        message = (event.message or event.edited_message) if isinstance(event, Update) else None
        if (not message or message.chat.type not in ('group', 'supergroup') or
                not message.from_user or message.sender_chat or message.from_user.is_bot or
                message.successful_payment or message.new_chat_members or message.left_chat_member):
            return await handler(event, data)
        user_id = message.from_user.id
        container = self.container

        # Проверяем, замьючен ли пользователь
        try:
            is_muted = await container.moderation_service.is_muted(user_id)
            
            if is_muted:
                # Удаляем сообщение
                try:
                    await message.delete()
                    await campaign_message_deleted(container, message.chat.id, message.message_id)
                    logger.info(
                        f"Deleted message from muted user {user_id} "
                        f"in chat {message.chat.id}"
                    )
                except Exception as e:
                    logger.warning(f"Failed to delete message: {e}")
                
                # Не передаём дальше в хендлеры
                return None
        except Exception as e:
            logger.error(f"Error checking mute status: {e}")
            
        return await handler(event, data)
