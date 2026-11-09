"""Fail-closed group access policy; private chats and payment receipts are unaffected."""
import time

from aiogram import BaseMiddleware
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import Update


def access_denied(exc):
    if isinstance(exc, TelegramForbiddenError):
        return True
    return isinstance(exc, TelegramBadRequest) and any(text in str(exc).lower() for text in (
        'not enough rights', 'chat not found', 'kicked', 'not a member',
        'chat_write_forbidden', 'chat_send_plain_forbidden', 'migrated'))


class GroupAdminAccess:
    def __init__(self):
        self.cache = {}

    def invalidate(self, bot_id, chat_id):
        self.cache.pop((bot_id, chat_id), None)

    def deny(self, bot_id, chat_id):
        self.cache[(bot_id, chat_id)] = (time.monotonic()+300, False)

    async def allowed(self, bot, chat_id):
        key = (bot.id, chat_id)
        cached = self.cache.get(key)
        if cached and cached[0] > time.monotonic():
            return cached[1]
        try:
            member = await bot.get_chat_member(chat_id, bot.id)
            allowed = member.status in {'administrator', 'creator'}
        except Exception as exc:
            if access_denied(exc):
                self.deny(bot.id, chat_id)
                return False
            # Temporary lookup failures must not allow rewards or replies.
            raise
        self.cache[key] = (time.monotonic()+60, allowed)
        return allowed


group_admin_access = GroupAdminAccess()


class GroupAdminMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        if isinstance(event, Update):
            bot = data['bot']
            if event.my_chat_member:
                group_admin_access.invalidate(bot.id, event.my_chat_member.chat.id)
            message = event.message or event.edited_message
            if event.callback_query:
                message = event.callback_query.message
            if message and message.chat.type in {'group', 'supergroup'}:
                try:
                    if not await group_admin_access.allowed(bot, message.chat.id):
                        return None
                except Exception:
                    # No API response/rewards when membership cannot be verified.
                    return None
        return await handler(event, data)
