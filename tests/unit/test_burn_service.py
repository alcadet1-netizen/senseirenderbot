"""Voluntary burn: user balance and global emission fall together."""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.services.burn_service import BurnService
from src.services.hedgehog_service import GameError
from tests.unit.test_hedgehog_game import Collection


class Tx(Collection):
    async def insert_one(self, doc):
        self.docs[len(self.docs)] = doc


def service(*, bank_coins=1_000_000, emitted=10_000):
    db = SimpleNamespace(
        users=Collection([{'id': 7, 'coins': 5_000}]),
        transactions=Tx(),
        bank=Collection([{
            '_id': 'single',
            'coins': bank_coins,
            'total_emitted': emitted,
            'emission_cap': 10_000_000_000,
        }]),
    )
    return db, BurnService(SimpleNamespace(database=db))


@pytest.mark.asyncio
async def test_burn_decreases_player_balance_and_emission_without_touching_bank():
    db, burner = service()
    result = await burner.burn(7, 1_000)
    assert result['success'] is True
    assert result['amount'] == 1_000
    assert result['balance'] == 4_000
    assert db.users.docs[7]['coins'] == 4_000
    assert db.users.docs[7]['burned_coins'] == 1_000
    assert db.bank.docs['single']['coins'] == 1_000_000
    assert db.bank.docs['single']['total_emitted'] == 9_000
    assert db.bank.docs['single']['burned'] == 1_000
    assert len(db.transactions.docs) == 1
    tx = next(iter(db.transactions.docs.values()))
    assert tx['tx_type'] == 'burn' and tx['coins_change'] == -1_000


@pytest.mark.asyncio
async def test_burn_rejects_more_than_the_player_owns():
    db, burner = service()
    with pytest.raises(GameError, match='Недостаточно'):
        await burner.burn(7, 5_001)
    assert db.users.docs[7]['coins'] == 5_000
    assert db.bank.docs['single']['total_emitted'] == 10_000
    assert not db.transactions.docs


@pytest.mark.asyncio
async def test_failed_emission_update_refunds_the_player():
    db, burner = service()
    burner.emission.burn = AsyncMock(side_effect=RuntimeError('counter offline'))
    with pytest.raises(GameError, match='Не удалось сжечь'):
        await burner.burn(7, 1_000)
    assert db.users.docs[7]['coins'] == 5_000
    assert db.users.docs[7].get('burned_coins', 0) == 0
    assert db.bank.docs['single']['total_emitted'] == 10_000
