"""Bounded fallback for join requests when membership updates are missing.

A request is never treated as a join. Only a positive getChatMember result
can trigger the existing welcome/registration path.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import User
from pymongo import ReturnDocument

from src.bot.handlers.events import _handle_join
from src.bot.middlewares.group_admin import group_admin_access

logger = logging.getLogger(__name__)


class JoinRequestWatch:
    def __init__(self, container, bot):
        self.container = container
        self.bot = bot
        self.collection = container.mongo_client.database.join_request_watch

    async def ensure_indexes(self):
        await self.collection.create_index('expires_at', expireAfterSeconds=0)
        await self.collection.create_index('next_check')
        await self.collection.create_index([('chat_id', 1), ('user_id', 1)])

    async def capture(self, update):
        request = update.chat_join_request
        if not request or request.chat.type not in ('group', 'supergroup') or request.from_user.is_bot:
            return
        now = datetime.now(timezone.utc)
        # Only metadata required for a later welcome; never store contact IDs,
        # biography or the invite link. Upsert is idempotent across offset retry.
        await self.collection.update_one({'_id': update.update_id}, {'$setOnInsert': {
            'chat_id': request.chat.id, 'chat_type': request.chat.type,
            'user_id': request.from_user.id,
            'user': {key: getattr(request.from_user, key) for key in
                     ('id', 'is_bot', 'first_name', 'last_name', 'username')},
            'next_check': now + timedelta(seconds=90),
            'expires_at': now + timedelta(days=2),
        }}, upsert=True)
        logger.info('Join request recorded update=%s chat=%s user=%s',
                    update.update_id, request.chat.id, request.from_user.id)

    async def confirmed(self, chat_id, user_id):
        # Normal membership updates and service messages supersede the fallback.
        await self.collection.delete_many({'chat_id': chat_id, 'user_id': user_id})

    async def check_one(self):
        now = datetime.now(timezone.utc)
        # Claim via an atomic lease, also scheduling retry if the worker crashes.
        item = await self.collection.find_one_and_update(
            {'next_check': {'$lte': now}, 'expires_at': {'$gt': now}},
            {'$set': {'next_check': now + timedelta(seconds=120)}},
            sort=[('next_check', 1)], return_document=ReturnDocument.AFTER)
        if not item:
            return False
        chat_id, user_id = item['chat_id'], item['user_id']
        allowed_id = getattr(getattr(self.container, 'settings', None), 'main_chat_id', None)
        if allowed_id is not None and chat_id != allowed_id:
            await self.collection.delete_many({'_id': item['_id']})
            return True
        try:
            if not await group_admin_access.allowed(self.bot, chat_id):
                logger.warning('Join request check skipped: bot admin not verified chat=%s', chat_id)
                return True
            try:
                member = await self.bot.get_chat_member(chat_id, user_id)
            except TelegramBadRequest as exc:
                # Telegram may not expose a member record for an unresolved
                # join request. This is NOT proof of a join, a rejection or a
                # departure: keep the leased request until confirmation/expiry.
                description = exc.message.strip().casefold()
                if description in {'bad request: member not found', 'member not found'}:
                    logger.debug('Join request membership not found yet chat=%s user=%s; will retry',
                                 chat_id, user_id)
                    return True
                raise
            status = member.status
            is_member = status in ('member', 'administrator', 'creator') or (
                status == 'restricted' and getattr(member, 'is_member', False))
            if not is_member:
                return True
            # Recheck that a normal join handler did not already resolve this
            # request while the network lookups were running.
            if not await self.collection.find_one({'_id': item['_id']}):
                return True
            async def answer(text, **kwargs):
                return await self.bot.send_message(chat_id, text, **kwargs)
            event = SimpleNamespace(chat=SimpleNamespace(id=chat_id, type=item['chat_type']), answer=answer)
            await _handle_join(User.model_validate(item['user']), self.container, event)
            await self.confirmed(chat_id, user_id)
            logger.info('Join request confirmed by membership check chat=%s user=%s', chat_id, user_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception('Join request check failed chat=%s user=%s; will retry', chat_id, user_id)
        return True

    async def run(self):
        while True:
            try:
                # Rate-limit probes and bound work per iteration.
                for _ in range(20):
                    if not await self.check_one():
                        break
                    await asyncio.sleep(0.5)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception('Join request worker failed; will retry')
            await asyncio.sleep(10)
