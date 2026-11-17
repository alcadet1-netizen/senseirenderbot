"""Voluntary SenseiCoin burning — the only path that destroys emission.

Burning is deliberately separate from the bank flow: a player spends coins
from their own balance, those coins never enter SenseiBank, and the global
``total_emitted`` counter is reduced by the same amount.  A failed counter
update refunds the player, so the ledger never claims more burn than happened.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from src.services.emission_service import EmissionService
from src.services.hedgehog_service import GameError

logger = logging.getLogger(__name__)


class BurnService:
    def __init__(self, mongo_client):
        self.mongo_client = mongo_client
        self.db = mongo_client.database
        self.users = self.db.users
        self.transactions = self.db.transactions
        self.emission = EmissionService(mongo_client)

    @staticmethod
    def _amount(value) -> int:
        if isinstance(value, bool):
            return 0
        try:
            amount = int(value)
        except (TypeError, ValueError):
            return 0
        if isinstance(value, float) and not value.is_integer():
            return 0
        return amount if amount > 0 else 0

    async def burn(self, user_id: int, amount) -> dict:
        """Burn ``amount`` of the player's own coins, atomically per step.

        The user debit is a compare-and-set, so two concurrent taps can never
        spend the same coins.  If the emission counter cannot be reduced, the
        debit is refunded before the error is returned.
        """
        if type(user_id) is not int or user_id <= 0:
            raise GameError('Открой майнер внутри Telegram.')
        amount = self._amount(amount)
        if amount <= 0:
            raise GameError('Укажи целое количество Coin больше нуля.')
        user = await self.users.find_one({'id': user_id})
        if not user:
            raise GameError('Профиль недоступен. Сначала открой /start.')
        if user.get('is_banned'):
            raise GameError('Сжигание недоступно для этого профиля.')
        available = max(0.0, float(user.get('coins', 0) or 0))
        if amount > available:
            raise GameError('Недостаточно Coin для сжигания.')

        debited = await self.users.update_one(
            {'id': user_id, 'is_banned': {'$ne': True},
             'coins': {'$gte': amount}},
            {'$inc': {'coins': -amount, 'burned_coins': amount}},
        )
        matched = getattr(debited, 'matched_count', None)
        if debited is None or (isinstance(matched, int) and matched == 0):
            raise GameError('Баланс изменился. Обнови экран и попробуй снова.')

        burned = 0.0
        try:
            burned = float(await self.emission.burn(amount))
        except Exception:
            logger.exception('SenseiCoin burn counter failed user=%s amount=%s',
                             user_id, amount)
            await self._refund(user_id, amount)
            raise GameError('Не удалось сжечь Coin. Попробуй позже.')

        burned_int = int(max(0.0, min(float(amount), burned)))
        if burned_int < amount:
            # Never keep coins that were not actually removed from supply.
            await self._refund(user_id, amount - burned_int)
        if burned_int <= 0:
            raise GameError('Эмиссия уже не может быть уменьшена.')
        try:
            await self.transactions.insert_one({
                'user_id': user_id,
                'tx_type': 'burn',
                'coins_change': -burned_int,
                'description': 'Voluntary SenseiCoin burn',
                'created_at': datetime.now(timezone.utc),
            })
        except Exception:
            logger.exception('Burn transaction log failed user=%s', user_id)
        current = await self.users.find_one({'id': user_id}) or {}
        return {
            'success': True,
            'amount': burned_int,
            'balance': float(current.get('coins', available - burned_int)),
            'burned_total': float((await self._bank_burned()) or 0),
        }

    async def _refund(self, user_id: int, amount: int) -> None:
        if amount <= 0:
            return
        await self.users.update_one(
            {'id': user_id},
            {'$inc': {'coins': amount, 'burned_coins': -amount}},
        )

    async def _bank_burned(self) -> float:
        doc = await self.db.bank.find_one({'_id': 'single'}) or {}
        try:
            return max(0.0, float(doc.get('burned', 0) or 0))
        except (TypeError, ValueError):
            return 0.0
