"""Capture before game filters, throttling and command cleanup can discard input."""
import logging
from aiogram import BaseMiddleware
from aiogram.types import Update

logger = logging.getLogger(__name__)


class CommentCampaignMiddleware(BaseMiddleware):
    def __init__(self, service):
        self.service = service

    async def __call__(self, handler, event, data):
        if isinstance(event, Update):
            try:
                await self.service.capture(event)
            except Exception:
                logger.critical('Campaign ingress persistence failed; operator intervention required', exc_info=True)
                raise
        return await handler(event, data)


async def campaign_message_deleted(container, chat_id, message_id):
    service = getattr(container, '_comment_campaign_service', None)
    if service is not None:
        try:
            await service.note_deleted(chat_id, message_id)
        except Exception:
            logger.critical('Could not persist known campaign comment deletion', exc_info=True)
