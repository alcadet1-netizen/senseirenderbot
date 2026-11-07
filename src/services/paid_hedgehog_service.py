"""Stars-funded daily repeats; rewards/bank/order settle in one Mongo transaction."""
import copy
import secrets
import time
from datetime import datetime, timezone

from pymongo import ReturnDocument
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern

from src.services.hedgehog_service import GameError, utc_day

MAX_STARS = 10000


def price(paid_count):
    if not isinstance(paid_count, int) or not 0 <= paid_count <= 12:
        raise GameError('Лимит платных попыток на сегодня достигнут.')
    value = 1 if paid_count == 0 else 5 * 2 ** (paid_count - 1)
    if value > MAX_STARS:
        raise GameError('Лимит платных попыток на сегодня достигнут.')
    return value


class PaidHedgehogService:
    def __init__(self, mongo):
        self.db = mongo.database
        self.users = self.db.users
        self.orders = self.db.paid_pet_orders
        self.payments = self.db.paid_pet_payments
        self.days = self.db.paid_pet_days

    async def available(self):
        hello = await self.db.command('hello')
        if not hello.get('logicalSessionTimeoutMinutes') or not (hello.get('setName') or hello.get('msg') == 'isdbgrid'):
            raise GameError('Платные попытки временно недоступны: нужен транзакционный MongoDB.')

    async def transaction(self, callback):
        async with await self.db.client.start_session() as session:
            return await session.with_transaction(callback, read_concern=ReadConcern('snapshot'),
                                                  write_concern=WriteConcern('majority'))

    async def quote(self, uid):
        await self.available()
        day = utc_day()

        async def create(tx):
            user = await self.users.find_one({'id': uid}, session=tx)
            if not user or user.get('is_banned'):
                raise GameError('Профиль недоступен.')
            if user.get('hedgehog_day') != day or not user.get('hedgehog_result', {}).get('ordinary_daily'):
                raise GameError('Сначала получите бесплатную Ежу: /senseidaily.')
            pet = user.get('daily_pet', {})
            if pet and (pet.get('state') == 'pending' or pet.get('deadline', 0) > time.time()):
                raise GameError('Сначала завершите текущие 15 секунд поглаживаний.')
            if await self.payments.find_one({'user_id': uid, 'state': 'received'}, session=tx):
                raise GameError('Оплата уже сохранена. Повторите /senseidaily, не оплачивайте заново.')
            counter = await self.days.find_one({'_id': f'{uid}:{day}'}, session=tx) or {}
            count = counter.get('count', 0)
            amount = price(count)
            result = copy.deepcopy(user['hedgehog_result'])
            result['total_coins'] = result['coins'] + result['bonus_coins']
            bank = await self.db.bank.find_one({'_id': 'main'}, session=tx)
            if max(0, int((bank or {}).get('balance', 0))) < result['total_coins']:
                raise GameError('В банке недостаточно монет для полной награды. Оплата пока недоступна.')
            return await self.orders.find_one_and_update(
                {'_id': f'{uid}:{day}:{count+1}'},
                {'$setOnInsert': dict(user_id=uid, day=day, number=count+1, stars=amount,
                    reward=result, state='ready')}, upsert=True, return_document=ReturnDocument.AFTER, session=tx)
        return await self.transaction(create)

    async def checkout(self, oid, uid, amount, query_id):
        await self.available()

        async def check(tx):
            order = await self.orders.find_one({'_id': oid}, session=tx)
            user = await self.users.find_one({'id': uid}, session=tx)
            if not order or order['user_id'] != uid or order['stars'] != amount or order['day'] != utc_day():
                raise GameError('Счёт устарел. Откройте новую платную попытку.')
            if not user or user.get('is_banned'):
                raise GameError('Профиль недоступен.')
            pet = user.get('daily_pet', {})
            if pet and (pet.get('state') == 'pending' or pet.get('deadline', 0) > time.time()):
                raise GameError('Текущая попытка ещё не завершена.')
            counter = await self.days.find_one({'_id': f'{uid}:{order["day"]}'}, session=tx) or {}
            if order['number'] != counter.get('count', 0)+1:
                raise GameError('Эта попытка уже использована.')
            if order['state'] not in {'ready', 'checkout'}:
                raise GameError('Этот счёт уже оплачен.')
            if (order['state'] == 'checkout' and order.get('checkout_id') != query_id
                    and order.get('checkout_at', 0) > time.time()-900):
                raise GameError('Этот счёт уже обрабатывается. Не оплачивайте его повторно.')
            bank = await self.db.bank.find_one({'_id': 'main'}, session=tx)
            if max(0, int((bank or {}).get('balance', 0))) < order['reward']['total_coins']:
                raise GameError('В банке недостаточно монет. Оплата не принята.')
            await self.orders.update_one({'_id': oid}, {'$set': dict(state='checkout',
                checkout_id=query_id, checkout_at=time.time())}, session=tx)
        await self.transaction(check)

    async def receive(self, uid, payment):
        # Durable intake before fulfillment: /senseidaily resumes received orders.
        await self.payments.update_one({'_id': payment.telegram_payment_charge_id},
            {'$setOnInsert': dict(user_id=uid, order_id=payment.invoice_payload.removeprefix('petbuy:'),
                stars=payment.total_amount, currency=payment.currency, state='received',
                received_at=datetime.now(timezone.utc))}, upsert=True)
        return await self.settle(payment.telegram_payment_charge_id, uid)

    async def pending(self, uid):
        receipt = await self.payments.find_one({'user_id': uid, 'state': 'received'})
        if receipt:
            return await self.settle(receipt['_id'], uid)
        user = await self.users.find_one({'id': uid})
        pet = (user or {}).get('daily_pet', {})
        if pet.get('paid_order') and (not pet.get('delivered') or pet.get('state') == 'pending'
                                     or pet.get('deadline', 0) > time.time()):
            return await self.payments.find_one({'user_id': uid, 'state': 'fulfilled', 'pet_token': pet['token']})
        return None

    async def settle(self, charge, uid):
        async def fulfill(tx):
            receipt = await self.payments.find_one({'_id': charge}, session=tx)
            if not receipt or receipt['user_id'] != uid:
                raise GameError('Платёж не найден.')
            if receipt['state'] != 'received':
                return receipt
            oid = receipt['order_id']
            order = await self.orders.find_one({'_id': oid}, session=tx)
            user = await self.users.find_one({'id': uid}, session=tx)
            counter = await self.days.find_one({'_id': f'{uid}:{order["day"]}'}, session=tx) if order else None
            if (not order or order['user_id'] != uid or receipt['currency'] != 'XTR'
                    or receipt['stars'] != order['stars'] or order['state'] == 'fulfilled'
                    or order['number'] != (counter or {}).get('count', 0)+1
                    or not user or user.get('is_banned')):
                await self.payments.update_one({'_id': charge}, {'$set': {'state': 'refund_required'}}, session=tx)
                return {**receipt, 'state': 'refund_required'}
            pet = user.get('daily_pet', {})
            if pet and (pet.get('state') == 'pending' or pet.get('deadline', 0) > time.time()):
                raise GameError('Оплаченная попытка сохранена. После текущей игры напишите /senseidaily.')
            bank = await self.db.bank.find_one({'_id': 'main'}, session=tx)
            reward = copy.deepcopy(order['reward'])
            coins = reward['total_coins']
            if max(0, int((bank or {}).get('balance', 0))) < coins:
                await self.payments.update_one({'_id': charge}, {'$set': {'state': 'refund_required'}}, session=tx)
                await self.orders.update_one({'_id': oid}, {'$set': {'state': 'ready', 'checkout_id': None, 'checkout_at': 0}}, session=tx)
                return {**receipt, 'state': 'refund_required'}
            session = dict(day=user['hedgehog_day'], token=secrets.token_urlsafe(24), state='pending',
                deadline=None, duration=15, delivered=False, taps=0, extra_coins=0, queries=[],
                base_coins=coins, paid_order=oid, reward=reward)
            if coins:
                debit = await self.db.bank.update_one({'_id': 'main', 'balance': {'$gte': coins}},
                    {'$inc': {'balance': -coins}}, session=tx)
                if debit.matched_count != 1:
                    raise GameError('Банк изменился. Повторите /senseidaily; оплата сохранена.')
            await self.users.update_one({'id': uid}, {'$inc': {'coins': coins, 'xp': reward['total_xp']},
                '$set': {'daily_pet': session}}, session=tx)
            await self.days.update_one({'_id': f'{uid}:{order["day"]}'},
                {'$set': {'count': order['number']}}, upsert=True, session=tx)
            await self.orders.update_one({'_id': oid}, {'$set': {'state': 'fulfilled', 'charge': charge}}, session=tx)
            result = {**receipt, 'state': 'fulfilled', 'reward': reward, 'pet_token': session['token']}
            await self.payments.update_one({'_id': charge}, {'$set': {
                'state': 'fulfilled', 'reward': reward, 'pet_token': session['token']}}, session=tx)
            await self.db.transactions.update_one({'_id': f'paid_pet:{charge}'}, {'$setOnInsert': {
                'user_id': uid, 'tx_type': 'paid_pet_reward', 'coins_change': coins,
                'xp_change': reward['total_xp'], 'created_at': datetime.now(timezone.utc)}}, upsert=True, session=tx)
            return result
        return await self.transaction(fulfill)

    async def tap(self, token, uid, query_id, *, received_at=None):
        from src.services.daily_pet_service import PetRateLimit

        async def apply(tx):
            user = await self.users.find_one({'id': uid}, session=tx)
            pet = (user or {}).get('daily_pet', {})
            if (not user or user.get('is_banned') or pet.get('token') != token
                    or user.get('hedgehog_day') != pet.get('day') or not pet.get('paid_order')):
                raise GameError('Это не ваша оплаченная попытка.')
            if pet['state'] == 'pending':
                raise GameError('Уведомление ещё готовится.')
            if query_id in pet['queries']:
                return pet
            now = time.time() if received_at is None else received_at
            if not pet['deadline']-15 <= now < pet['deadline']:
                raise GameError('15 секунд истекли. Подтверждённые награды сохранены.')
            slot = int(now*10) if received_at is not None else None
            if slot is not None and slot in pet.get('web_slots', []):
                raise PetRateLimit('Тапы слишком частые. Эффекты работают на каждом касании.')
            bank = await self.db.bank.find_one({'_id': 'main'}, session=tx)
            delta = min(max(0, pet['base_coins']*(pet['taps']+1)//10-pet['extra_coins']),
                        max(0, int((bank or {}).get('balance', 0))))
            updated = copy.deepcopy(pet)
            updated['taps'] += 1
            updated['extra_coins'] += delta
            updated['queries'].append(query_id)
            if slot is not None:
                updated.setdefault('web_slots', []).append(slot)
            if delta:
                debit = await self.db.bank.update_one({'_id': 'main', 'balance': {'$gte': delta}},
                    {'$inc': {'balance': -delta}}, session=tx)
                if debit.matched_count != 1:
                    raise GameError('Банк изменился. Повторите запрос.')
            await self.users.update_one({'id': uid}, {'$set': {'daily_pet': updated},
                '$inc': {'coins': delta}}, session=tx)
            await self.db.transactions.update_one({'_id': f"paid_pet_tap:{pet['paid_order']}:{updated['taps']}"},
                {'$setOnInsert': dict(user_id=uid,tx_type='daily_pet_bonus',coins_change=delta,
                    xp_change=0,created_at=datetime.now(timezone.utc))}, upsert=True, session=tx)
            return updated
        return await self.transaction(apply)
