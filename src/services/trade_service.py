"""Bank-funded trade game with transactional bets and payouts."""
import asyncio
import hashlib
import logging
import math
import random
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict

from pymongo.errors import DuplicateKeyError

from src.core.config import settings
from src.services.bank_ledger import _matched
from src.services.referral_economy import transaction

logger = logging.getLogger(__name__)


class TradeService:
    def __init__(self, mongo_client):
        self.mongo_client = mongo_client
        self.db = mongo_client.database
        self.users = self.db.users
        self.transactions = self.db.transactions
        self.bank = self.db.bank
        self._trade_timestamps = {}
        self._throttle_lock = asyncio.Lock()

    @staticmethod
    def _prior(receipt, user_id, bet_amount):
        if (receipt.get('user_id') != user_id or receipt.get('trade_bet') != bet_amount
                or not isinstance(receipt.get('trade_result'), dict)):
            return {'success': False, 'error': 'Этот запрос уже использован.'}
        return receipt['trade_result']

    async def play_game(self, user_id: int, bet_amount: int, *, request_id=None) -> Dict[str, Any]:
        if request_id is not None and (not isinstance(request_id, str) or not 1 <= len(request_id) <= 256):
            return {'success': False, 'error': 'Некорректный идентификатор запроса.'}
        receipt_id = 'trade:' + hashlib.sha256(request_id.encode()).hexdigest() if request_id else None
        if receipt_id:
            try:
                prior = await self.transactions.find_one({'_id': receipt_id})
                if prior:
                    return self._prior(prior, user_id, bet_amount)
            except Exception:
                logger.exception('Trade receipt could not be read user=%s', user_id)
                return {'success': False, 'error': 'Результат не подтверждён. Проверьте баланс и журнал перед повтором.'}
        async with self._throttle_lock:
            now = time.time()
            last = self._trade_timestamps.get(user_id, 0)
            if now - last < 5:
                return {'success': False, 'error': 'rate_limit', 'ttl': int(5 - (now - last))}
            self._trade_timestamps[user_id] = now
        if not isinstance(bet_amount, int) or isinstance(bet_amount, bool) or bet_amount < 1:
            return {'success': False, 'error': 'Ставка должна быть больше 0!'}
        if bet_amount > 1_000_000:
            return {'success': False, 'error': 'Максимальная ставка: 1 000 000 монет'}

        # The same outcome is retained if Mongo retries the transaction.
        is_win = random.random() < settings.trade_win_chance
        fee = int(bet_amount * .05)
        payout = (bet_amount - fee) * 2 if is_win else 0
        profit = payout - bet_amount

        async def settle(tx):
            if receipt_id:
                prior = await self.transactions.find_one({'_id': receipt_id}, session=tx)
                if prior:
                    return self._prior(prior, user_id, bet_amount)
            user = await self.users.find_one({'id': user_id}, session=tx)
            if not user:
                return {'success': False, 'error': 'Пользователь не найден. Напиши что-нибудь в чат.'}
            balance = user.get('coins', 0)
            if balance < bet_amount:
                return {'success': False, 'error': f'Недостаточно монет! У тебя: {balance:.0f}', 'balance': balance}
            accounts = []
            for bank_id, field in (('single', 'coins'), ('main', 'balance')):
                doc = await self.bank.find_one({'_id': bank_id}, session=tx)
                if doc is None:
                    continue
                value = float(doc.get(field, 0) or 0)
                if not math.isfinite(value) or value < 0:
                    raise ValueError('Invalid bank balance')
                accounts.append([bank_id, field, Decimal(str(value))])
            if not accounts:
                raise RuntimeError('Trade bank account missing')
            # Stake goes to the canonical account first, as in BankLedger.
            accounts[0][2] += Decimal(bet_amount)
            if sum((a[2] for a in accounts), Decimal(0)) < payout:
                return {'success': False, 'error': 'Банк не покрывает выигрыш. Ставка не списана.'}
            debit = await self.users.update_one({'id': user_id, 'coins': {'$gte': bet_amount}},
                                                {'$inc': {'coins': -bet_amount}}, session=tx)
            if not _matched(debit):
                raise RuntimeError('Trade stake debit missed')
            deposit = await self.bank.update_one({'_id': accounts[0][0]},
                {'$inc': {accounts[0][1]: bet_amount}}, session=tx)
            if not _matched(deposit):
                raise RuntimeError('Trade bank deposit missed')
            remaining = Decimal(payout)
            for bank_id, field, available in accounts:
                take = min(remaining, available)
                if take > 0:
                    withdrawn = await self.bank.update_one({'_id': bank_id, field: {'$gte': float(take)}},
                        {'$inc': {field: -float(take)}}, session=tx)
                    if not _matched(withdrawn):
                        raise RuntimeError('Trade bank withdrawal missed')
                    remaining -= take
            if remaining:
                raise RuntimeError('Trade withdrawal incomplete')
            if payout:
                credit = await self.users.update_one({'id': user_id}, {'$inc': {'coins': payout}}, session=tx)
                if not _matched(credit):
                    raise RuntimeError('Trade payout recipient missing')
            user_updated = await self.users.find_one({'id': user_id}, session=tx)
            result = {'success': True, 'is_win': is_win, 'profit': profit, 'balance': user_updated['coins'],
                      'fee': fee, 'bet': bet_amount, 'payout': payout}
            now_utc = datetime.now(timezone.utc)
            bet_tx = {'user_id': user_id, 'tx_type': 'purchase', 'coins_change': -float(bet_amount),
                      'description': 'Trade bet', 'created_at': now_utc}
            if receipt_id:
                bet_tx.update(_id=receipt_id, trade_bet=bet_amount, trade_result=result)
            await self.transactions.insert_one(bet_tx, session=tx)
            if is_win:
                await self.transactions.insert_one({'user_id': user_id, 'tx_type': 'game_win',
                    'coins_change': float(payout), 'description': 'Trade win', 'created_at': now_utc}, session=tx)
            return result

        try:
            return await transaction(self.mongo_client, settle)
        except DuplicateKeyError:
            if receipt_id:
                try:
                    prior = await self.transactions.find_one({'_id': receipt_id})
                    if prior:
                        return self._prior(prior, user_id, bet_amount)
                except Exception:
                    logger.exception('Trade duplicate receipt could not be read user=%s', user_id)
        except Exception:
            logger.exception('Trade result could not be confirmed user=%s', user_id)
        return {'success': False, 'error': 'Результат не подтверждён. Проверьте баланс и журнал перед повтором.'}
