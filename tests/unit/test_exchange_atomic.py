"""Exchange failures and duplicate callbacks on a rollback-capable fake."""
import asyncio
import copy
from types import SimpleNamespace as NS
from uuid import uuid4

import pytest
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from src.services.exchange_service import ExchangeService
from tests.unit.test_paid_hedgehog import TxCollection, Session


class ExchangeCollection(TxCollection):
    async def insert_one(self, document, **kwargs):
        document = copy.deepcopy(document)
        key = document.setdefault('_id', uuid4().hex)
        if key in self.docs:
            raise DuplicateKeyError('duplicate')
        self.docs[key] = document
        return NS(inserted_id=key)

    async def find_one_and_update(self, query, changes, upsert=False, **kwargs):
        before = await self.find_one(query)
        updated = await super().find_one_and_update(query, changes, upsert=upsert, **kwargs)
        return before if kwargs.get('return_document') == ReturnDocument.BEFORE else updated


def fixture():
    db = NS(users=ExchangeCollection([{'id': 7, 'coins': 6000}]),
            bank=ExchangeCollection([{'_id': 'single', 'coins': 100, 'total_emitted': 10000, 'burned': 20},
                                     {'_id': 'main', 'balance': 500}]),
            tickets=ExchangeCollection(), transactions=ExchangeCollection(), lock=asyncio.Lock())
    async def start(): return Session(db)
    db.client = NS(start_session=start)
    return db, ExchangeService(NS(database=db))


@pytest.mark.asyncio
async def test_purchase_redemption_and_duplicate_callbacks_conserve_coins():
    db, svc = fixture()
    first = await svc.coins_to_ticket(7, 'buy')
    assert first == await svc.coins_to_ticket(7, 'buy')
    assert len(db.tickets.docs) == 1 and len(db.transactions.docs) == 1
    assert db.users.docs[7]['coins'] == 3000 and db.bank.docs['single']['coins'] == 3100
    assert not (await svc.ticket_to_coins(7, 'buy'))['success']
    sold = await svc.ticket_to_coins(7, 'sell')
    assert sold == await svc.ticket_to_coins(7, 'sell')
    assert db.users.docs[7]['coins'] == 5600 and db.bank.docs['single']['coins'] == 500
    assert next(iter(db.tickets.docs.values()))['burned'] is True
    assert db.bank.docs['single']['total_emitted'] == 10000


@pytest.mark.asyncio
async def test_failed_journal_rolls_back_and_reports_ambiguous_outcome():
    db, svc = fixture()
    async def fail(*args, **kwargs): raise RuntimeError('journal unavailable')
    svc.transactions.insert_one = fail
    assert not (await svc.coins_to_ticket(7))['success']
    assert db.users.docs[7]['coins'] == 6000
    assert db.bank.docs['single']['coins'] == 100
    assert not db.tickets.docs


@pytest.mark.asyncio
async def test_empty_bank_does_not_burn_ticket():
    db, svc = fixture()
    await db.tickets.insert_one({'user_id': 7, 'code': 'A', 'burned': False})
    result = await svc.ticket_to_coins(7, 'sell')
    assert not result['success'] and 'Банк' in result['error']
    assert not next(iter(db.tickets.docs.values()))['burned']
    assert db.users.docs[7]['coins'] == 6000
    assert not db.transactions.docs


@pytest.mark.asyncio
async def test_redemption_draws_both_bank_accounts():
    db, svc = fixture()
    db.bank.docs['single']['coins'] = 1000
    db.bank.docs['main']['balance'] = 2000
    await db.tickets.insert_one({'user_id': 7, 'code': 'A', 'burned': False})
    assert (await svc.ticket_to_coins(7, 'sell'))['success']
    assert db.bank.docs['single']['coins'] == 0
    assert db.bank.docs['main']['balance'] == 400
    assert db.users.docs[7]['coins'] == 8600


@pytest.mark.asyncio
async def test_user_without_coin_or_ticket_is_not_debited():
    from src.core.exceptions import InsufficientFundsError, InsufficientTicketsError
    db, svc = fixture()
    db.users.docs[7]['coins'] = 10
    with pytest.raises(InsufficientFundsError):
        await svc.coins_to_ticket(7, 'buy')
    with pytest.raises(InsufficientTicketsError):
        await svc.ticket_to_coins(7, 'sell')
    assert db.users.docs[7]['coins'] == 10
    assert db.bank.docs['single']['coins'] == 100
    assert not db.transactions.docs
