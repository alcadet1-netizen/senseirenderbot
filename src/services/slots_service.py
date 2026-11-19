"""Slot spins settled atomically against the two existing bank accounts."""
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

from src.services.bank_ledger import _matched
from src.services.referral_economy import transaction

logger = logging.getLogger(__name__)


class SlotsService:
    def __init__(self, mongo_client):
        self.mongo_client = mongo_client
        self.db = mongo_client.database
        self.users = self.db.users
        self.transactions = self.db.transactions
        self.bank = self.db.bank
        self._slots_timestamps = {}
        self._throttle_lock = asyncio.Lock()

    @staticmethod
    def _prior(prior, user_id, bet_amount):
        if prior.get('user_id') != user_id or prior.get('slot_bet') != bet_amount:
            return {'success': False, 'reason': 'request_conflict'}
        return prior['slot_result']

    async def play_slots(self, user_id: int, bet_amount: int, *, request_id=None) -> Dict[str, Any]:
        if request_id is not None and (not isinstance(request_id, str) or not 1 <= len(request_id) <= 256):
            return {'success': False, 'reason': 'request_conflict'}
        receipt_id = ('slots:' + hashlib.sha256(request_id.encode()).hexdigest()) if request_id else None
        if receipt_id:
            try:
                prior = await self.transactions.find_one({'_id': receipt_id})
            except Exception:
                logger.exception('Slot receipt could not be read for user=%s', user_id)
                return {'success': False, 'reason': 'unconfirmed'}
            if prior:
                return self._prior(prior, user_id, bet_amount)
        async with self._throttle_lock:
            now = time.time()
            last = self._slots_timestamps.get(user_id, 0)
            if now - last < 5:
                return {'success': False, 'reason': 'rate_limit', 'error': 'rate_limit', 'ttl': int(5 - (now - last))}
            self._slots_timestamps[user_id] = now
        if not isinstance(bet_amount, int) or isinstance(bet_amount, bool) or bet_amount < 1:
            return {'success': False, 'reason': 'Ставка должна быть больше 0!'}
        if bet_amount > 1_000_000:
            return {'success': False, 'reason': 'Максимальная ставка: 1 000 000 монет'}

        # Choose once, outside the callback: the Mongo driver can retry it.
        symbols = ['🍒', '🍋', '🍊', '💎', '⭐', '7️⃣']
        multipliers = {'🍒': 3, '🍋': 4, '🍊': 5, '💎': 10, '⭐': 15, '7️⃣': 20}
        roll = random.random()
        if roll < .01:
            result_symbols = ['7️⃣'] * 3
        elif roll < .33:
            result_symbols = [random.choice(symbols[:-1])] * 3
        else:
            result_symbols = random.sample(symbols, 3)
        is_win = roll < .33
        prize = bet_amount * multipliers[result_symbols[0]] if is_win else 0
        fee = int(bet_amount * .05)

        async def settle(tx):
            if receipt_id:
                prior = await self.transactions.find_one({'_id': receipt_id}, session=tx)
                if prior:
                    return self._prior(prior, user_id, bet_amount)
            user = await self.users.find_one({'id': user_id}, session=tx)
            if not user:
                return {'success': False, 'reason': 'user_not_found'}
            if user.get('coins', 0) < bet_amount:
                return {'success': False, 'reason': 'insufficient_funds', 'balance': user.get('coins', 0)}
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
                raise ValueError('Bank account is missing')
            # The stake goes to the canonical account first, or legacy if the
            # canonical account does not exist, as in BankLedger.deposit.
            accounts[0][2] += Decimal(bet_amount)
            if sum((account[2] for account in accounts), Decimal(0)) < prize:
                # Nothing has been written: the bet stays with the player.
                return {'success': False, 'reason': 'bank_empty'}
            debit = await self.users.update_one({'id': user_id, 'coins': {'$gte': bet_amount}},
                                                {'$inc': {'coins': -bet_amount}}, session=tx)
            if not _matched(debit):
                raise RuntimeError('Slot bet debit missed')
            deposit = await self.bank.update_one({'_id': accounts[0][0]},
                {'$inc': {accounts[0][1]: bet_amount}}, session=tx)
            if not _matched(deposit):
                raise RuntimeError('Slot bank deposit missed')
            remaining = Decimal(prize)
            for bank_id, field, available in accounts:
                take = min(remaining, available)
                if take > 0:
                    withdrawn = await self.bank.update_one({'_id': bank_id, field: {'$gte': float(take)}},
                        {'$inc': {field: -float(take)}}, session=tx)
                    if not _matched(withdrawn):
                        raise RuntimeError('Slot bank withdrawal missed')
                    remaining -= take
            if remaining:
                raise RuntimeError('Slot bank withdrawal incomplete')
            if prize:
                credited = await self.users.update_one({'id': user_id}, {'$inc': {'coins': prize}}, session=tx)
                if not _matched(credited):
                    raise RuntimeError('Slot user credit missed')
            now_utc = datetime.now(timezone.utc)
            updated = await self.users.find_one({'id': user_id}, session=tx)
            result = {'success': True, 'is_win': is_win, 'prize': prize, 'bet': bet_amount,
                      'fee': fee, 'symbols': result_symbols, 'balance': updated['coins']}
            entry = {'user_id': user_id, 'tx_type': 'slots_bet', 'coins_change': -float(bet_amount),
                     'description': 'Slots bet', 'created_at': now_utc}
            if receipt_id:
                entry.update(_id=receipt_id, slot_bet=bet_amount, slot_result=result)
            await self.transactions.insert_one(entry, session=tx)
            if is_win:
                await self.transactions.insert_one({'user_id': user_id, 'tx_type': 'slots_win',
                    'coins_change': float(prize), 'description': f"Slots win: {''.join(result_symbols)}",
                    'created_at': now_utc}, session=tx)
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
                    logger.exception('Slot receipt could not be confirmed for user=%s', user_id)
            return {'success': False, 'reason': 'unconfirmed'}
        except Exception:
            logger.exception('Slot outcome could not be confirmed for user=%s', user_id)
            return {'success': False, 'reason': 'unconfirmed'}
