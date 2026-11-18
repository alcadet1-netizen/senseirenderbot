"""Observe membership delivery and route service joins before message middleware."""
import logging

from aiogram import BaseMiddleware
from aiogram.types import Update

from src.bot.handlers.events import on_new_chat_members

logger = logging.getLogger(__name__)


class JoinDiagnosticsMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        if isinstance(event, Update):
            membership = event.chat_member
            if membership:
                logger.info(
                    'Join ingress update=%s chat=%s user=%s old=%s new=%s via_request=%s',
                    event.update_id, membership.chat.id, membership.new_chat_member.user.id,
                    membership.old_chat_member.status, membership.new_chat_member.status,
                    membership.via_join_request,
                )
            elif event.message and event.message.new_chat_members:
                logger.info('Join ingress update=%s chat=%s service_members=%s',
                            event.update_id, event.message.chat.id,
                            [user.id for user in event.message.new_chat_members])
        return await handler(event, data)


class JoinServiceMessageMiddleware(BaseMiddleware):
    """Confirmed service messages are not commands or messages from an inviter.

    Run after the group-admin access check but before maintenance, moderation,
    and activity middleware: those can otherwise consume or fail a join message.
    """
    def __init__(self, container):
        self.container = container

    async def __call__(self, handler, event, data):
        if (isinstance(event, Update) and event.message and event.message.new_chat_members
                and event.message.chat.type in ('group', 'supergroup')):
            await on_new_chat_members(event.message, self.container)
            return None
        return await handler(event, data)
