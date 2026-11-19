"""Conservation, replay and failure checks for the trade game."""
import copy
from types import SimpleNamespace as NS
from unittest.mock import patch

import pytest

from src.services.trade_service import TradeService
from tests.unit.test_hedgehog_game import Collection, services


class Transactions(Collection):
    async def insert_one(self, doc, **kwargs):
        self.docs[doc.get('_id', len(self.docs))] = copy.deepcopy(doc)


def setup(bank=1000):
    db, _, _ = services()
    db.transactions = Transactions()
    db.bank.docs['main']['balance'] = bank
    return db, TradeService(NS(database=db))


@pytest.mark.asyncio
@pytest.mark.parametrize('win,bank,success,coins,balance', [
    (False, 1000, True, 900, 1100),
    (True, 1000, True, 1090, 910),
    (True, 50, False, 1000, 50),
])
async def test_trade_funding_and_existing_rules(win, bank, success, coins, balance):
    db, trade = setup(bank)
    with patch('src.services.trade_service.settings.trade_win_chance', 0.5), \
         patch('src.services.trade_service.random.random', return_value=0.1 if win else 0.9):
        result = await trade.play_game(7, 100)
    assert result['success'] is success
    assert db.users.docs[7]['coins'] == coins and db.bank.docs['main']['balance'] == balance
    if success:
        assert result['fee'] == 5 and result['payout'] == (190 if win else 0)
        assert result['profit'] == (90 if win else -100)
    else:
        assert not db.transactions.docs


@pytest.mark.asyncio
async def test_trade_replay_and_request_conflict():
    db, trade = setup()
    with patch('src.services.trade_service.settings.trade_win_chance', 0.5), \
         patch('src.services.trade_service.random.random', return_value=.1):
        first = await trade.play_game(7, 100, request_id='chat:42')
        repeat = await trade.play_game(7, 100, request_id='chat:42')
        conflict = await trade.play_game(7, 200, request_id='chat:42')
    assert first == repeat and first['success']
    assert not conflict['success'] and 'использован' in conflict['error']
    assert db.users.docs[7]['coins'] == 1090
    assert db.bank.docs['main']['balance'] == 910
    assert len(db.transactions.docs) == 2


@pytest.mark.asyncio
async def test_trade_journal_failure_rolls_back_and_does_not_guess_outcome():
    db, trade = setup()
    insert = db.transactions.insert_one
    async def fail_win(doc, **kwargs):
        if doc['tx_type'] == 'game_win': raise RuntimeError('journal unavailable')
        await insert(doc, **kwargs)
    with patch('src.services.trade_service.settings.trade_win_chance', 0.5), \
         patch('src.services.trade_service.random.random', return_value=.1), \
         patch.object(db.transactions, 'insert_one', side_effect=fail_win):
        result = await trade.play_game(7, 100, request_id='chat:42')
    assert not result['success'] and 'не подтверждён' in result['error']
    assert db.users.docs[7]['coins'] == 1000 and db.bank.docs['main']['balance'] == 1000
    assert not db.transactions.docs
