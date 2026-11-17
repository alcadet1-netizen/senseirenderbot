"""Серверный четырёхчасовой цикл: старт, ожидание, выплата из банка."""
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


def test_cycle_constants_are_four_hours_and_small():
    assert miner.CYCLE_SECONDS == 4 * 60 * 60
    assert miner.BASE_RATE == 15
    assert miner.PICKAXE_STEP == 10
    assert miner.MINING_REWARD == 60


@pytest.mark.asyncio
async def test_ready_state_has_balance_and_reward():
    _, dojo, _ = service()
    with patch.object(miner.time, 'time', return_value=1000):
        state = await dojo.state(7)
    assert state['phase'] == 'ready'
    assert state['reward'] == 20
    assert state['next_reward'] == 20
    assert state['balance'] == 500
    assert state['energy_max'] == 100
    assert state['base_rate'] == 15
    assert state['progress_percent'] == 0
    assert state['cycle_seconds'] == 14400


@pytest.mark.asyncio
async def test_start_runs_only_one_four_hour_cycle():
    _, dojo, economy = service()
    with patch.object(miner.time, 'time', return_value=1000):
        started = await dojo.start(7)
    assert started['phase'] == 'mining'
    assert started['finish_at'] == 1000 + 14400
    assert started['remaining_ms'] == 14400_000
    with patch.object(miner.time, 'time', return_value=2000):
        with pytest.raises(GameError, match='уже идёт'):
            await dojo.start(7)
        state = await dojo.state(7)
    assert state['phase'] == 'mining' and state['progress'] == pytest.approx(1000 / 14400)
    assert state['energy'] == 72
    assert state['energy_max'] == 100
    economy.process_game_win.assert_not_awaited()


@pytest.mark.asyncio
async def test_cannot_collect_before_four_hours():
    _, dojo, economy = service()
    with patch.object(miner.time, 'time', return_value=1000):
        await dojo.start(7)
    with patch.object(miner.time, 'time', return_value=15399):
        with pytest.raises(GameError, match='не завершён'):
            await dojo.collect(7)
    economy.process_game_win.assert_not_awaited()


@pytest.mark.asyncio
async def test_collect_pays_once_from_bank_and_reopens_cycle():
    _, dojo, economy = service()
    with patch.object(miner.time, 'time', return_value=1000):
        await dojo.start(7)
    with patch.object(miner.time, 'time', return_value=15400):
        result = await dojo.collect(7)
    assert result['mined'] == 20
    assert result['balance'] == 620
    assert result['phase'] == 'ready'
    economy.process_game_win.assert_awaited_once()
    assert economy.process_game_win.await_args.kwargs['coins'] == 20
    assert '4h' in economy.process_game_win.await_args.kwargs['description']
    with patch.object(miner.time, 'time', return_value=30000):
        with pytest.raises(GameError, match='уже получена'):
            await dojo.collect(7)
        again = await dojo.start(7)
    assert again['phase'] == 'mining'
    assert economy.process_game_win.await_count == 1


@pytest.mark.asyncio
async def test_finished_uncollected_state_is_ready_to_collect():
    _, dojo, _ = service()
    with patch.object(miner.time, 'time', return_value=1000):
        await dojo.start(7)
    with patch.object(miner.time, 'time', return_value=15401):
        state = await dojo.state(7)
    assert state['phase'] == 'ready_to_collect'
    assert state['progress'] == 1
    assert state['remaining_ms'] == 0


@pytest.mark.asyncio
async def test_bank_failure_rolls_back_so_reward_is_not_lost():
    _, dojo, economy = service()
    economy.process_game_win.return_value = {'success': False, 'reason': 'banned'}
    with patch.object(miner.time, 'time', return_value=1000):
        await dojo.start(7)
    with patch.object(miner.time, 'time', return_value=15400):
        with pytest.raises(GameError, match='недоступна'):
            await dojo.collect(7)
    doc = dojo.miners.docs[7]
    assert doc['collected'] is False
    with patch.object(miner.time, 'time', return_value=15400):
        state = await dojo.state(7)
    assert state['phase'] == 'ready_to_collect'


@pytest.mark.asyncio
async def test_bank_exception_rolls_back_so_reward_is_not_lost():
    _, dojo, economy = service()
    economy.process_game_win.side_effect = RuntimeError('bank offline')
    with patch.object(miner.time, 'time', return_value=1000):
        await dojo.start(7)
    with patch.object(miner.time, 'time', return_value=15400):
        with pytest.raises(GameError, match='не смог выплатить'):
            await dojo.collect(7)
    assert dojo.miners.docs[7]['collected'] is False


@pytest.mark.asyncio
async def test_invalid_user_rejected():
    _, dojo, _ = service()
    for bad in (0, -1, '7', True):
        with pytest.raises(GameError):
            await dojo.state(bad)


@pytest.mark.asyncio
async def test_task_energy_is_spent_once_and_never_raises_the_cap():
    _, dojo, _ = service()
    with patch.object(miner.time, 'time', return_value=1000):
        started = await dojo.start(7)
        assert started['reward'] == 20
        assert await dojo.apply_task_energy(7, 100, 'claim-1') is True
        state = await dojo.state(7)
    assert state['energy_max'] == 100
    assert state['energy'] == 200
    assert state['reward'] == 34  # one extra full-power hour (15 -> 33.5)
    assert state['task_energy_pending'] == 0
    with patch.object(miner.time, 'time', return_value=1000):
        assert await dojo.apply_task_energy(7, 100, 'claim-1') is True
        assert (await dojo.state(7))['reward'] == 34


@pytest.mark.asyncio
async def test_speed_boost_repeats_add_hours_but_never_the_percentage():
    _, dojo, _ = service()
    dojo.users.docs[7]['coins'] = 500
    with patch.object(miner.time, 'time', return_value=1000):
        started = await dojo.start(7)
        assert started['reward'] == 20
        assert await dojo.apply_speed_boost(7, 'charge-boost-1') is True
        boosted = await dojo.state(7)
        assert boosted['reward'] == 35  # +15 for two boosted hours
        assert boosted['boost_percent'] == 50
        assert boosted['boost_seconds_left'] == 7200
        assert boosted['current_rate'] == 22.5
        assert await dojo.apply_speed_boost(7, 'charge-boost-2') is True
        extended = await dojo.state(7)
    assert extended['boost_seconds_left'] == 14400
    assert extended['reward'] == 50  # the remaining two hours, not +100%
    assert extended['boost_percent'] == 50
    assert extended['current_rate'] == 22.5


@pytest.mark.asyncio
async def test_task_energy_waits_for_the_next_cycle_and_is_consumed_once():
    _, dojo, _ = service()
    with patch.object(miner.time, 'time', return_value=1000):
        assert await dojo.apply_task_energy(7, 100, 'claim-ready') is True
        ready = await dojo.state(7)
        assert ready['phase'] == 'ready'
        assert ready['energy'] == 200 and ready['energy_max'] == 100
        assert ready['task_energy_pending'] == 100
        started = await dojo.start(7)
    assert started['energy_start'] == 200 and started['energy_max'] == 100
    assert started['task_energy_pending'] == 0
    with patch.object(miner.time, 'time', return_value=1001):
        after = await dojo.state(7)
    assert after['energy_max'] == 100
    assert after['energy'] < 200
