"""Transactionally burn a player's coins and record an idempotent receipt."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from uuid import uuid4

from pymongo.errors import DuplicateKeyError

from src.services.emission_service import EmissionService
from src.services.hedgehog_service import GameError
from src.services.referral_economy import transaction

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
        except (TypeError, ValueError, OverflowError):
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
        if type(user_id) is not int or user_id <= 0:
            raise GameError('Открой майнер внутри Telegram.')
        amount = self._amount(amount)
        if amount <= 0:
            raise GameError('Укажи целое количество Coin больше нуля.')
        request_id = self._request_id(request_id)
        receipt_id = f'burn:{user_id}:{request_id or uuid4().hex}'

        async def work(session):
            prior = await self.transactions.find_one({'_id': receipt_id}, session=session)
            if prior:
                if abs(int(prior.get('coins_change', 0))) != amount:
                    raise GameError('Этот запрос уже использован для другой суммы.')
                return await self._receipt(prior, session, duplicate=True)
            user = await self.users.find_one({'id': user_id}, session=session)
            if not user:
                raise GameError('Профиль недоступен. Сначала открой /start.')
            if user.get('is_banned'):
                raise GameError('Сжигание недоступно для этого профиля.')
            if amount > float(user.get('coins', 0) or 0):
                raise GameError('Недостаточно Coin для сжигания.')
            debited = await self.users.update_one(
                {'id': user_id, 'is_banned': {'$ne': True}, 'coins': {'$gte': amount}},
                {'$inc': {'coins': -amount, 'burned_coins': amount}}, session=session)
            if not debited.matched_count:
                raise GameError('Баланс изменился. Обнови экран и попробуй снова.')
            if await self.emission.burn(amount, session=session) != amount:
                raise GameError('Эмиссия меньше суммы сжигания или счётчик сжиганий недоступен. Попробуй позже.')
            receipt = {'_id': receipt_id, 'user_id': user_id, 'tx_type': 'burn',
                       'coins_change': -amount, 'description': 'Voluntary SenseiCoin burn',
                       'created_at': datetime.now(timezone.utc)}
            if request_id:
                receipt['request_id'] = request_id
            await self.transactions.insert_one(receipt, session=session)
            return await self._receipt(receipt, session)

        try:
            # Initialization must happen before opening the transaction, never
            # after the player's balance is debited.
            if await self.db.bank.find_one({'_id': 'single'}) is None:
                await self.emission.ensure_state()
            return await transaction(self.mongo_client, work)
        except DuplicateKeyError:
            # A concurrent request with the same id committed first.
            prior = await self.transactions.find_one({'_id': receipt_id})
            if prior:
                if abs(int(prior.get('coins_change', 0))) != amount:
                    raise GameError('Этот запрос уже использован для другой суммы.')
                return await self._receipt(prior, None, duplicate=True)
            raise GameError('Не удалось подтвердить сжигание. Повтори запрос.')
        except GameError:
            raise
        except Exception:
            logger.exception('Atomic burn failed user=%s request=%s', user_id, request_id)
            raise GameError('Не удалось сжечь Coin. Попробуй позже.')

    async def _receipt(self, receipt, session, *, duplicate=False):
        kwargs = {'session': session} if session is not None else {}
        user = await self.users.find_one({'id': receipt['user_id']}, **kwargs) or {}
        bank = await self.db.bank.find_one({'_id': 'single'}, **kwargs) or {}
        result = {'success': True, 'amount': abs(int(receipt.get('coins_change', 0))),
                  'balance': float(user.get('coins', 0) or 0),
                  'burned_total': max(0.0, float(bank.get('burned', 0) or 0))}
        if duplicate:
            result['duplicate'] = True
        return result
