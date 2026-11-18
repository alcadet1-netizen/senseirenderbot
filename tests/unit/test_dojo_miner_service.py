"""Серверный трёхчасовой цикл: старт, ожидание, выплата из банка."""
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


def test_cycle_constants_are_three_hours_and_small():
    assert miner.CYCLE_SECONDS == 3 * 60 * 60
    assert miner.BASE_RATE == 15
    assert miner.PICKAXE_STEP == 10
    assert miner.MINING_REWARD == 45
    assert miner.SPEED_BOOST_SECONDS == 60 * 60


@pytest.mark.asyncio
async def test_ready_state_has_balance_and_reward():
    _, dojo, _ = service()
    with patch.object(miner.time, 'time', return_value=1000):
        state = await dojo.state(7)
    assert state['phase'] == 'ready'
    assert state['reward'] == 18
    assert state['next_reward'] == 18
    assert state['balance'] == 500
    assert state['energy_max'] == 100
    assert state['base_rate'] == 15
    assert state['progress_percent'] == 0
    assert state['cycle_seconds'] == 10800


@pytest.mark.asyncio
async def test_start_runs_only_one_three_hour_cycle():
    _, dojo, economy = service()
    with patch.object(miner.time, 'time', return_value=1000):
        started = await dojo.start(7)
    assert started['phase'] == 'mining'
    assert started['finish_at'] == 1000 + 10800
    assert started['remaining_ms'] == 10800_000
    with patch.object(miner.time, 'time', return_value=2000):
        with pytest.raises(GameError, match='уже идёт'):
            await dojo.start(7)
        state = await dojo.state(7)
    assert state['phase'] == 'mining' and state['progress'] == pytest.approx(1000 / 10800)
    assert state['energy'] == 72
    assert state['energy_max'] == 100
    economy.process_game_win.assert_not_awaited()


@pytest.mark.asyncio
async def test_cannot_collect_before_three_hours():
    _, dojo, economy = service()
    with patch.object(miner.time, 'time', return_value=1000):
        await dojo.start(7)
    with patch.object(miner.time, 'time', return_value=11799):
        with pytest.raises(GameError, match='не завершён'):
            await dojo.collect(7)
    economy.process_game_win.assert_not_awaited()


@pytest.mark.asyncio
async def test_collect_pays_once_from_bank_and_reopens_cycle():
    _, dojo, economy = service()
    with patch.object(miner.time, 'time', return_value=1000):
        await dojo.start(7)
    with patch.object(miner.time, 'time', return_value=11800):
        result = await dojo.collect(7)
    assert result['mined'] == 18
    assert result['balance'] == 620
    assert result['phase'] == 'ready'
    economy.process_game_win.assert_awaited_once()
    assert economy.process_game_win.await_args.kwargs['coins'] == 18
    assert '3h' in economy.process_game_win.await_args.kwargs['description']
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
    with patch.object(miner.time, 'time', return_value=11801):
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
    with patch.object(miner.time, 'time', return_value=11800):
        with pytest.raises(GameError, match='недоступна'):
            await dojo.collect(7)
    doc = dojo.miners.docs[7]
    assert doc['collected'] is False
    with patch.object(miner.time, 'time', return_value=11800):
        state = await dojo.state(7)
    assert state['phase'] == 'ready_to_collect'


@pytest.mark.asyncio
async def test_bank_exception_rolls_back_so_reward_is_not_lost():
    _, dojo, economy = service()
    economy.process_game_win.side_effect = RuntimeError('bank offline')
    with patch.object(miner.time, 'time', return_value=1000):
        await dojo.start(7)
    with patch.object(miner.time, 'time', return_value=11800):
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
        assert started['reward'] == 18
        assert await dojo.apply_task_energy(7, 100, 'claim-1') is True
        state = await dojo.state(7)
    assert state['energy_max'] == 100
    assert state['energy'] == 200
    assert state['reward'] == 32  # one extra full-power hour: 18 -> 32 (31.5 rounded)
    assert state['task_energy_pending'] == 0
    with patch.object(miner.time, 'time', return_value=1000):
        assert await dojo.apply_task_energy(7, 100, 'claim-1') is True
        assert (await dojo.state(7))['reward'] == 32


@pytest.mark.asyncio
async def test_speed_boost_is_one_hour_and_once_per_cycle():
    _, dojo, _ = service()
    dojo.users.docs[7]['coins'] = 500
    with patch.object(miner.time, 'time', return_value=1000):
        started = await dojo.start(7)
        assert started['reward'] == 18
        assert await dojo.apply_speed_boost(7, 'charge-boost-1') is True
        boosted = await dojo.state(7)
        assert boosted['reward'] == 26  # +7.5 for one boosted hour
        assert boosted['boost_percent'] == 50
        assert boosted['boost_seconds_left'] == 3600
        assert boosted['boost_purchased'] is True
        assert boosted['current_rate'] == 22.5
        # A second purchase in the same cycle is rejected even after the
        # first hour ends; the percentage never stacks.
        assert await dojo.apply_speed_boost(7, 'charge-boost-2') is False
    with patch.object(miner.time, 'time', return_value=1000 + 3601):
        assert (await dojo.state(7))['boost_active'] is False
        assert await dojo.apply_speed_boost(7, 'charge-boost-3') is False
    with patch.object(miner.time, 'time', return_value=1000 + 10800):
        await dojo.collect(7)
        await dojo.start(7)
        assert await dojo.apply_speed_boost(7, 'charge-boost-4') is True


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


@pytest.mark.asyncio
async def test_boost_bought_before_start_is_in_the_ready_reward():
    _, dojo, _ = service()
    with patch.object(miner.time, 'time', return_value=1000):
        assert await dojo.apply_speed_boost(7, 'charge-ready-boost') is True
        ready = await dojo.state(7)
        assert ready['phase'] == 'ready'
        assert ready['boost_active'] is True
        assert ready['reward'] == 26
        assert ready['next_reward'] == 26
        started = await dojo.start(7)
    assert started['reward'] == 26
    assert started['boost_seconds_left'] == 3600


@pytest.mark.asyncio
async def test_circle_energy_rapid_replay_cap_and_new_cycle():
    _, dojo, _ = service()
    with patch.object(miner.time, 'time', return_value=1000):
        await dojo.start(7)
        with pytest.raises(GameError, match='энергия закончилась'):
            await dojo.add_circle_energy(7, 1000, 'circle-early')
    with patch.object(miner.time, 'time', return_value=4600):
        for i in range(50):
            assert (await dojo.add_circle_energy(7, 1000, f'circle-{i:04}'))['added'] == 1
        assert (await dojo.add_circle_energy(7, 1000, 'circle-0000'))['replayed'] is True
        assert (await dojo.add_circle_energy(7, 1000, 'circle-0050'))['added'] == 0
        state = await dojo.state(7)
        assert state['energy'] == pytest.approx(50)
        assert state['circle_energy_limit'] == 50
        assert state['reward'] == 25  # extra 50 energy gives 6.75 coins, rounded once
    with patch.object(miner.time, 'time', return_value=4636):
        assert (await dojo.state(7))['energy'] == pytest.approx(49)
        assert (await dojo.add_circle_energy(7, 1000, 'circle-0051'))['added'] == 1
    with patch.object(miner.time, 'time', return_value=11800):
        with pytest.raises(GameError, match='не запущен'):
            await dojo.add_circle_energy(7, 1000, 'circle-finish')
        await dojo.collect(7)
        await dojo.start(7)
        with pytest.raises(GameError, match='Цикл изменился'):
            await dojo.add_circle_energy(7, 1000, 'circle-stale')
        assert (await dojo.state(7))['circle_available'] is False


@pytest.mark.asyncio
async def test_circle_energy_adds_reward_only_for_remaining_cycle_and_interacts_with_tasks():
    _, dojo, _ = service()
    with patch.object(miner.time, 'time', return_value=1000):
        await dojo.start(7)
    with patch.object(miner.time, 'time', return_value=11764):
        for i in range(10):
            await dojo.add_circle_energy(7, 1000, f'late-{i:04}')
        state = await dojo.state(7)
        assert state['energy'] == pytest.approx(10)
        assert state['reward'] == 18  # just 36 seconds remain
        assert await dojo.apply_task_energy(7, 100, 'late-task')
        doc = dojo.miners.docs[7]
        assert doc['circle_reward'] == 0  # no double counting when the task fills the same time


@pytest.mark.asyncio
async def test_circle_access_rejects_banned_player():
    _, dojo, _ = service()
    with patch.object(miner.time, 'time', return_value=1000):
        await dojo.start(7)
    dojo.users.docs[7]['is_banned'] = True
    with patch.object(miner.time, 'time', return_value=4600):
        with pytest.raises(GameError, match='Профиль'):
            await dojo.add_circle_energy(7, 1000, 'circle-test')
