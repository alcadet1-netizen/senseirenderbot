"""Versioned Stars packages; Mongo receipt and bank transfer, never coin emission."""
import re
import secrets
from datetime import datetime, timezone
from types import SimpleNamespace

from src.services.paid_hedgehog_service import PaidHedgehogService
from src.services.hedgehog_service import GameError

PACKAGES = {1: 500, 5: 3500, 10: 8000, 50: 45000}
PREFIX = 'coinbuy:v1:'


def valid(payload, uid, currency, stars):
    return (currency == 'XTR' and stars in PACKAGES and isinstance(payload, str) and
            (payload == f'{PREFIX}{uid}:{stars}' or
             re.fullmatch(rf'coinbuy:v2:{uid}:{stars}:[a-f0-9]{{24}}', payload) is not None))


class StarCoinService(PaidHedgehogService):
    def __init__(self, mongo):
        super().__init__(mongo)
        self.receipts = self.db.star_coin_payments
        self.coin_orders = self.db.star_coin_orders

    async def create_order(self, uid, stars):
        await self.check(uid, stars)
        payload = f'coinbuy:v2:{uid}:{stars}:{secrets.token_hex(12)}'
        await self.coin_orders.update_one({'_id': payload}, {'$setOnInsert': dict(
            user_id=uid, stars=stars, created_at=datetime.now(timezone.utc))}, upsert=True)
        return payload

    async def bind_invoice(self, payload, uid, chat_id, message_id):
        result = await self.coin_orders.update_one({'_id': payload, 'user_id': uid},
            {'$set': {'notice': dict(chat_id=chat_id, message_id=message_id)}})
        if result.matched_count != 1:
            raise GameError('Не удалось сохранить счёт. Не оплачивайте его; /paysupport.')

    async def checkout(self, payload, uid, currency, stars):
        if not valid(payload, uid, currency, stars):
            raise GameError('Неверный счёт. Откройте /donate заново.')
        if payload.startswith('coinbuy:v2:'):
            order = await self.coin_orders.find_one({'_id': payload, 'user_id': uid})
            if not order or not order.get('notice') or order.get('charge'):
                raise GameError('Счёт недоступен или уже оплачен. Откройте /donate.')
        await self.check(uid, stars)

    async def check(self, uid, stars):
        await self.available()
        if await self.pending(uid):
            raise GameError('Есть незавершённый платёж. Откройте /donate для восстановления; не платите повторно.')
        if stars not in PACKAGES:
            raise GameError('Неверный пакет Stars.')
        user = await self.users.find_one({'id': uid})
        if not user or user.get('is_banned'):
            raise GameError('Сначала откройте /start. Профиль должен быть доступен.')
        bank = await self.db.bank.find_one({'_id': 'single'})
        if (bank or {}).get('coins', 0) < PACKAGES[stars]:
            raise GameError('В SenseiBank недостаточно монет. Оплата недоступна.')

    async def pending(self, uid):
        for state in ('received', 'refund_required', 'fulfilled'):
            query = {'user_id': uid, 'state': state}
            if state == 'fulfilled':
                query['notice_pending'] = True
            receipt = await self.receipts.find_one(query)
            if receipt:
                return SimpleNamespace(invoice_payload=receipt['payload'], currency=receipt['currency'],
                    total_amount=receipt['stars'], telegram_payment_charge_id=receipt['_id'])
        return None

    async def receive(self, uid, payment):
        if not valid(payment.invoice_payload, uid, payment.currency, payment.total_amount):
            raise GameError('Неверный платёж SenseiCoin.')
        charge = payment.telegram_payment_charge_id
        await self.receipts.update_one({'_id': charge}, {'$setOnInsert': dict(
            user_id=uid, stars=payment.total_amount, coins=PACKAGES[payment.total_amount],
            payload=payment.invoice_payload, currency='XTR', state='received',
            created_at=datetime.now(timezone.utc))}, upsert=True)

        async def settle(tx):
            receipt = await self.receipts.find_one({'_id': charge}, session=tx)
            if (receipt['user_id'] != uid or receipt['stars'] != payment.total_amount
                    or receipt['payload'] != payment.invoice_payload):
                raise GameError('Платёж требует сверки через /paysupport.')
            if receipt['state'] != 'received':
                return receipt
            order = None
            is_order = receipt['payload'].startswith('coinbuy:v2:')
            if is_order:
                order = await self.coin_orders.find_one({'_id': receipt['payload'], 'user_id': uid}, session=tx)
                if not order or not order.get('notice') or (order.get('charge') and order['charge'] != charge):
                    await self.receipts.update_one({'_id': charge}, {'$set': {'state': 'refund_required'}}, session=tx)
                    return {**receipt, 'state': 'refund_required'}

            user = await self.users.find_one({'id': uid}, session=tx)
            coins = receipt['coins']
            bank = await self.db.bank.find_one({'_id': 'single'}, session=tx)
            if not user or user.get('is_banned') or (bank or {}).get('coins', 0) < coins:
                state = 'refund_required'
            else:
                debit = await self.db.bank.update_one({'_id': 'single', 'coins': {'$gte': coins}},
                    {'$inc': {'coins': -coins}}, session=tx)
                if debit.matched_count != 1:
                    raise GameError('Банк изменился. Платёж сохранён для сверки /paysupport.')
                await self.users.update_one({'id': uid}, {'$inc': {'coins': coins}}, session=tx)
                await self.db.transactions.update_one({'_id': f'star_coin:{charge}'},
                    {'$setOnInsert': dict(user_id=uid, tx_type='star_coin_purchase',
                        coins_change=coins, xp_change=0, created_at=datetime.now(timezone.utc))},
                    upsert=True, session=tx)
                state = 'fulfilled'
            changes = {'state': state}
            if order:
                changes['notice'] = order['notice']
                changes['notice_pending'] = True
                await self.coin_orders.update_one({'_id': receipt['payload']}, {'$set': {'charge': charge}}, session=tx)
            await self.receipts.update_one({'_id': charge}, {'$set': changes}, session=tx)
            return {**receipt, **changes}
        return await self.transaction(settle)
