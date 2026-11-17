"""Voluntary SenseiCoin burning — the only path that destroys emission.

Burning is deliberately separate from the bank flow: a player spends coins
from their own balance, those coins never enter SenseiBank, and the global
``total_emitted`` counter is reduced by the same amount.  A failed counter
update refunds the player, so the ledger never claims more burn than happened.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from src.services.emission_service import EmissionService
from src.services.hedgehog_service import GameError

logger = logging.getLogger(__name__)
BURN_REQUEST_RE = re.compile(r'[A-Za-z0-9_-]{8,64}')


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

    @staticmethod
    def _request_id(value) -> str:
        if value is None:
            return ''
        if not isinstance(value, str) or not BURN_REQUEST_RE.fullmatch(value):
            raise GameError('Неверный запрос сжигания. Открой окно заново.')
        return value

    async def burn(self, user_id: int, amount, request_id=None) -> dict:
        """Burn ``amount`` of the player's own coins, atomically per step.

        The optional ``request_id`` makes a retried HTTP request safe: the
        debit stores the id on the user, and a duplicate returns the previous
        receipt instead of burning the same coins twice.  If the emission
        counter cannot be reduced, the debit is refunded and the id is cleared.
        """
        if type(user_id) is not int or user_id <= 0:
            raise GameError('Открой майнер внутри Telegram.')
        amount = self._amount(amount)
        if amount <= 0:
            raise GameError('Укажи целое количество Coin больше нуля.')
        request_id = self._request_id(request_id)
        if request_id:
            prior = await self._prior_receipt(user_id, request_id)
            if prior:
                return prior
        user = await self.users.find_one({'id': user_id})
        if not user:
            raise GameError('Профиль недоступен. Сначала открой /start.')
        if user.get('is_banned'):
            raise GameError('Сжигание недоступно для этого профиля.')
        available = max(0.0, float(user.get('coins', 0) or 0))
        if amount > available:
            raise GameError('Недостаточно Coin для сжигания.')

        query = {'id': user_id, 'is_banned': {'$ne': True},
                 'coins': {'$gte': amount}}
        changes = {'$inc': {'coins': -amount, 'burned_coins': amount}}
        if request_id:
            # The id is written together with the debit, so a concurrent
            # duplicate cannot pass this compare-and-set.
            query['last_burn_request'] = {'$ne': request_id}
            changes['$set'] = {'last_burn_request': request_id,
                               'last_burn_at': datetime.now(timezone.utc)}
        debited = await self.users.update_one(query, changes)
        matched = getattr(debited, 'matched_count', None)
        if debited is None or (isinstance(matched, int) and matched == 0):
            if request_id:
                current = await self.users.find_one({'id': user_id}) or {}
                if current.get('last_burn_request') == request_id:
                    prior = await self._prior_receipt(user_id, request_id)
                    if prior:
                        return prior
                    raise GameError(
                        'Сжигание уже обрабатывается. Подожди и обнови экран.')
            raise GameError('Баланс изменился. Обнови экран и попробуй снова.')

        burned = 0.0
        try:
            burned = float(await self.emission.burn(amount))
        except Exception:
            logger.exception('SenseiCoin burn counter failed user=%s amount=%s',
                             user_id, amount)
            await self._refund(user_id, amount, request_id)
            raise GameError('Не удалось сжечь Coin. Попробуй позже.')

        burned_int = int(max(0.0, min(float(amount), burned)))
        if burned_int < amount:
            # Never keep coins that were not actually removed from supply.
            await self._refund(user_id, amount - burned_int,
                               request_id if burned_int <= 0 else '')
        if burned_int <= 0:
            raise GameError('Эмиссия уже не может быть уменьшена.')
        transaction = {
            'user_id': user_id,
            'tx_type': 'burn',
            'coins_change': -burned_int,
            'description': 'Voluntary SenseiCoin burn',
            'created_at': datetime.now(timezone.utc),
        }
        if request_id:
            transaction['_id'] = f'burn:{user_id}:{request_id}'
            transaction['request_id'] = request_id
        try:
            await self.transactions.insert_one(transaction)
        except Exception:
            # The debit is already applied; a deterministic _id still prevents
            # a retry from creating a second burn receipt.
            logger.exception('Burn transaction log failed user=%s', user_id)
        current = await self.users.find_one({'id': user_id}) or {}
        return {
            'success': True,
            'amount': burned_int,
            'balance': float(current.get('coins', available - burned_int)),
            'burned_total': float((await self._bank_burned()) or 0),
        }

    async def _prior_receipt(self, user_id: int, request_id: str) -> dict | None:
        prior = await self.transactions.find_one({
            '_id': f'burn:{user_id}:{request_id}'})
        if not prior:
            # Older rows (or test doubles) may not expose the deterministic _id.
            prior = await self.transactions.find_one({
                'user_id': user_id, 'tx_type': 'burn',
                'request_id': request_id})
        if not prior:
            return None
        try:
            amount = abs(int(prior.get('coins_change', 0) or 0))
        except (TypeError, ValueError):
            amount = 0
        current = await self.users.find_one({'id': user_id}) or {}
        return {
            'success': True,
            'amount': amount,
            'balance': float(current.get('coins', 0) or 0),
            'burned_total': float((await self._bank_burned()) or 0),
            'duplicate': True,
        }

    async def _refund(self, user_id: int, amount: int,
                      request_id: str = '') -> None:
        if amount <= 0:
            return
        await self.users.update_one(
            {'id': user_id},
            {'$inc': {'coins': amount, 'burned_coins': -amount}},
        )
        if request_id:
            await self.users.update_one(
                {'id': user_id, 'last_burn_request': request_id},
                {'$set': {'last_burn_request': None}},
            )

    async def _bank_burned(self) -> float:
        doc = await self.db.bank.find_one({'_id': 'single'}) or {}
        try:
            return max(0.0, float(doc.get('burned', 0) or 0))
        except (TypeError, ValueError):
            return 0.0
