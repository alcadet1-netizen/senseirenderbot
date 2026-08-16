import logging
import time
from typing import Callable, Dict, Any, Awaitable
import asyncio
from datetime import datetime

from aiogram import BaseMiddleware
from aiogram.types import Message
from aiogram.enums import ParseMode

from src.core.container import Container

logger = logging.getLogger(__name__)

class DigestMiddleware(BaseMiddleware):
    def __init__(self, container: Container):
        self.container = container

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        start = time.time()
        logger.info(f"[DIGEST] Start processing message chat_id={event.chat.id}")
        # Only handle text messages in groups/supergroups
        if isinstance(event, Message) and event.text and event.chat.type in ("group", "supergroup"):
            # Check if allowed chats are set and if current chat is allowed
            allowed_chats = self.container.settings.allowed_chats
            if not allowed_chats or event.chat.id in allowed_chats:

                # Extract reply text
                reply_text = None
                if event.reply_to_message and event.reply_to_message.text:
                    reply_text = event.reply_to_message.text

                user = event.from_user
                display_name = user.full_name or user.username or f"Анон_{user.id}"

                # Add message to storage
                self.container.digest_service.add_message(
                    chat_id=event.chat.id,
                    user_id=user.id,
                    username=user.username,
                    display_name=display_name,
                    text=event.text,
                    reply_to=reply_text
                )

                # Check for auto-digest
                threshold = self.container.settings.auto_digest_threshold
                new_messages = self.container.digest_service.get_new_messages_count(event.chat.id)

                if new_messages >= threshold:
                    can, _ = self.container.digest_service.can_generate(event.chat.id)
                    if can:
                        asyncio.create_task(
                            self.container.digest_service.trigger_digest(
                                chat_id=event.chat.id,
                                bot=event.bot,
                                auto=True
                            )
                        )
        duration_ms = (time.time() - start) * 1000
        logger.info(f"[DIGEST] Finished processing message chat_id={event.chat.id} in {duration_ms:.2f} ms")
        return await handler(event, data)
