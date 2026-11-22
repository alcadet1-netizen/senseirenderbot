"""Immediate ordinary daily reward plus a fifteen-second personal callback window."""
import asyncio
import copy
import secrets
import time
from collections import defaultdict
from datetime import datetime, timezone

import logging

from pymongo import ReturnDocument

from src.core.exceptions import DailyAlreadyClaimedError
from src.services.hedgehog_service import GameError, utc_day
from src.services.bank_ledger import BankLedger


logger = logging.getLogger(__name__)

# How long a 'sending' reservation is considered live. A real send takes a few
# seconds; anything older (or without a timestamp, i.e. left by a process that
# died mid-send) is abandoned and may be taken over.
NOTICE_LEASE_SECONDS = 15 * 60


class PetRateLimit(GameError):
    pass


class DailyPetService:
    def __init__(self, mongo, daily, hedgehog_gridfs):
        self.mongo = mongo
        self.users = mongo.database.users
        self.bank = mongo.database.bank
        self.transactions = mongo.database.transactions
        self.daily = daily
        self.ledger = BankLedger(mongo)
        self.hedgehog_gridfs = hedgehog_gridfs
        self._locks = defaultdict(asyncio.Lock)

    async def claim(self, user_id):
        async with self._locks[user_id]:
            day = utc_day()
            user = await self.users.find_one({'id': user_id})
            if not user or user.get('is_banned'):
                raise GameError('Профиль недоступен.')
            if user.get('hedgehog_day') == day:
                if not user.get('hedgehog_result', {}).get('ordinary_daily'):
                    raise DailyAlreadyClaimedError('завтра после 00:00 UTC')
                session = user.get('daily_pet')
                if session and session.get('day') == day:
                    if session.get('delivered'):
                        raise DailyAlreadyClaimedError('завтра после 00:00 UTC')
                    return session.get('reward', user['hedgehog_result']), session
            result = await self.daily.settle_hedgehog(user_id, True, day, ordinary=True)
            if not result.get('ordinary_daily'):
                raise DailyAlreadyClaimedError('завтра после 00:00 UTC')
            user = await self.users.find_one({'id': user_id})
            previous = user.get('daily_pet')
            if previous and previous.get('day') == day:
                if previous.get('delivered'):
                    raise DailyAlreadyClaimedError('завтра после 00:00 UTC')
                return result, previous
            from src.services.hedgehog_gallery import select_image
            image_name, images_seen = await select_image(user, self.hedgehog_gridfs)
            session = dict(day=day, token=secrets.token_urlsafe(24), state='pending',
                           deadline=None, duration=15, delivered=False, taps=0, extra_coins=0, queries=[],
                           base_coins=result['total_coins'], image_name=image_name)
            committed = await self.users.find_one_and_update(
                {'id': user_id, 'hedgehog_day': day, 'daily_pet': previous},
                {'$set': {'daily_pet': session, 'hedgehog_images_seen': images_seen}}, return_document=ReturnDocument.AFTER)
            if not committed:
                raise GameError('Награда сохранена. Повторите команду, чтобы получить уведомление.')
            return result, session

    async def owned(self, token, user_id):
        if not isinstance(token, str) or len(token) != 32:
            raise GameError('Неверная ссылка на ежа.')
        user = await self.users.find_one({'id': user_id})
        session = (user or {}).get('daily_pet', {})
        if (not user or user.get('is_banned') or session.get('token') != token
                or user.get('hedgehog_day') != session.get('day')):
            raise GameError('Это не ваш ёж или наступил новый день. Откройте /senseidaily.')
        return session

    async def activate(self, token, user_id, sent_at):
        session = await self.owned(token, user_id)
        if session['state'] != 'pending':
            return session  # Resends/restarts never extend the first delivery's window.
        active = {**session, 'state': 'active', 'deadline': sent_at + session.get('duration', 10)}
        saved = await self.users.find_one_and_update(
            {'id': user_id, 'daily_pet': session}, {'$set': {'daily_pet': active}},
            return_document=ReturnDocument.AFTER)
        return saved['daily_pet'] if saved else await self.owned(token, user_id)

    async def reserve_notice(self, token, user_id, *, lease_seconds=None):
        """At-most-once send admission, persisted before contacting Telegram.

        A reservation older than NOTICE_LEASE_SECONDS -- or one without a
        timestamp, left behind by a process that died between Telegram's reply
        and mark_delivered -- is abandoned and taken over: the photo was almost
        certainly not delivered, and the user would otherwise be blocked until
        the next day. Fresh reservations are never taken over, because a send
        may be in flight right now. The reward itself is not re-credited either
        way; rewards are unaffected.
        """
        lease = NOTICE_LEASE_SECONDS if lease_seconds is None else lease_seconds
        now = time.time()
        for _ in range(8):
            session = await self.owned(token, user_id)
            if session.get('delivered'):
                return False
            notice_state = session.get('notice_state')
            if notice_state:
                if notice_state == 'sent':
                    return False
                reserved_at = session.get('notice_reserved_at')
                age = (now - reserved_at) if isinstance(reserved_at, (int, float)) else None
                if age is not None and age < lease:
                    return False  # Fresh reservation: a send may be in flight.
                logger.warning('Taking over abandoned hedgehog notice reservation user=%s state=%s age=%s',
                               user_id, notice_state,
                               f'{age:.0f}s' if age is not None else 'unknown (legacy, no timestamp)')
            saved = await self.users.find_one_and_update(
                {'id': user_id, 'daily_pet': session},
                {'$set': {'daily_pet': {**session, 'notice_state': 'sending', 'notice_reserved_at': now}}},
                return_document=ReturnDocument.AFTER)
            if saved:
                return True
        raise GameError('Уведомление готовится. Повторное начисление не выполняется.')

    async def release_rejected_notice(self, token, user_id):
        """Release only after Telegram explicitly rejected this send.

        A timeout, cancellation or connection failure is ambiguous and must not
        use this path: Telegram may already have delivered the photo.
        """
        session = await self.owned(token, user_id)
        if session.get('delivered') or session.get('notice_state') != 'sending':
            return False
        released = {**session}
        released.pop('notice_state', None)
        released.pop('notice_reserved_at', None)
        saved = await self.users.find_one_and_update(
            {'id': user_id, 'daily_pet': session},
            {'$set': {'daily_pet': released}}, return_document=ReturnDocument.AFTER)
        return bool(saved)

    async def replace_image(self, token, user_id, *, exclude=()):
        """Select and persist a replacement image while a notice is reserved for sending."""
        from src.services.hedgehog_gallery import select_image
        for _ in range(8):
            user = await self.users.find_one({'id': user_id})
            session = (user or {}).get('daily_pet', {})
            if (not user or user.get('is_banned') or session.get('token') != token
                    or user.get('hedgehog_day') != session.get('day')
                    or session.get('delivered')):
                return None
            current = session.get('image_name')
            excluded = set(exclude or ())
            if current:
                excluded.add(current)
            image_name, images_seen = await select_image(user, self.hedgehog_gridfs, exclude=excluded)
            updated = {**session, 'image_name': image_name}
            saved = await self.users.find_one_and_update(
                {'id': user_id, 'daily_pet': session},
                {'$set': {'daily_pet': updated, 'hedgehog_images_seen': images_seen}},
                return_document=ReturnDocument.AFTER)
            if saved:
                logger.info('Hedgehog notice image rerolled user=%s from=%s to=%s', user_id, current, image_name)
                return image_name
        return None

    async def mark_delivered(self, token, user_id):
        for _ in range(8):
            session = await self.owned(token, user_id)
            if session.get('delivered'):
                return
            delivered_session = {**session, 'delivered': True, 'notice_state': 'sent'}
            delivered_session.pop('notice_reserved_at', None)
            saved = await self.users.find_one_and_update(
                {'id': user_id, 'daily_pet': session},
                {'$set': {'daily_pet': delivered_session}},
                return_document=ReturnDocument.AFTER)
            if saved:
                return
        raise GameError('Уведомление отправлено; окно поглаживаний не продлевается.')

    async def widget_action(self, token, user_id, action, query_id, *, received_at=None):
        native = received_at is None
        if native:
            received_at = time.time()  # Trusted server arrival, before database/lock waits.
        if action not in {'v', 'p'}:
            raise GameError('Неверное действие.')
        session = await self.owned(token, user_id)
        if session['state'] == 'pending':
            raise GameError('Уведомление ежа ещё готовится.')
        if action == 'p' and (time.time() if received_at is None else received_at) < session['deadline']:
            try:
                session = await self.tap(token, user_id, query_id, received_at=received_at, rate_limit=not native)
            except PetRateLimit:
                raise
            except GameError:
                session = await self.owned(token, user_id)
                if time.time() < session['deadline']:
                    raise
        left = max(0, round((session['deadline'] - time.time()) * 1000))
        return {'state': 'playing' if left else 'done', 'remaining_ms': left,
                'taps': session['taps'], 'extra_coins': session['extra_coins'],
                'base_coins': session['base_coins']}

    async def tap(self, token, user_id, query_id, *, received_at=None, rate_limit=True):
        if not isinstance(query_id, str) or not 1 <= len(query_id) <= 128:
            raise GameError('Неверное поглаживание.')
        from decimal import Decimal
        import math
        from src.services.bank_ledger import _matched
        from src.services.referral_economy import transaction

        async with self._locks[user_id]:
            initial = await self.owned(token, user_id)
            if initial.get('paid_order'):
                from src.services.paid_hedgehog_service import PaidHedgehogService
                return await PaidHedgehogService(self.mongo, self.hedgehog_gridfs).tap(
                    token, user_id, query_id, received_at=received_at, rate_limit=rate_limit)

            async def settle(tx):
                user = await self.users.find_one({'id': user_id}, session=tx)
                session = (user or {}).get('daily_pet', {})
                if (not user or user.get('is_banned') or session.get('token') != token
                        or user.get('hedgehog_day') != session.get('day') or session.get('paid_order')):
                    raise GameError('Это не ваш ёж или наступил новый день. Откройте /senseidaily.')
                if session['state'] == 'pending':
                    raise GameError('Ёж ещё готовится. Нажмите ещё раз.')
                if query_id in session['queries']:
                    return session
                accepted_at = time.time() if received_at is None else received_at
                if accepted_at >= session['deadline'] or accepted_at < session['deadline'] - session.get('duration', 10):
                    raise GameError(f"{session.get('duration', 10)} секунд истекли. Основная награда ваша. Дополнительно: +{session['extra_coins']} монет.")
                slot = int(accepted_at * 10) if received_at is not None and rate_limit else None
                if slot is not None and slot in session.get('web_slots', []):
                    raise PetRateLimit('Тапы слишком частые: не более одного за 100 мс. Эффекты работают на каждом касании.')
                accounts = []
                for bank_id, field in (('single', 'coins'), ('main', 'balance')):
                    doc = await self.bank.find_one({'_id': bank_id}, session=tx) or {}
                    balance = float(doc.get(field, 0) or 0)
                    if not math.isfinite(balance):
                        raise ValueError('Invalid bank balance')
                    accounts.append((bank_id, field, Decimal(str(max(0.0, balance)))))
                available = int(sum((entry[2] for entry in accounts), Decimal(0)))
                desired = session['base_coins'] * (session['taps'] + 1) // 10
                delta = min(max(0, desired - session['extra_coins']), available)
                remaining = Decimal(delta)
                for bank_id, field, balance in accounts:
                    take = min(remaining, balance)
                    if take <= 0:
                        continue
                    debit = await self.bank.update_one({'_id': bank_id, field: {'$gte': float(take)}},
                        {'$inc': {field: -float(take)}}, session=tx)
                    if not _matched(debit):
                        raise GameError('Банк изменился. Повторите запрос.')
                    remaining -= take
                if remaining > 0:
                    raise GameError('Банк изменился. Повторите запрос.')
                updated = copy.deepcopy(session)
                updated['taps'] += 1
                updated['extra_coins'] += delta
                updated['queries'].append(query_id)
                if slot is not None:
                    updated.setdefault('web_slots', []).append(slot)
                committed = await self.users.find_one_and_update(
                    {'id': user_id, 'is_banned': {'$ne': True}, 'daily_pet': session},
                    {'$set': {'daily_pet': updated}, '$inc': {'coins': delta}},
                    return_document=ReturnDocument.AFTER, session=tx)
                if not committed:
                    raise GameError('Поглаживания пришли одновременно. Нажмите ещё раз.')
                await self.transactions.update_one(
                    {'_id': f"daily_pet:{user_id}:{session['day']}:{updated['taps']}"},
                    {'$setOnInsert': {'user_id': user_id, 'tx_type': 'daily_pet_bonus',
                     'coins_change': delta, 'xp_change': 0, 'created_at': datetime.now(timezone.utc)}},
                    upsert=True, session=tx)
                return updated

            return await transaction(self.mongo, settle)
