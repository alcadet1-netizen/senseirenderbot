"""Slot accounting against a rollback-capable transaction fake."""
import copy
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from src.services.slots_service import SlotsService
from tests.unit.test_hedgehog_game import Collection, services


class Transactions(Collection):
    async def insert_one(self, doc, **kwargs):
        self.docs[len(self.docs)] = copy.deepcopy(doc)


@pytest.mark.asyncio
@pytest.mark.parametrize('roll, bank, expected_user, expected_bank', [
    (.5, 1000, 900, 1100),   # loss
    (.1, 1000, 1200, 800),   # cherries pay 3x
    (.1, 50, 1000, 50),      # bank cannot cover prize: no stake lost
])
async def test_slots_conserve_funds_and_preserve_rules(roll, bank, expected_user, expected_bank):
    db, _, _ = services()
    mongo = SimpleNamespace(database=db)
    db.transactions = Transactions()
    db.bank.docs['main']['balance'] = bank
    with patch('src.services.slots_service.random.random', return_value=roll), \
         patch('src.services.slots_service.random.choice', return_value='🍒'):
        result = await SlotsService(mongo).play_slots(7, 100)
    assert db.users.docs[7]['coins'] == expected_user
    assert db.bank.docs['main']['balance'] == expected_bank
    assert result['success'] == (bank != 50)
    assert len(db.transactions.docs) == (0 if bank == 50 else 2 if roll < .33 else 1)


@pytest.mark.asyncio
async def test_failed_win_journal_aborts_all_movements():
    db, _, _ = services()
    mongo = SimpleNamespace(database=db)
    db.transactions = Transactions()
    db.bank.docs['main']['balance'] = 1000
    insert = db.transactions.insert_one
    async def fail_second(doc, **kwargs):
        if doc['tx_type'] == 'slots_win':
            raise RuntimeError('journal unavailable')
        await insert(doc, **kwargs)
    with patch.object(db.transactions, 'insert_one', side_effect=fail_second), \
         patch('src.services.slots_service.random.random', return_value=.1), \
         patch('src.services.slots_service.random.choice', return_value='🍒'):
        result = await SlotsService(mongo).play_slots(7, 100)
    assert result['reason'] == 'unconfirmed'
    assert db.users.docs[7]['coins'] == 1000
    assert db.bank.docs['main']['balance'] == 1000
    assert not db.transactions.docs
