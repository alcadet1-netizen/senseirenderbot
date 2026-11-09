"""Fail-closed group access policy; private chats and payment receipts are unaffected."""
import asyncio
from collections import OrderedDict
import time
from weakref import WeakValueDictionary

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
    def __init__(self, *, max_entries=4096, clock=time.monotonic):
        if max_entries < 1:
            raise ValueError('max_entries must be positive')
        self.cache = OrderedDict()
        self.max_entries = max_entries
        self.clock = clock
        # Idle locks disappear; simultaneous lookups for one chat share one lock.
        self._locks = WeakValueDictionary()

    def _invalidate_lookup(self, key):
        lock = self._locks.get(key)
        if lock is not None:
            lock.generation += 1

    def invalidate(self, bot_id, chat_id):
        key = (bot_id, chat_id)
        self._invalidate_lookup(key)
        self.cache.pop(key, None)

    def _store(self, key, ttl, allowed):
        self.cache[key] = (self.clock()+ttl, allowed)
        self.cache.move_to_end(key)
        while len(self.cache) > self.max_entries:
            self.cache.popitem(last=False)

    def deny(self, bot_id, chat_id):
        key = (bot_id, chat_id)
        self._invalidate_lookup(key)
        self._store(key, 300, False)

    def _cached(self, key):
        cached = self.cache.get(key)
        if cached is not None:
            if cached[0] > self.clock():
                self.cache.move_to_end(key)
                return cached[1]
            self.cache.pop(key, None)
        return None

    async def allowed(self, bot, chat_id):
        key = (bot.id, chat_id)
        cached = self._cached(key)
        if cached is not None:
            return cached
        lock = self._locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            lock.generation = 0
            self._locks[key] = lock
        async with lock:
            cached = self._cached(key)
            if cached is not None:
                return cached
            generation = lock.generation
            try:
                member = await bot.get_chat_member(chat_id, bot.id)
                allowed = member.status in {'administrator', 'creator'}
            except Exception as exc:
                if access_denied(exc):
                    self.deny(bot.id, chat_id)
                    return False
                # Brief fail-closed backoff prevents outage-driven request storms.
                if generation == lock.generation:
                    self._store(key, 5, False)
                raise
            # A membership update or send denial raced this lookup. Never restore
            # stale positive permissions; the next lookup may verify fresh rights.
            if generation != lock.generation:
                return False
            self._store(key, 60, allowed)
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
