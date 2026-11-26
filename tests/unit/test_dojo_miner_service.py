"""Серверный трёхчасовой цикл: старт, ожидание, выплата из банка."""
import copy
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.core.container import Container
from src.services import dojo_miner_service as miner
from src.services.dojo_miner_service import DojoMinerService
from src.services.hedgehog_service import GameError
from tests.unit.test_hedgehog_game import Collection as BaseCollection


class Collection(BaseCollection):
    async def find_one(self, query, **kwargs):
        return await super().find_one(query)

    async def update_one(self, query, changes, **kwargs):
        doc = next((d for d in self.docs.values() if self.matches(d, query)), None)
        value = await self.find_one_and_update(query, changes, **kwargs)
        if value is not None and doc is not None:
            for key, item in changes.get('$addToSet', {}).items():
                values = doc.setdefault(key, [])
                if item not in values:
                    values.append(copy.deepcopy(item))
        return SimpleNamespace(matched_count=int(value is not None))

    async def insert_one(self, doc, **kwargs):
        self.docs[doc.get("_id", len(self.docs))] = copy.deepcopy(doc)


@pytest.fixture(autouse=True)
def mock_mongo_transaction(monkeypatch):
    lock = asyncio.Lock()
    async def tx(mongo, callback):
        async with lock:
            return await atomic(mongo, callback)
    async def atomic(mongo, callback):
        collections = [mongo.database.users, mongo.database.dojo_miners, mongo.database.bank, mongo.database.transactions, mongo.database.dojo_ref_rewards]
        snapshots = [copy.deepcopy(c.docs) for c in collections]
        try: return await callback("session")
        except BaseException:
            for collection, saved in zip(collections, snapshots): collection.docs = saved
            raise
    monkeypatch.setattr("src.services.dojo_miner_service.transaction", tx)


class Miners(Collection):
    async def insert_one(self, doc):
        self.docs[doc['_id']] = copy.deepcopy(doc)


def service():
    db = SimpleNamespace(
        dojo_miners=Miners(),
        users=Collection([{'id': 7, 'coins': 500}]),
        bank=Collection([{'_id': 'single', 'coins': 1000}]),
        transactions=Collection(), dojo_ref_rewards=Collection(),
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
    assert miner.BASE_RATE == 75
    assert miner.PICKAXE_STEP == 50
    assert miner.MINING_REWARD == 225
    assert miner.SPEED_BOOST_SECONDS == 60 * 60


@pytest.mark.asyncio
async def test_ready_state_has_balance_and_reward():
    _, dojo, _ = service()
    with patch.object(miner.time, 'time', return_value=1000):
        state = await dojo.state(7)
    assert state['phase'] == 'ready'
    assert state['reward'] == 90
    assert state['next_reward'] == 90
    assert state['balance'] == 500
    assert state['energy_max'] == 100
    assert state['base_rate'] == 75
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
    assert result['mined'] == 90
    assert result['balance'] == 590
    assert result['phase'] == 'ready'
    assert dojo.mongo.database.bank.docs['single']['coins'] == 910
    assert len(dojo.mongo.database.transactions.docs) == 1
    economy.process_game_win.assert_not_awaited()
    with patch.object(miner.time, 'time', return_value=30000):
        with pytest.raises(GameError, match='уже получена'):
            await dojo.collect(7)
        again = await dojo.start(7)
    assert again['phase'] == 'mining'
    economy.process_game_win.assert_not_awaited()


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
    dojo.mongo.database.users.docs[7]['is_banned'] = True
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
    dojo.mongo.database.transactions.insert_one = AsyncMock(side_effect=RuntimeError('log offline'))
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
        assert started['reward'] == 90
        assert await dojo.apply_task_energy(7, 100, 'claim-1') is True
        state = await dojo.state(7)
    assert state['energy_max'] == 100
    assert state['energy'] == 200
    assert state['reward'] == 158  # one extra full-power hour: 90 -> 158 (157.5 rounded)
    assert state['task_energy_pending'] == 0
    with patch.object(miner.time, 'time', return_value=1000):
        assert await dojo.apply_task_energy(7, 100, 'claim-1') is True
        assert (await dojo.state(7))['reward'] == 158


@pytest.mark.asyncio
async def test_speed_boost_is_one_hour_and_once_per_cycle():
    _, dojo, _ = service()
    dojo.users.docs[7]['coins'] = 500
    with patch.object(miner.time, 'time', return_value=1000):
        started = await dojo.start(7)
        assert started['reward'] == 90
        assert await dojo.apply_speed_boost(7, 'charge-boost-1') is True
        boosted = await dojo.state(7)
        assert boosted['reward'] == 128  # +37.5 for one boosted hour
        assert boosted['boost_percent'] == 50
        assert boosted['boost_seconds_left'] == 3600
        assert boosted['boost_purchased'] is True
        assert boosted['current_rate'] == 112.5
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
        assert ready['reward'] == 128
        assert ready['next_reward'] == 128
        started = await dojo.start(7)
    assert started['reward'] == 128
    assert started['boost_seconds_left'] == 3600


@pytest.mark.asyncio
async def test_circle_energy_rapid_replay_cap_and_new_cycle(monkeypatch):
    monkeypatch.setattr(miner, 'CIRCLE_MIN_INTERVAL', 0)
    _, dojo, _ = service()
    with patch.object(miner.time, 'time', return_value=1000):
        await dojo.start(7)
        assert (await dojo.add_circle_energy(7, 1000, 'circle-early'))['added'] == 0
    with patch.object(miner.time, 'time', return_value=4600):
        for i in range(100):
            assert (await dojo.add_circle_energy(7, 1000, f'circle-{i:04}'))['added'] == 1
        assert (await dojo.add_circle_energy(7, 1000, 'circle-0000'))['replayed'] is True
        assert (await dojo.add_circle_energy(7, 1000, 'circle-0100'))['added'] == 0
        state = await dojo.state(7)
        assert state['energy'] == pytest.approx(100)
        assert state['circle_energy_limit'] == 100
        assert state['reward'] == 158
    with patch.object(miner.time, 'time', return_value=4636):
        assert (await dojo.state(7))['energy'] == pytest.approx(99)
        assert (await dojo.add_circle_energy(7, 1000, 'circle-0101'))['added'] == 1
    with patch.object(miner.time, 'time', return_value=11800):
        with pytest.raises(GameError, match='не запущен'):
            await dojo.add_circle_energy(7, 1000, 'circle-finish')
        await dojo.collect(7)
        await dojo.start(7)
        with pytest.raises(GameError, match='Цикл изменился'):
            await dojo.add_circle_energy(7, 1000, 'circle-stale')
        assert (await dojo.state(7))['circle_available'] is False


@pytest.mark.asyncio
async def test_circle_energy_adds_reward_only_for_remaining_cycle_and_interacts_with_tasks(monkeypatch):
    monkeypatch.setattr(miner, 'CIRCLE_MIN_INTERVAL', 0)
    _, dojo, _ = service()
    with patch.object(miner.time, 'time', return_value=1000):
        await dojo.start(7)
    with patch.object(miner.time, 'time', return_value=11764):
        for i in range(10):
            await dojo.add_circle_energy(7, 1000, f'late-{i:04}')
        state = await dojo.state(7)
        assert state['energy'] == pytest.approx(10)
        assert state['reward'] == 91  # just 36 seconds remain
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


@pytest.mark.asyncio
async def test_circle_available_below_cap_before_empty_and_partial_credit_replays():
    _, dojo, _ = service()
    with patch.object(miner.time, 'time', return_value=1000):
        await dojo.start(7)
    for now in (1000,):
        with patch.object(miner.time, 'time', return_value=now):
            state = await dojo.state(7)
            assert state['circle_available'] is False
            assert (await dojo.add_circle_energy(7, 1000, f'above-{now}'))['added'] == 0
    with patch.object(miner.time, 'time', return_value=1018):
        state = await dojo.state(7)
        assert state['circle_energy'] == pytest.approx(99.5)
        assert state['circle_available'] is True
        result = await dojo.add_circle_energy(7, 1000, 'partial-circle')
        assert result['added'] == pytest.approx(0.5)
        assert (await dojo.add_circle_energy(7, 1000, 'partial-circle')) == {
            'added': result['added'], 'replayed': True}
        state = await dojo.state(7)
        assert state['energy'] == pytest.approx(100)
        assert state['circle_available'] is False
        assert (await dojo.add_circle_energy(7, 1000, 'at-cap-again'))['added'] == 0
    with patch.object(miner.time, 'time', return_value=1054):
        assert (await dojo.state(7))['circle_available'] is True
        assert (await dojo.add_circle_energy(7, 1000, 'after-drain'))['added'] == 1


@pytest.mark.asyncio
async def test_circle_limit_uses_permanent_energy_cap_not_task_energy():
    _, dojo, _ = service()
    with patch.object(miner.time, 'time', return_value=1000):
        await dojo.apply_task_energy(7, 100, 'test-task-before-start')
        await dojo.start(7)
    with patch.object(miner.time, 'time', return_value=4600):
        state = await dojo.state(7)
        assert state['circle_energy'] == pytest.approx(100)
        assert state['energy_max'] == 100
        assert state['circle_available'] is False
        assert (await dojo.add_circle_energy(7, 1000, 'with-task-cap'))['added'] == 0
    with patch.object(miner.time, 'time', return_value=4618):
        assert (await dojo.add_circle_energy(7, 1000, 'with-task-partial'))['added'] == pytest.approx(.5)


@pytest.mark.asyncio
async def test_miner_transaction_split_bank_and_rollback():
    _, dojo, _ = service()
    bank = dojo.mongo.database.bank
    bank.docs['single']['coins'] = 10
    bank.docs['main'] = {'_id': 'main', 'balance': 80}
    with patch.object(miner.time, 'time', return_value=1000):
        await dojo.start(7)
    with patch.object(miner.time, 'time', return_value=11800):
        result = await dojo.collect(7)
    assert result['balance'] == 590
    assert bank.docs['single']['coins'] == 0 and bank.docs['main']['balance'] == 0
    assert len(dojo.mongo.database.transactions.docs) == 1


@pytest.mark.asyncio
async def test_miner_partial_bank_debit_is_rolled_back():
    _, dojo, _ = service()
    dojo.mongo.database.bank.docs['single']['coins'] = 10
    with patch.object(miner.time, 'time', return_value=1000):
        await dojo.start(7)
    with patch.object(miner.time, 'time', return_value=11800):
        with pytest.raises(GameError, match='SenseiBank'): await dojo.collect(7)
    assert dojo.mongo.database.bank.docs['single']['coins'] == 10
    assert dojo.mongo.database.users.docs[7]['coins'] == 500
    assert not dojo.miners.docs[7]['collected']
    assert not dojo.mongo.database.transactions.docs


@pytest.mark.asyncio
async def test_miner_two_workers_pay_cycle_only_once():
    mongo, first, _ = service()
    second = DojoMinerService(mongo, first.economy)
    with patch.object(miner.time, 'time', return_value=1000):
        await first.start(7)
    with patch.object(miner.time, 'time', return_value=11800):
        results = await asyncio.gather(first.collect(7), second.collect(7), return_exceptions=True)
    assert sum(isinstance(r, dict) for r in results) == 1
    assert mongo.database.users.docs[7]['coins'] == 590
    assert mongo.database.bank.docs['single']['coins'] == 910
    assert len(mongo.database.transactions.docs) == 1


@pytest.mark.asyncio
async def test_auto_collect_waits_for_funding_and_records_only_success():
    mongo, dojo, _ = service()
    with patch.object(miner.time, 'time', return_value=1000):
        await dojo.start(7)
    bank = mongo.database.bank.docs['single']
    bank['coins'] = 0
    with patch.object(miner.time, 'time', return_value=11800):
        assert await dojo.auto_step(7) == 'waiting'
        waiting = await dojo.state(7)
        assert waiting['auto_waiting'] and not waiting['last_auto_collect_at']
        mongo.database.bank.docs['single']['coins'] = 100
        assert await dojo.auto_step(7) == 'renewed'
        assert await dojo.auto_step(7) == 'mining'
        renewed = await dojo.state(7)
        assert not renewed['auto_waiting'] and renewed['last_auto_collect_at'] == 11800
        assert renewed['phase'] == 'mining' and renewed['balance'] == 590
        assert len(mongo.database.transactions.docs) == 1


@pytest.mark.asyncio
async def test_mining_referral_bonuses_reserved_once_and_owner_claim_only():
    mongo, dojo, _ = service()
    db = mongo.database
    for uid in (7, 8, 9):
        db.users.docs[uid]['referrer_id'] = uid + 1
        db.users.docs[uid + 1] = {'id': uid + 1, 'coins': 0}
    with patch.object(miner.time, 'time', return_value=1000):
        await dojo.start(7)
    with patch.object(miner.time, 'time', return_value=11800):
        db.bank.docs['single']['coins'] = 90
        with pytest.raises(GameError):
            await dojo.collect(7)
        assert not db.dojo_ref_rewards.docs
        db.bank.docs['single']['coins'] = 1000
        await dojo.collect(7, automatic=True)
        with pytest.raises(GameError):
            await dojo.collect(7)
    for owner, units in [(8, 9000), (9, 900), (10, 90)]:
        reward = db.dojo_ref_rewards.docs[f'{owner}:7']
        assert reward['pending'] == reward['lifetime'] == units
        with pytest.raises(GameError):
            await dojo.claim_referral_mining(7, reward['token'])
        assert await dojo.claim_referral_mining(owner, reward['token']) == {'claimed': units / 1000}
        with pytest.raises(GameError):
            await dojo.claim_referral_mining(owner, reward['token'])
        assert db.users.docs[owner]['coins'] == units / 1000
        reward = db.dojo_ref_rewards.docs[f"{owner}:7"]
        assert reward['pending'] == 0 and reward['lifetime'] == units
    assert db.bank.docs['single']['coins'] == pytest.approx(900.01)


@pytest.mark.asyncio
async def test_boost_rolls_back_entitlement_if_cycle_write_fails_and_replays_once():
    _, dojo, _ = service()
    with patch.object(miner.time, 'time', return_value=1000):
        await dojo.start(7)
        with patch.object(dojo.miners, 'find_one_and_update', AsyncMock(return_value=None)):
            with pytest.raises(RuntimeError, match='Boost cycle changed'):
                await dojo.apply_speed_boost(7, 'boost-failure')
        assert 'dojo_boost_until' not in dojo.users.docs[7]
        assert (await dojo.state(7))['reward'] == 90
        assert await dojo.apply_speed_boost(7, 'boost-failure')
        assert await dojo.apply_speed_boost(7, 'boost-failure')
        assert (await dojo.state(7))['reward'] == 128


@pytest.mark.asyncio
async def test_circle_rate_limit_replay_and_two_service_instances(monkeypatch):
    mongo, first, economy = service()
    second = DojoMinerService(mongo, economy)
    with patch.object(miner.time, 'time', return_value=1000):
        await first.start(7)
    with patch.object(miner.time, 'time', return_value=4600):
        results = await asyncio.gather(*(s.add_circle_energy(7, 1000, f'concurrent-{i}')
                                       for i, s in enumerate([first, second])))
        assert sorted(r['added'] for r in results) == [0, 1]
        assert any(r.get('retry_after') == 2 for r in results)
        winner = next(i for i, r in enumerate(results) if r['added'])
        replay = await second.add_circle_energy(7, 1000, f'concurrent-{winner}')
        assert replay == {'added': 1, 'replayed': True}
    with patch.object(miner.time, 'time', return_value=4602):
        assert (await second.add_circle_energy(7, 1000, 'another-circle'))['added'] == 1
    assert len(first.miners.docs[7]['circle_energy_events']) == 2


@pytest.mark.asyncio
async def test_circle_event_limit_preserves_legacy_history_and_replays(monkeypatch):
    monkeypatch.setattr(miner, 'CIRCLE_MAX_EVENTS', 2)
    _, dojo, _ = service()
    with patch.object(miner.time, 'time', return_value=1000):
        await dojo.start(7)
    for at, key in [(4600, 'circle-one'), (4602, 'circle-two')]:
        with patch.object(miner.time, 'time', return_value=at):
            assert (await dojo.add_circle_energy(7, 1000, key))['added'] == 1
    with patch.object(miner.time, 'time', return_value=4610):
        before = copy.deepcopy(dojo.miners.docs[7])
        assert (await dojo.add_circle_energy(7, 1000, 'circle-three'))['limit_reached']
        assert (await dojo.add_circle_energy(7, 1000, 'circle-one'))['replayed']
        assert dojo.miners.docs[7] == before
        assert (await dojo.state(7))['circle_limit_reached']


@pytest.mark.asyncio
async def test_user_locks_are_shared_while_active_and_released_when_idle():
    import gc
    _, dojo, _ = service()
    entered = asyncio.Event()
    release = asyncio.Event()
    async def first():
        async with dojo._user_lock(7):
            entered.set()
            await release.wait()
    task = asyncio.create_task(first())
    await entered.wait()
    active_lock = dojo._user_lock(7)
    assert active_lock.locked()
    assert dojo._user_lock(7) is active_lock
    release.set()
    await task
    del active_lock, task
    gc.collect()
    assert 7 not in dojo._locks
