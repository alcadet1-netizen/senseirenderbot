"""
📝 Middleware для логирования.
"""

import logging
import time
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseMiddleware):
    """Middleware для логирования событий."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        start_time = time.perf_counter()
        
        user_info = ""
        event_info = ""
        
        if isinstance(event, Message) and event.from_user:
            text_preview = ""
            if event.text:
                text_preview = event.text[:50] + "..." if len(event.text) > 50 else event.text
            elif event.caption:
                text_preview = f"[Caption] {event.caption[:50]}..."
            else:
                text_preview = f"[{event.content_type}]"
                
            user_info = f"user_id={event.from_user.id} username=@{event.from_user.username}"
            # Log full text representation to debug invisible characters
            text_repr = repr(event.text) if event.text else "None"
            event_info = f"chat_id={event.chat.id} text={text_repr}"
            
            logger.debug(f"➡️ [MSG] {user_info} {event_info}")
            
        elif isinstance(event, CallbackQuery) and event.from_user:
            user_info = f"user_id={event.from_user.id} username=@{event.from_user.username}"
            event_info = f"data='{event.data}'"
            logger.debug(f"➡️ [CALLBACK] {user_info} {event_info}")

        try:
            result = await handler(event, data)
            
            duration = (time.perf_counter() - start_time) * 1000
            if user_info:
                # Log chat_id and text in INFO for better visibility of silent failures
                msg_details = f"chat_id={event.chat.id}" if isinstance(event, Message) else ""
                logger.info(f"✅ [DONE] {user_info} {msg_details} duration={duration:.2f}ms")
            
            return result
        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000
            if user_info:
                logger.error(f"❌ [ERROR] {user_info} duration={duration:.2f}ms error={e}")
            raise e
