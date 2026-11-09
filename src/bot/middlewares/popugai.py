"""Observe accepted messages without consuming game/command handlers."""
import logging
import random

from aiogram import BaseMiddleware
from aiogram.types import Message, ReplyParameters
from src.bot.middlewares.group_admin import group_admin_access

logger = logging.getLogger(__name__)


class PopugaiMiddleware(BaseMiddleware):
    def __init__(self, container):
        self.container = container

    async def __call__(self, handler, event, data):
        if (isinstance(event, Message) and event.chat.type in {'group', 'supergroup'}
                and event.from_user and not event.from_user.is_bot and not event.sender_chat
                and not event.successful_payment):
            text = event.text or event.caption or ''
            command = text.startswith('/') or any(e.type == 'bot_command' for e in
                [*(event.entities or []), *(event.caption_entities or [])])
            if not command and (event.sticker or event.animation or event.text or event.caption):
                try:
                    # Explicit fail-closed check also protects independently installed middleware.
                    if await group_admin_access.allowed(event.bot, event.chat.id):
                        await self.observe(event)
                except Exception as exc:
                    logger.warning('Popugai unavailable error_type=%s', type(exc).__name__)
        return await handler(event, data)

    async def observe(self, message):
        service = self.container.popugai_service
        media = message.sticker or message.animation
        if media:
            kind = 'sticker' if message.sticker else 'gif'
            await service.add_media(message.chat.id, kind, media.file_id, media.file_unique_id)
        chance = await service.get_reply_chance(message.chat.id)
        if chance <= 0 or random.random() >= chance:
            return
        item = await service.get_random_media(message.chat.id)
        if not item:
            return
        kind, file_id = item
        reply = ReplyParameters(message_id=message.message_id, allow_sending_without_reply=True)
        if kind == 'sticker':
            await message.answer_sticker(sticker=file_id, reply_parameters=reply)
        else:
            await message.answer_animation(animation=file_id, reply_parameters=reply)
