"""Duel stakes are player-funded and rollback together."""
import asyncio
import copy
from types import SimpleNamespace as NS
from unittest.mock import patch

import pytest

from src.services.duel_escrow import DuelEscrow
from tests.unit.test_hedgehog_game import Collection, services


class Insertable(Collection):
    async def insert_one(self, doc, **kwargs):
        self.docs[doc.get('_id', len(self.docs))] = copy.deepcopy(doc)


def setup():
    db, _, _ = services()
    db.users.docs[8] = {'id': 8, 'coins': 1000}
    db.transactions = Insertable()
    db.duel_escrows = Insertable()
    return db, DuelEscrow(NS(database=db))


@pytest.mark.asyncio
@pytest.mark.parametrize('winner', [7, 8, None])
async def test_stakes_win_and_refund_are_idempotent(winner):
    db, escrow = setup()
    bank = copy.deepcopy(db.bank.docs)
    assert await escrow.reserve('key', 7, 8, 300, 123)
    assert await escrow.reserve('key', 7, 8, 300, 123)
    assert db.users.docs[7]['coins'] == db.users.docs[8]['coins'] == 700
    await asyncio.gather(*(escrow.settle('key', winner) for _ in range(4)))
    assert db.users.docs[7]['coins'] == (1300 if winner == 7 else 700 if winner == 8 else 1000)
    assert db.users.docs[8]['coins'] == (1300 if winner == 8 else 700 if winner == 7 else 1000)
    assert db.bank.docs == bank
    assert sum(db.users.docs[i]['coins'] for i in (7, 8)) == 2000
    with pytest.raises(RuntimeError):
        await escrow.settle('key', 7 if winner != 7 else None)


@pytest.mark.asyncio
async def test_insufficient_stake_does_not_debit_either_player():
    db, escrow = setup()
    db.users.docs[8]['coins'] = 299
    assert not await escrow.reserve('key', 7, 8, 300, 123)
    assert db.users.docs[7]['coins'] == 1000 and db.users.docs[8]['coins'] == 299
    assert not db.duel_escrows.docs and not db.transactions.docs


@pytest.mark.asyncio
async def test_failed_payout_rolls_back_and_keeps_decision_for_retry():
    db, escrow = setup()
    await escrow.reserve('key', 7, 8, 300, 123)
    async def fail(*args, **kwargs): raise RuntimeError('journal unavailable')
    with patch.object(escrow.transactions, 'insert_one', side_effect=fail):
        with pytest.raises(RuntimeError, match='journal unavailable'):
            await escrow.settle('key', 7)
    assert db.users.docs[7]['coins'] == db.users.docs[8]['coins'] == 700
    assert db.duel_escrows.docs['key']['state'] == 'decided'
    assert db.duel_escrows.docs['key']['winner_id'] == 7
    with pytest.raises(RuntimeError, match='decided differently'):
        await escrow.settle('key', None)
    await escrow.settle('key', 7)
    assert db.users.docs[7]['coins'] == 1300
    assert db.duel_escrows.docs['key']['state'] == 'settled'


@pytest.mark.asyncio
async def test_failed_reservation_journal_rolls_back_both_players():
    db, escrow = setup()
    insert = db.transactions.insert_one
    async def fail_second(doc, **kwargs):
        if doc['user_id'] == 8:
            raise RuntimeError('journal unavailable')
        await insert(doc, **kwargs)
    with patch.object(db.transactions, 'insert_one', side_effect=fail_second):
        with pytest.raises(RuntimeError, match='journal unavailable'):
            await escrow.reserve('bad', 7, 8, 300, 10)
    assert db.users.docs[7]['coins'] == db.users.docs[8]['coins'] == 1000
    assert not db.transactions.docs and not db.duel_escrows.docs


@pytest.mark.asyncio
async def test_live_service_creates_and_pays_player_to_player():
    from unittest.mock import AsyncMock
    from src.services.duel_service import Duel, DuelService

    db, _ = setup()
    mongo = NS(database=db)
    container = NS(mongo_client=mongo, user_service=NS(), economy_service=NS())
    service = DuelService(container)
    service._update_arena = AsyncMock()
    service._archive_duel = AsyncMock()
    duel = await service.create_duel(7, 8, 300, -100, AsyncMock())
    assert isinstance(duel, Duel) and duel.escrow_id
    assert db.users.docs[7]['coins'] == db.users.docs[8]['coins'] == 700
    await service._finish_duel(duel, 8, 'Победа')
    await service._finish_duel(duel, 8, 'Победа')
    assert db.users.docs[7]['coins'] == 700 and db.users.docs[8]['coins'] == 1300
    assert db.duel_escrows.docs[duel.escrow_id]['state'] == 'settled'
    assert len([tx for tx in db.transactions.docs.values() if tx['tx_type'] == 'duel_bet_payout']) == 1
    assert db.bank.docs['main']['balance'] == 100000
    await asyncio.sleep(0)
