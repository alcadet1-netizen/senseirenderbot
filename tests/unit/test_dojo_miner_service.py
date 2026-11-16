"""Серверный восьмичасовой цикл: пинок, ожидание, выплата из банка."""
import copy
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.core.container import Container
from src.services import dojo_miner_service as miner
from src.services.dojo_miner_service import DojoMinerService
from src.services.hedgehog_service import GameError
from tests.unit.test_hedgehog_game import Collection


class Miners(Collection):
    async def insert_one(self, doc):
        self.docs[doc['_id']] = copy.deepcopy(doc)


def service():
    db = SimpleNamespace(
        dojo_miners=Miners(),
        users=Collection([{'id': 7, 'coins': 500}]),
    )
    economy = SimpleNamespace(process_game_win=AsyncMock(return_value={
        'success': True, 'new_coins': 620}))
    return SimpleNamespace(database=db), DojoMinerService(
        SimpleNamespace(database=db), economy), economy


def test_container_has_lazy_miner_service_slot():
    container = Container(settings=SimpleNamespace(), mongo_client=SimpleNamespace())
    assert container._dojo_miner_service is None


def test_cycle_constants_are_eight_hours_and_small():
    assert miner.CYCLE_SECONDS == 8 * 60 * 60
    assert miner.MINING_REWARD == 120


@pytest.mark.asyncio
async def test_ready_state_has_balance_and_reward():
    _, dojo, _ = service()
    with patch.object(miner.time, 'time', return_value=1000):
        state = await dojo.state(7)
    assert state['phase'] == 'ready'
    assert state['reward'] == 120
    assert state['balance'] == 500
    assert state['cycle_seconds'] == 28800


@pytest.mark.asyncio
async def test_kick_starts_only_one_eight_hour_cycle():
    _, dojo, economy = service()
    with patch.object(miner.time, 'time', return_value=1000):
        started = await dojo.kick(7)
    assert started['phase'] == 'mining'
    assert started['finish_at'] == 1000 + 28800
    assert started['remaining_ms'] == 28800_000
    with patch.object(miner.time, 'time', return_value=2000):
        with pytest.raises(GameError, match='уже летит'):
            await dojo.kick(7)
        state = await dojo.state(7)
    assert state['phase'] == 'mining' and state['progress'] == pytest.approx(1000 / 28800)
    economy.process_game_win.assert_not_awaited()


@pytest.mark.asyncio
async def test_cannot_collect_before_eight_hours():
    _, dojo, economy = service()
    with patch.object(miner.time, 'time', return_value=1000):
        await dojo.kick(7)
    with patch.object(miner.time, 'time', return_value=29799):
        with pytest.raises(GameError, match='не завершён'):
            await dojo.collect(7)
    economy.process_game_win.assert_not_awaited()


@pytest.mark.asyncio
async def test_collect_pays_once_from_bank_and_reopens_kick():
    _, dojo, economy = service()
    with patch.object(miner.time, 'time', return_value=1000):
        await dojo.kick(7)
    with patch.object(miner.time, 'time', return_value=29800):
        result = await dojo.collect(7)
    assert result['mined'] == 120
    assert result['balance'] == 620
    assert result['phase'] == 'ready'
    economy.process_game_win.assert_awaited_once()
    assert economy.process_game_win.await_args.kwargs['coins'] == 120
    assert '8h' in economy.process_game_win.await_args.kwargs['description']
    with patch.object(miner.time, 'time', return_value=30000):
        with pytest.raises(GameError, match='уже получена'):
            await dojo.collect(7)
        again = await dojo.kick(7)
    assert again['phase'] == 'mining'
    assert economy.process_game_win.await_count == 1


@pytest.mark.asyncio
async def test_finished_uncollected_state_is_ready_to_collect():
    _, dojo, _ = service()
    with patch.object(miner.time, 'time', return_value=1000):
        await dojo.kick(7)
    with patch.object(miner.time, 'time', return_value=29801):
        state = await dojo.state(7)
    assert state['phase'] == 'ready_to_collect'
    assert state['progress'] == 1
    assert state['remaining_ms'] == 0


@pytest.mark.asyncio
async def test_bank_failure_rolls_back_so_reward_is_not_lost():
    _, dojo, economy = service()
    economy.process_game_win.return_value = {'success': False, 'reason': 'banned'}
    with patch.object(miner.time, 'time', return_value=1000):
        await dojo.kick(7)
    with patch.object(miner.time, 'time', return_value=29800):
        with pytest.raises(GameError, match='недоступна'):
            await dojo.collect(7)
    doc = dojo.miners.docs[7]
    assert doc['collected'] is False
    with patch.object(miner.time, 'time', return_value=29800):
        state = await dojo.state(7)
    assert state['phase'] == 'ready_to_collect'


@pytest.mark.asyncio
async def test_bank_exception_rolls_back_so_reward_is_not_lost():
    _, dojo, economy = service()
    economy.process_game_win.side_effect = RuntimeError('bank offline')
    with patch.object(miner.time, 'time', return_value=1000):
        await dojo.kick(7)
    with patch.object(miner.time, 'time', return_value=29800):
        with pytest.raises(GameError, match='не смог выплатить'):
            await dojo.collect(7)
    assert dojo.miners.docs[7]['collected'] is False


@pytest.mark.asyncio
async def test_invalid_user_rejected():
    _, dojo, _ = service()
    for bad in (0, -1, '7', True):
        with pytest.raises(GameError):
            await dojo.state(bad)
