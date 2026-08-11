"""
🛡️ Middleware модерации.
"""
from typing import Any, Awaitable, Callable, Dict
import logging

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from src.core.container import Container

logger = logging.getLogger(__name__)


class ModerationMiddleware(BaseMiddleware):
    """Middleware для автоматического удаления сообщений замьюченных пользователей."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Работаем только с сообщениями
        if not isinstance(event, Message):
            return await handler(event, data)
        
        message: Message = event
        
        # Пропускаем, если нет отправителя
        if not message.from_user:
            return await handler(event, data)
        
        user_id = message.from_user.id
        
        # Получаем контейнер с сервисами
        container: Container = data.get("container")
        if not container:
            return await handler(event, data)
        
        # Проверяем, замьючен ли пользователь
        try:
            is_muted = await container.moderation_service.is_muted(user_id)
            
            if is_muted:
                # Удаляем сообщение
                try:
                    await message.delete()
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
