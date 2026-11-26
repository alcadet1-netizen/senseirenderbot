"""Bank-funded Coin/ticket exchange with transactional settlement."""
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import logging
import math
import secrets

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from src.domain.tickets import active_ticket_filter
from src.core.constants import EXCHANGE_COINS_TO_TICKET, EXCHANGE_TICKET_TO_COINS
from src.core.exceptions import InsufficientFundsError, InsufficientTicketsError
from src.infra.mongo.client import MongoClient
from src.services.referral_economy import transaction

logger = logging.getLogger(__name__)


class ExchangeService:
    def __init__(self, mongo_client: MongoClient):
        self.mongo_client = mongo_client
        self.db = mongo_client.database
        self.users = self.db.users
        self.transactions = self.db.transactions
        self.bank = self.db.bank
        self.tickets = self.db.tickets

    @staticmethod
    def _receipt_id(request_id):
        if request_id is None:
            return None
        if not isinstance(request_id, str) or not 1 <= len(request_id) <= 256:
            raise ValueError('Invalid exchange request')
        return 'exchange:' + hashlib.sha256(request_id.encode()).hexdigest()

    @staticmethod
    def _prior_result(prior, user_id, direction):
        if prior.get('user_id') != user_id or prior.get('exchange_direction') != direction or not isinstance(prior.get('exchange_result'), dict):
            return {'success': False, 'error': 'Этот запрос уже использован.'}
        return prior['exchange_result']

    async def _exchange(self, user_id, direction, request_id):
        receipt_id = self._receipt_id(request_id)
        now = datetime.now(timezone.utc)
        ticket_code = f'TICKET-{secrets.token_hex(8).upper()}'

        async def settle(session):
            if receipt_id:
                prior = await self.transactions.find_one({'_id': receipt_id}, session=session)
                if prior:
                    return self._prior_result(prior, user_id, direction)
            user = await self.users.find_one({'id': user_id}, session=session)
            if not user:
                return {'success': False, 'error': 'Пользователь не найден.'}
            balance = user.get('coins', 0)
            if direction == 'coins_to_ticket':
                if balance < EXCHANGE_COINS_TO_TICKET:
                    raise InsufficientFundsError(EXCHANGE_COINS_TO_TICKET, balance)
                debit = await self.users.update_one(
                    {'id': user_id, 'coins': {'$gte': EXCHANGE_COINS_TO_TICKET}},
                    {'$inc': {'coins': -EXCHANGE_COINS_TO_TICKET}}, session=session)
                if debit.matched_count != 1:
                    raise RuntimeError('User balance changed during exchange')
                # Keep the existing canonical-first choice without creating a bank.
                canonical = await self.bank.find_one({'_id': 'single'}, session=session)
                legacy = await self.bank.find_one({'_id': 'main'}, session=session) if canonical is None else None
                if canonical is not None:
                    bank_id, field = 'single', 'coins'
                elif legacy is not None:
                    bank_id, field = 'main', 'balance'
                else:
                    raise RuntimeError('No bank account available')
                deposited = await self.bank.update_one({'_id': bank_id},
                    {'$inc': {field: EXCHANGE_COINS_TO_TICKET}}, session=session)
                if deposited.matched_count != 1:
                    raise RuntimeError('Bank disappeared during exchange')
                await self.tickets.insert_one({'user_id': user_id, 'code': ticket_code,
                                               'created_at': now, 'burned': False, 'is_burned': False}, session=session)
                result = {'success': True, 'direction': direction,
                          'coins_spent': EXCHANGE_COINS_TO_TICKET, 'ticket_code': ticket_code,
                          'new_coins_balance': balance - EXCHANGE_COINS_TO_TICKET}
                change, tx_type = -EXCHANGE_COINS_TO_TICKET, 'exchange_in'
                description = f'Exchange: {EXCHANGE_COINS_TO_TICKET} coins → 1 ticket'
            else:
                ticket = await self.tickets.find_one_and_update(
                    active_ticket_filter(user_id=user_id),
                    {'$set': {'burned': True, 'is_burned': True, 'burned_at': now, 'burn_reason': 'exchange'}},
                    sort=[('_id', 1)], return_document=ReturnDocument.BEFORE, session=session)
                if not ticket:
                    raise InsufficientTicketsError(1, 0)
                accounts = []
                for bank_id, field in (('single', 'coins'), ('main', 'balance')):
                    doc = await self.bank.find_one({'_id': bank_id}, session=session) or {}
                    value = float(doc.get(field, 0) or 0)
                    if not math.isfinite(value):
                        raise ValueError('Invalid bank balance')
                    accounts.append((bank_id, field, Decimal(str(max(0.0, value)))))
                remaining = Decimal(EXCHANGE_TICKET_TO_COINS)
                if sum((entry[2] for entry in accounts), Decimal(0)) < remaining:
                    # Exception aborts the already tentatively burned ticket.
                    raise _BankEmpty()
                for bank_id, field, available in accounts:
                    take = min(available, remaining)
                    if take <= 0:
                        continue
                    debit = await self.bank.update_one({'_id': bank_id, field: {'$gte': float(take)}},
                                                       {'$inc': {field: -float(take)}}, session=session)
                    if debit.matched_count != 1:
                        raise RuntimeError('Bank balance changed during exchange')
                    remaining -= take
                credited = await self.users.update_one({'id': user_id},
                    {'$inc': {'coins': EXCHANGE_TICKET_TO_COINS}}, session=session)
                if credited.matched_count != 1:
                    raise RuntimeError('User disappeared during exchange')
                result = {'success': True, 'direction': direction, 'ticket_burned': ticket['code'],
                          'coins_received': EXCHANGE_TICKET_TO_COINS,
                          'new_coins_balance': balance + EXCHANGE_TICKET_TO_COINS}
                change, tx_type = EXCHANGE_TICKET_TO_COINS, 'exchange_out'
                description = f'Exchange: 1 ticket → {EXCHANGE_TICKET_TO_COINS} coins'
            entry = {'user_id': user_id, 'tx_type': tx_type, 'coins_change': change,
                     'description': description, 'created_at': now}
            if receipt_id:
                entry.update(_id=receipt_id, exchange_direction=direction, exchange_result=result)
            await self.transactions.insert_one(entry, session=session)
            return result

        try:
            return await transaction(self.mongo_client, settle)
        except _BankEmpty:
            return {'success': False, 'error': 'Банк временно пуст.'}
        except DuplicateKeyError:
            if receipt_id:
                prior = await self.transactions.find_one({'_id': receipt_id})
                if prior:
                    return self._prior_result(prior, user_id, direction)
            logger.error('Exchange duplicate key without confirmed receipt')
            return {'success': False, 'error': 'Не удалось подтвердить обмен. Проверьте баланс и билеты перед повтором.'}
        except (InsufficientFundsError, InsufficientTicketsError):
            raise
        except Exception:
            logger.exception('Exchange outcome could not be confirmed')
            return {'success': False, 'error': 'Не удалось подтвердить обмен. Проверьте баланс и билеты перед повтором.'}

    async def coins_to_ticket(self, user_id: int, request_id=None) -> dict:
        return await self._exchange(user_id, 'coins_to_ticket', request_id)

    async def ticket_to_coins(self, user_id: int, request_id=None) -> dict:
        return await self._exchange(user_id, 'ticket_to_coins', request_id)

    async def get_exchange_rates(self) -> dict:
        return {
            'coins_to_ticket': {'from': EXCHANGE_COINS_TO_TICKET, 'to': 1,
                                'from_currency': 'coins', 'to_currency': 'ticket'},
            'ticket_to_coins': {'from': 1, 'to': EXCHANGE_TICKET_TO_COINS,
                                'from_currency': 'ticket', 'to_currency': 'coins'},
        }


class _BankEmpty(Exception):
    pass
