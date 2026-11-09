"""Versioned Stars packages; Mongo receipt and bank transfer, never coin emission."""
from datetime import datetime, timezone
from types import SimpleNamespace

from src.services.paid_hedgehog_service import PaidHedgehogService
from src.services.hedgehog_service import GameError

PACKAGES = {1: 500, 5: 3500, 10: 8000, 50: 45000}
PREFIX = 'coinbuy:v1:'


def valid(payload, uid, currency, stars):
    return currency == 'XTR' and stars in PACKAGES and payload == f'{PREFIX}{uid}:{stars}'


class StarCoinService(PaidHedgehogService):
    def __init__(self, mongo):
        super().__init__(mongo)
        self.receipts = self.db.star_coin_payments

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
        for state in ('received', 'refund_required'):
            receipt = await self.receipts.find_one({'user_id': uid, 'state': state})
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
            await self.receipts.update_one({'_id': charge}, {'$set': {'state': state}}, session=tx)
            return {**receipt, 'state': state}
        return await self.transaction(settle)
