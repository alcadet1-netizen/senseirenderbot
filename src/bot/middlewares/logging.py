"""
📝 Middleware для логирования.
"""

import logging
import time
import structlog
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery, ChatMemberUpdated

logger = structlog.get_logger(__name__)


class LoggingMiddleware(BaseMiddleware):
    """Middleware для логирования событий."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        start_time = time.perf_counter()
        
        # Контекст для логгера
        log_context = {}
        
        if isinstance(event, Message) and event.from_user:
            text_preview = ""
            if event.text:
                text_preview = event.text[:50] + "..." if len(event.text) > 50 else event.text
            elif event.caption:
                text_preview = f"[Caption] {event.caption[:50]}..."
            else:
                text_preview = f"[{event.content_type}]"
                
            log_context.update({
                "event_type": "message",
                "user_id": event.from_user.id,
                "username": event.from_user.username,
                "chat_id": event.chat.id,
                "text": text_preview
            })
            
            logger.info("➡️ Incoming Message", **log_context)
            
        elif isinstance(event, CallbackQuery) and event.from_user:
            log_context.update({
                "event_type": "callback",
                "user_id": event.from_user.id,
                "username": event.from_user.username,
                "data": event.data
            })
            logger.info("➡️ Incoming Callback", **log_context)
            
        elif isinstance(event, ChatMemberUpdated) and event.from_user:
            log_context.update({
                "event_type": "chat_member",
                "user_id": event.from_user.id,
                "username": event.from_user.username,
                "chat_id": event.chat.id,
                "status": event.new_chat_member.status
            })
            logger.info("➡️ Member Update", **log_context)

        try:
            result = await handler(event, data)
            
            duration = (time.perf_counter() - start_time) * 1000
            if log_context:
                logger.info("✅ Handled", duration_ms=round(duration, 2), **log_context)
            
            return result
        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000
            if log_context:
                logger.error("❌ Error", duration_ms=round(duration, 2), error=str(e), **log_context)
            raise e
