"""Immediate ordinary daily reward plus a fifteen-second personal callback window."""
import asyncio
import copy
import secrets
import time
from collections import defaultdict
from datetime import datetime, timezone

from pymongo import ReturnDocument

from src.core.exceptions import DailyAlreadyClaimedError
from src.services.hedgehog_service import GameError, utc_day


class PetRateLimit(GameError):
    pass


class DailyPetService:
    def __init__(self, mongo, daily):
        self.users = mongo.database.users
        self.bank = mongo.database.bank
        self.transactions = mongo.database.transactions
        self.daily = daily
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
                    return user['hedgehog_result'], session
            result = await self.daily.settle_hedgehog(user_id, True, day, ordinary=True)
            if not result.get('ordinary_daily'):
                raise DailyAlreadyClaimedError('завтра после 00:00 UTC')
            user = await self.users.find_one({'id': user_id})
            previous = user.get('daily_pet')
            if previous and previous.get('day') == day:
                if previous.get('delivered'):
                    raise DailyAlreadyClaimedError('завтра после 00:00 UTC')
                return result, previous
            session = dict(day=day, token=secrets.token_urlsafe(24), state='pending',
                           deadline=None, duration=15, delivered=False, taps=0, extra_coins=0, queries=[],
                           base_coins=result['total_coins'])
            committed = await self.users.find_one_and_update(
                {'id': user_id, 'hedgehog_day': day, 'daily_pet': previous},
                {'$set': {'daily_pet': session}}, return_document=ReturnDocument.AFTER)
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

    async def mark_delivered(self, token, user_id):
        for _ in range(8):
            session = await self.owned(token, user_id)
            if session.get('delivered'):
                return
            saved = await self.users.find_one_and_update(
                {'id': user_id, 'daily_pet': session},
                {'$set': {'daily_pet': {**session, 'delivered': True}}},
                return_document=ReturnDocument.AFTER)
            if saved:
                return
        raise GameError('Уведомление отправлено; окно поглаживаний не продлевается.')

    async def widget_action(self, token, user_id, action, query_id, *, received_at=None):
        if action not in {'v', 'p'}:
            raise GameError('Неверное действие.')
        session = await self.owned(token, user_id)
        if session['state'] == 'pending':
            raise GameError('Уведомление ежа ещё готовится.')
        if action == 'p' and (time.time() if received_at is None else received_at) < session['deadline']:
            try:
                session = await self.tap(token, user_id, query_id, received_at=received_at)
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

    async def tap(self, token, user_id, query_id, *, received_at=None):
        if not isinstance(query_id, str) or not 1 <= len(query_id) <= 128:
            raise GameError('Неверное поглаживание.')
        async with self._locks[user_id]:
            for _ in range(8):
                session = await self.owned(token, user_id)
                if session['state'] == 'pending':
                    raise GameError('Ёж ещё готовится. Нажмите ещё раз.')
                if query_id in session['queries']:
                    return session
                accepted_at = time.time() if received_at is None else received_at
                if accepted_at >= session['deadline'] or accepted_at < session['deadline'] - session.get('duration', 10):
                    raise GameError(f"{session.get('duration', 10)} секунд истекли. Основная награда ваша. Дополнительно: +{session['extra_coins']} монет.")
                slot = int(accepted_at * 10) if received_at is not None else None
                if slot is not None and slot in session.get('web_slots', []):
                    raise PetRateLimit('Тапы слишком частые: не более одного за 100 мс. Эффекты работают на каждом касании.')
                bank = await self.bank.find_one({'_id': 'main'})
                desired = session['base_coins'] * (session['taps'] + 1) // 10
                # Each tap adds ten percent of the original coin award, not compound interest.
                delta = min(max(0, desired - session['extra_coins']), max(0, int((bank or {}).get('balance', 0))))
                updated = copy.deepcopy(session)
                updated['taps'] += 1
                updated['extra_coins'] += delta
                updated['queries'].append(query_id)
                if slot is not None:
                    updated.setdefault('web_slots', []).append(slot)
                # Count, dedup receipt and money are ONE atomic user-document change.
                # Full snapshot CAS also protects simultaneous callbacks across processes.
                committed = await self.users.find_one_and_update(
                    {'id': user_id, 'is_banned': {'$ne': True}, 'daily_pet': session},
                    {'$set': {'daily_pet': updated}, '$inc': {'coins': delta}},
                    return_document=ReturnDocument.AFTER)
                if not committed:
                    continue
                try:
                    if delta:
                        debit = await self.bank.update_one({'_id': 'main', 'balance': {'$gte': delta}},
                                                   {'$inc': {'balance': -delta}})
                        if debit is None or getattr(debit, 'matched_count', None) == 0:
                            raise RuntimeError('Bank debit did not match after user credit; reconciliation required')
                    await self.transactions.update_one(
                        {'_id': f"daily_pet:{user_id}:{session['day']}:{updated['taps']}"},
                        {'$setOnInsert': {'user_id': user_id, 'tx_type': 'daily_pet_bonus',
                         'coins_change': delta, 'xp_change': 0, 'created_at': datetime.now(timezone.utc)}},
                        upsert=True)
                except Exception:
                    import logging
                    logging.getLogger(__name__).exception('Daily pet credited; ledger needs reconciliation: user=%s', user_id)
                return updated
            raise GameError('Поглаживания пришли одновременно. Нажмите ещё раз.')
