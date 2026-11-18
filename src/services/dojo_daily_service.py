"""Daily Dojo rewards, serialized and paid in MongoDB transactions."""
import secrets
import re
from datetime import datetime, timezone, timedelta

from src.services.hedgehog_service import GameError
from src.services.referral_economy import transaction


def day_number(day, previous, streak):
    if previous == day:
        return streak
    if previous == day - timedelta(days=1) and streak < 90:
        return streak + 1
    return 1


def reward_for_day(day):
    return 100 if day == 1 else 200 if day == 2 else 600


class DojoDailyService:
    def __init__(self, mongo):
        self.mongo = mongo
        self.db = mongo.database

    async def state(self, uid):
        now = datetime.now(timezone.utc).date()
        doc = await self.db.dojo_daily.find_one({'_id': uid}) or {}
        previous = datetime.strptime(doc['last_day'], '%Y-%m-%d').date() if doc.get('last_day') else None
        streak = day_number(now, previous, doc.get('streak', 0))
        return {'streak': streak, 'claimed': previous == now,
                'reward': reward_for_day(streak), 'bonus_chests': doc.get('chests', 0),
                'free_chest': doc.get('free_day') != now.isoformat(),
                'gram_hundredths': doc.get('gram_hundredths', 0)}

    async def claim(self, uid):
        now = datetime.now(timezone.utc)
        today = now.date()
        async def work(session):
            user = await self.db.users.find_one({'id': uid}, session=session)
            if not user or user.get('is_banned'):
                raise GameError('Профиль недоступен.')
            doc = await self.db.dojo_daily.find_one({'_id': uid}, session=session) or {}
            last = datetime.strptime(doc['last_day'], '%Y-%m-%d').date() if doc.get('last_day') else None
            if last == today:
                raise GameError('Награда за сегодня уже получена.')
            day = day_number(today, last, doc.get('streak', 0))
            amount = reward_for_day(day)
            debit = await self.db.bank.update_one({'_id': 'single', 'coins': {'$gte': amount}}, {'$inc': {'coins': -amount}}, session=session)
            if not debit.matched_count:
                raise GameError('В SenseiBank недостаточно средств. Попробуй позже.')
            await self.db.users.update_one({'id': uid}, {'$inc': {'coins': amount}}, session=session)
            await self.db.dojo_daily.update_one({'_id': uid}, {'$set': {'last_day': today.isoformat(), 'streak': day}, '$inc': {'chests': day // 7 if day % 7 == 0 else 0}}, upsert=True, session=session)
            await self.db.transactions.insert_one({'user_id': uid, 'tx_type': 'dojo_daily', 'coins_change': amount, 'created_at': now, 'description': f'Dojo daily day {day}'}, session=session)
            return {'day': day, 'reward': amount, 'chests_added': day // 7 if day % 7 == 0 else 0}
        return await transaction(self.mongo, work)

    async def grant_admin_chests(self, username, amount, admin_id, request_id):
        """Atomically credit bonus chests and persist an idempotent audit record."""
        if (not isinstance(username, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{4,31}', username)
                or type(amount) is not int or not 1 <= amount <= 10000):
            raise GameError('Укажи @username и количество от 1 до 10000.')
        now = datetime.now(timezone.utc)
        async def work(session):
            receipt = await self.db.dojo_admin_chest_grants.find_one({'_id': request_id}, session=session)
            if receipt:
                if (receipt.get('admin_id') != admin_id or receipt.get('amount') != amount
                        or str(receipt.get('username', '')).lower() != username.lower()):
                    raise GameError('Этот идентификатор уже использован для другой выдачи.')
                return receipt
            # Reject ambiguous/stale duplicate usernames rather than credit the wrong player.
            matches = await self.db.users.find(
                {'username': {'$regex': '^' + re.escape(username) + '$', '$options': 'i'}},
                {'id': 1, 'username': 1}, session=session).limit(2).to_list(length=2)
            if not matches:
                raise GameError('Пользователь не найден. Он должен сначала зарегистрироваться у бота.')
            if len(matches) != 1 or type(matches[0].get('id')) is not int:
                raise GameError('Имя пользователя неоднозначно. Выдача отменена; проверь профиль.')
            uid = matches[0]['id']
            await self.db.dojo_daily.update_one(
                {'_id': uid}, {'$inc': {'chests': amount}}, upsert=True, session=session)
            receipt = {'_id': request_id, 'admin_id': admin_id, 'user_id': uid,
                       'username': matches[0]['username'], 'amount': amount, 'created_at': now}
            await self.db.dojo_admin_chest_grants.insert_one(receipt, session=session)
            return receipt
        return await transaction(self.mongo, work)

    async def open_chest(self, uid, request_id):
        now = datetime.now(timezone.utc)
        today = now.date().isoformat()
        # Fixed, public probabilities, independent of balance and streak.
        roll = secrets.randbelow(1000)
        if roll < 10:
            prize = ('gram', 1 + secrets.randbelow(3))
        elif roll < 60:
            prize = ('chest', 2)
        else:
            prize = ('coin', (100, 200, 300, 400, 500)[secrets.randbelow(5)])
        async def work(session):
            old = await self.db.dojo_chest_receipts.find_one({'_id': f'{uid}:{request_id}'}, session=session)
            if old:
                return old['result']
            user = await self.db.users.find_one({'id': uid}, session=session)
            if not user or user.get('is_banned'):
                raise GameError('Профиль недоступен.')
            doc = await self.db.dojo_daily.find_one({'_id': uid}, session=session) or {}
            free = doc.get('free_day') != today
            if not free and doc.get('chests', 0) <= 0:
                raise GameError('Сундуков пока нет.')
            # Require enough bank for every possible Coin outcome before any
            # roll can succeed, so an empty bank cannot be used to reroll for GRAM.
            bank = await self.db.bank.find_one({'_id': 'single'}, session=session)
            if not bank or bank.get('coins', 0) < 500:
                raise GameError('SenseiBank временно не может обеспечить все награды сундука.')
            kind, amount = prize
            if kind == 'coin':
                debit = await self.db.bank.update_one({'_id': 'single', 'coins': {'$gte': amount}}, {'$inc': {'coins': -amount}}, session=session)
                if not debit.matched_count:
                    raise GameError('В SenseiBank недостаточно средств. Попробуй позже.')
                await self.db.users.update_one({'id': uid}, {'$inc': {'coins': amount}}, session=session)
                await self.db.transactions.insert_one({'user_id': uid, 'tx_type': 'dojo_chest', 'coins_change': amount, 'created_at': now}, session=session)
            updates = {'$inc': {'chests': (0 if free else -1) + (amount if kind == 'chest' else 0), 'gram_hundredths': amount if kind == 'gram' else 0}}
            if free:
                updates['$set'] = {'free_day': today}
            await self.db.dojo_daily.update_one({'_id': uid}, updates, upsert=True, session=session)
            result = {'kind': kind, 'amount': amount}
            await self.db.dojo_chest_receipts.insert_one({'_id': f'{uid}:{request_id}', 'result': result, 'created_at': now}, session=session)
            return result
        return await transaction(self.mongo, work)
