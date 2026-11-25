"""Снятие банов, выданных за отписку от канала задания.

Отписка от канала — не нарушение: игрок выполнил «подпишись» и вправе
отписаться. Восстановление трогает только автобаны за выход из чата и
возвращает конфискованное из банка.
"""
import copy
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.services.bank_ledger import BankLedger
from src.services.moderation_service import AUTO_BAN_REASON, ModerationService
from tests.unit.test_hedgehog_game import Collection


class Transactions(Collection):
    async def insert_one(self, doc):
        self.docs[doc.setdefault('_id', f'tx-{len(self.docs)}')] = copy.deepcopy(doc)
        return SimpleNamespace(inserted_id=doc['_id'])


class Users(Collection):
    def find(self, query):
        items = [copy.deepcopy(doc) for doc in self.docs.values()
                 if all(doc.get(k) == v for k, v in query.items())]
        return Cursor(items)


class Cursor:
    def __init__(self, items):
        self.items = list(items)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self.items:
            raise StopAsyncIteration
        return self.items.pop(0)


def service(users, transactions, bank):
    db = SimpleNamespace(users=users, transactions=transactions, bank=bank,
                         muted_users=Collection())
    svc = ModerationService.__new__(ModerationService)
    svc.mongo_client = SimpleNamespace(database=db)
    svc.db, svc.users, svc.transactions, svc.bank = db, users, transactions, bank
    svc.ledger = BankLedger(svc.mongo_client)
    svc.ledger.bank = bank
    svc.ledger.emission = SimpleNamespace(
        ensure_state=AsyncMock(return_value={'_id': 'single', 'coins': 0}))
    return svc


def confiscation(_id, user_id, amount):
    return {'_id': _id, 'user_id': user_id, 'tx_type': 'ban_confiscation',
            'coins_change': -float(amount),
            'created_at': datetime.now(timezone.utc)}


@pytest.mark.asyncio
async def test_unsubscribed_player_gets_ban_lifted_and_coins_back():
    users = Users([
        {'_id': 1, 'id': 1, 'coins': 0.0, 'is_banned': True, 'ban_reason': AUTO_BAN_REASON},
        {'_id': 3, 'id': 3, 'coins': 120.0, 'is_banned': True, 'ban_reason': 'Спам'},
    ])
    transactions = Transactions([confiscation('t1', 1, 1000.0),
                                 confiscation('t3', 3, 50.0)])
    bank = Collection([{'_id': 'single', 'coins': 50_000.0}])
    svc = service(users, transactions, bank)

    result = await svc.restore_channel_unsubscribe_bans()

    assert result['restored'] == 1 and result['coins_returned'] == 1000.0
    player = users.docs[1]
    assert player['is_banned'] is False and player['ban_reason'] is None
    assert player['coins'] == 1000.0
    assert bank.docs['single']['coins'] == 49_000.0, 'возврат должен уйти из банка'
    # Другой бан не трогаем.
    assert users.docs[3]['is_banned'] is True and users.docs[3]['coins'] == 120.0


@pytest.mark.asyncio
async def test_ban_stays_if_bank_cannot_refund():
    """Если денег в банке нет, не снимаем бан молча — иначе игрок останется без баланса."""
    users = Users([
        {'_id': 2, 'id': 2, 'coins': 0.0, 'is_banned': True, 'ban_reason': AUTO_BAN_REASON},
    ])
    transactions = Transactions([confiscation('t2', 2, 99_999.0)])
    bank = Collection([{'_id': 'single', 'coins': 10.0}])
    svc = service(users, transactions, bank)

    result = await svc.restore_channel_unsubscribe_bans()

    assert result['restored'] == 0 and result['skipped'] == 1
    assert users.docs[2]['is_banned'] is True
    assert bank.docs['single']['coins'] == 10.0, 'неудачный возврат не должен менять банк'
