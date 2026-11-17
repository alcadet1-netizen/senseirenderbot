"""Stars-funded permanent upgrades for the dojo miner.

Payments are receipts, not button presses: Telegram's successful_payment is
stored first, then the upgrade is applied with one atomic user-document update
guarded by the charge id. Retries are therefore idempotent without requiring a
replica-set transaction.
"""
import re
import secrets
import time
from datetime import datetime, timezone

from src.services.dojo_miner_service import (
    BASE_ENERGY,
    BASE_RATE,
    ENERGY_MAX_PURCHASES,
    ENERGY_REFILL_AMOUNT,
    ENERGY_REFILL_STARS,
    PICKAXE_MAX_LEVEL,
    PICKAXE_STEP,
    SPEED_BOOST_SECONDS,
    SPEED_BOOST_PERCENT,
    SPEED_BOOST_STARS,
)
from src.services.hedgehog_service import GameError

PICKAXE_STARS = 10
ENERGY_STARS = 50
AUTOCOLLECT_STARS = 1000
BOOST_STARS = SPEED_BOOST_STARS
KINDS = {
    'pickaxe': {
        'stars': PICKAXE_STARS,
        'title': 'Кирка +10 Coin/ч',
        'description': 'Постоянный бонус +10 SenseiCoin в час. Действует со следующего цикла.',
    },
    'energy': {
        'stars': ENERGY_STARS,
        'title': 'Энергия +100',
        'description': 'Навсегда +100 к запасу энергии. 100 энергии — час полной мощности; действует со следующего цикла.',
    },
    'auto': {
        'stars': AUTOCOLLECT_STARS,
        'title': 'Автосбор',
        'description': 'Автоматически собирает награду и запускает новый цикл каждые 4 часа.',
    },
    'refill': {
        'stars': ENERGY_REFILL_STARS,
        'title': 'Пополнение энергии',
        'description': 'Мгновенно +100 энергии в текущем цикле, если энергия уже на нуле.',
    },
    'boost': {
        'stars': BOOST_STARS,
        'title': 'Скорость +50% на 2 часа',
        'description': 'Ускоряет добычу на 50% на два часа. Повторная покупка добавляет только часы — процент не растёт.',
    },
}
PAYLOAD_PREFIX = 'dojobuy:v1:'
PAYLOAD_RE = re.compile(
    r'^dojobuy:v1:(\d+):(pickaxe|energy|auto|refill|boost):(\d+):([a-f0-9]{24})$')


def payload_kind(payload: str) -> str:
    match = PAYLOAD_RE.fullmatch(payload or '')
    return match.group(2) if match else ''


class DojoUpgradeService:
    def __init__(self, container):
        self.container = container
        self.db = container.mongo_client.database
        self.users = self.db.users
        self.orders = self.db.dojo_orders
        self.payments = self.db.dojo_payments


    async def snapshot(self, user_id: int) -> dict:
        user = await self.users.find_one({'id': user_id}) or {}
        level = max(0, min(PICKAXE_MAX_LEVEL, int(user.get('dojo_pickaxe_level', 0) or 0)))
        purchases = max(0, min(ENERGY_MAX_PURCHASES,
                               int(user.get('dojo_energy_purchases', 0) or 0)))
        now = time.time()
        boost_until = float(user.get('dojo_boost_until', 0) or 0)
        return {
            'pickaxe_level': level,
            'pickaxe_max': PICKAXE_MAX_LEVEL,
            'pickaxe_rate': BASE_RATE + level * PICKAXE_STEP,
            'pickaxe_next_rate': BASE_RATE + min(PICKAXE_MAX_LEVEL, level + 1) * PICKAXE_STEP,
            'pickaxe_stars': PICKAXE_STARS,
            'energy_purchases': purchases,
            'energy_max_purchases': ENERGY_MAX_PURCHASES,
            'energy_bonus': purchases * 100,
            'energy_stars': ENERGY_STARS,
            'auto_collect': bool(user.get('dojo_auto_collect')),
            'auto_stars': AUTOCOLLECT_STARS,
            'base_energy': BASE_ENERGY,
            'energy_refill_stars': ENERGY_REFILL_STARS,
            'energy_refill_amount': ENERGY_REFILL_AMOUNT,
            'boost_stars': BOOST_STARS,
            'boost_percent': SPEED_BOOST_PERCENT,
            'boost_hours': SPEED_BOOST_SECONDS // 3600,
            'boost_until': boost_until,
            'boost_active': boost_until > now,
            'boost_seconds_left': max(0, int(boost_until - now)),
        }

    async def prepare(self, user_id: int, kind: str) -> dict:
        if kind not in KINDS:
            raise GameError('Неизвестное улучшение.')
        user = await self.users.find_one({'id': user_id})
        if not user or user.get('is_banned'):
            raise GameError('Профиль недоступен. Сначала открой /start.')
        await self._check_available(kind, user)
        spec = KINDS[kind]
        payload = (f'{PAYLOAD_PREFIX}{user_id}:{kind}:{spec["stars"]}:'
                   f'{secrets.token_hex(12)}')
        await self.orders.update_one(
            {'_id': payload},
            {'$setOnInsert': {
                'user_id': user_id,
                'kind': kind,
                'stars': spec['stars'],
                'state': 'created',
                'created_at': datetime.now(timezone.utc),
            }},
            upsert=True,
        )
        return {**spec, 'payload': payload, 'kind': kind}

    async def checkout(self, payload: str, user_id: int, currency: str, stars: int) -> None:
        match = PAYLOAD_RE.fullmatch(payload or '')
        if (not match or currency != 'XTR'
                or int(match.group(1)) != user_id
                or int(match.group(3)) != stars
                or match.group(2) not in KINDS
                or KINDS[match.group(2)]['stars'] != stars):
            raise GameError('Неверный счёт улучшения. Открой «Улучшения» заново.')
        kind = match.group(2)
        order = await self.orders.find_one({'_id': payload, 'user_id': user_id})
        if (not order or order.get('kind') != kind
                or order.get('stars') != stars
                or order.get('state') == 'fulfilled'):
            raise GameError('Счёт уже использован или устарел.')
        user = await self.users.find_one({'id': user_id})
        if not user or user.get('is_banned'):
            raise GameError('Профиль недоступен.')
        await self._check_available(kind, user)
        await self.orders.update_one(
            {'_id': payload, 'user_id': user_id},
            {'$set': {'state': 'checkout', 'checkout_at': datetime.now(timezone.utc)}},
        )

    async def receive(self, user_id: int, payment) -> dict:
        match = PAYLOAD_RE.fullmatch(payment.invoice_payload or '')
        if (not match or payment.currency != 'XTR'
                or int(match.group(1)) != user_id
                or int(match.group(3)) != payment.total_amount
                or match.group(2) not in KINDS
                or KINDS[match.group(2)]['stars'] != payment.total_amount):
            raise GameError('Неверный платёж улучшения.')
        charge = payment.telegram_payment_charge_id
        kind = match.group(2)
        order = await self.orders.find_one(
            {'_id': payment.invoice_payload, 'user_id': user_id})
        if (not order or order.get('kind') != kind
                or order.get('stars') != payment.total_amount):
            raise GameError('Счёт улучшения не найден. Не оплачивайте повторно.')
        await self.payments.update_one(
            {'_id': charge},
            {'$setOnInsert': {
                'user_id': user_id,
                'payload': payment.invoice_payload,
                'kind': kind,
                'stars': payment.total_amount,
                'currency': payment.currency,
                'state': 'received',
                'created_at': datetime.now(timezone.utc),
            }},
            upsert=True,
        )
        receipt = await self.payments.find_one({'_id': charge})
        if receipt['state'] in {'fulfilled', 'refunded', 'refund_required'}:
            return receipt
        if order.get('state') == 'fulfilled' and order.get('charge') != charge:
            state = 'refund_required'
            applied = False
        else:
            applied = await self._apply(user_id, kind, charge)
        state = 'fulfilled' if applied else 'refund_required'
        changes = {'state': state, 'settled_at': datetime.now(timezone.utc)}
        await self.payments.update_one({'_id': charge}, {'$set': changes})
        await self.orders.update_one(
            {'_id': payment.invoice_payload, 'user_id': user_id},
            {'$set': {'state': state, 'charge': charge}},
        )
        return {**receipt, **changes}

    async def mark_refunded(self, charge: str) -> None:
        await self.payments.update_one(
            {'_id': charge}, {'$set': {'state': 'refunded'}})

    async def _apply(self, user_id: int, kind: str, charge: str) -> bool:
        if kind == 'refill':
            return await self.container.dojo_miner_service.apply_energy_refill(
                user_id, charge)
        if kind == 'boost':
            return await self.container.dojo_miner_service.apply_speed_boost(
                user_id, charge)
        base = {
            'id': user_id,
            'is_banned': {'$ne': True},
            'dojo_applied_receipts': {'$ne': charge},
        }
        if kind == 'pickaxe':
            # A missing level counts as zero, so $exists/$lt is used instead
            # of a single $lt condition (which would not match missing fields).
            query = {
                **base,
                '$or': [
                    {'dojo_pickaxe_level': {'$exists': False}},
                    {'dojo_pickaxe_level': {'$lt': PICKAXE_MAX_LEVEL}},
                ],
            }
            update = {
                '$inc': {'dojo_pickaxe_level': 1},
                '$addToSet': {'dojo_applied_receipts': charge},
            }
        elif kind == 'energy':
            query = {
                **base,
                '$or': [
                    {'dojo_energy_purchases': {'$exists': False}},
                    {'dojo_energy_purchases': {'$lt': ENERGY_MAX_PURCHASES}},
                ],
            }
            update = {
                '$inc': {'dojo_energy_purchases': 1},
                '$addToSet': {'dojo_applied_receipts': charge},
            }
        elif kind == 'auto':
            query = {**base, 'dojo_auto_collect': {'$ne': True}}
            update = {
                '$set': {'dojo_auto_collect': True},
                '$addToSet': {'dojo_applied_receipts': charge},
            }
        else:
            return False
        result = await self.users.update_one(query, update)
        if getattr(result, 'matched_count', None) == 1:
            return True
        user = await self.users.find_one({'id': user_id})
        if not user or user.get('is_banned'):
            return False
        return charge in (user.get('dojo_applied_receipts') or [])

    async def _check_available(self, kind: str, user: dict) -> None:
        level = int(user.get('dojo_pickaxe_level', 0) or 0)
        purchases = int(user.get('dojo_energy_purchases', 0) or 0)
        if kind == 'pickaxe' and level >= PICKAXE_MAX_LEVEL:
            raise GameError('Кирка уже прокачана до 100 уровня.')
        if kind == 'energy' and purchases >= ENERGY_MAX_PURCHASES:
            raise GameError('Достигнут максимум покупок энергии.')
        if kind == 'auto' and user.get('dojo_auto_collect'):
            raise GameError('Автосбор уже включён навсегда.')
        if kind == 'refill':
            state = await self.container.dojo_miner_service.state(user['id'])
            if state.get('phase') != 'mining' or int(state.get('energy', 0)) > 0:
                raise GameError('Пополнить можно только при нулевой энергии.')
        if kind == 'boost' and not user.get('id'):
            raise GameError('Профиль недоступен.')
