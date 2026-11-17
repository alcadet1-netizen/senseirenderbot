"""Dojo upgrades: Stars receipts, permanent levels and automatic cycles."""
import copy
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.services import dojo_miner_service as miner
from src.services.dojo_miner_service import DojoMinerService
from src.services.dojo_upgrade_service import (
    AUTOCOLLECT_STARS,
    ENERGY_STARS,
    PICKAXE_STARS,
    DojoUpgradeService,
)
from src.services.hedgehog_service import GameError
from src.services.stats_service import StatsService
from tests.unit.test_hedgehog_game import Collection


class Cursor:
    def __init__(self, items):
        self.items = list(items)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self.items:
            raise StopAsyncIteration
        return self.items.pop(0)


class Users(Collection):
    """Collection fake with the update operators used by permanent upgrades."""

    def matches(self, doc, query):
        if '$or' in query:
            if not any(self.matches(doc, part) for part in query['$or']):
                return False
        for key, value in query.items():
            if key == '$or':
                continue
            actual = doc.get(key)
            if isinstance(value, dict) and any(k.startswith('$') for k in value):
                if '$ne' in value and actual == value['$ne']:
                    return False
                if '$exists' in value and (key in doc) != value['$exists']:
                    return False
                if '$lt' in value and (actual is None or actual >= value['$lt']):
                    return False
                if '$gte' in value and (actual is None or actual < value['$gte']):
                    return False
            elif actual != value:
                return False
        return True

    async def update_one(self, query, changes, upsert=False, **kwargs):
        found = next((d for d in self.docs.values() if self.matches(d, query)), None)
        if found is None:
            if not upsert:
                return SimpleNamespace(matched_count=0, modified_count=0)
            found = {k: v for k, v in query.items() if not isinstance(v, dict)}
            found.update(copy.deepcopy(changes.get('$setOnInsert', {})))
            self.docs[found.get('_id')] = found
        matched = 1
        found.update(copy.deepcopy(changes.get('$set', {})))
        for key, value in changes.get('$inc', {}).items():
            found[key] = found.get(key, 0) + value
        for key, value in changes.get('$addToSet', {}).items():
            current = found.setdefault(key, [])
            if value not in current:
                current.append(copy.deepcopy(value))
        return SimpleNamespace(matched_count=matched, modified_count=1)

    def find(self, query, projection=None):
        return Cursor(copy.deepcopy(doc) for doc in self.docs.values()
                      if self.matches(doc, query))


class Miners(Collection):
    async def insert_one(self, doc):
        self.docs[doc['_id']] = copy.deepcopy(doc)


def upgrade_service(user=None):
    users = Users([user or {'id': 7, 'coins': 0}])
    db = SimpleNamespace(users=users, dojo_orders=Users(), dojo_payments=Users())
    container = SimpleNamespace(mongo_client=SimpleNamespace(database=db))
    return users, DojoUpgradeService(container)


def test_energy_curve_matches_the_four_hour_cycle():
    assert miner.estimate_amount(miner.BASE_RATE, 0) == 6
    assert miner.estimate_amount(miner.BASE_RATE, 100) == 20
    assert miner.estimate_amount(miner.BASE_RATE, 800) == 60
    assert miner.estimate_amount(miner.BASE_RATE + 10, 100) == 33


def payment(payload, charge, stars):
    return SimpleNamespace(
        invoice_payload=payload,
        currency='XTR',
        total_amount=stars,
        telegram_payment_charge_id=charge,
    )


@pytest.mark.asyncio
async def test_snapshot_defaults_and_prices():
    _, service = upgrade_service()
    data = await service.snapshot(7)
    assert data['pickaxe_level'] == 0 and data['pickaxe_rate'] == 15
    assert data['pickaxe_stars'] == PICKAXE_STARS == 10
    assert data['energy_bonus'] == 0 and data['energy_stars'] == ENERGY_STARS == 50
    assert data['energy_refill_stars'] == 10
    assert data['energy_refill_amount'] == 100
    assert data['auto_collect'] is False and data['auto_stars'] == AUTOCOLLECT_STARS == 1000


@pytest.mark.asyncio
async def test_pickaxe_receipt_applies_once_and_is_idempotent():
    users, service = upgrade_service()
    order = await service.prepare(7, 'pickaxe')
    await service.checkout(order['payload'], 7, 'XTR', 10)
    paid = payment(order['payload'], 'charge-1', 10)
    first = await service.receive(7, paid)
    second = await service.receive(7, paid)
    assert first['state'] == second['state'] == 'fulfilled'
    assert users.docs[7]['dojo_pickaxe_level'] == 1
    assert users.docs[7]['dojo_applied_receipts'] == ['charge-1']
    assert (await service.snapshot(7))['pickaxe_rate'] == 25


@pytest.mark.asyncio
async def test_late_receipt_after_a_limit_is_refunded():
    users, service = upgrade_service({
        'id': 7, 'coins': 0, 'dojo_pickaxe_level': 99})
    first = await service.prepare(7, 'pickaxe')
    second = await service.prepare(7, 'pickaxe')
    assert (await service.receive(
        7, payment(first['payload'], 'charge-a', 10)))['state'] == 'fulfilled'
    receipt = await service.receive(7, payment(second['payload'], 'charge-b', 10))
    assert receipt['state'] == 'refund_required'
    assert users.docs[7]['dojo_pickaxe_level'] == 100
    assert users.docs[7]['dojo_applied_receipts'] == ['charge-a']


@pytest.mark.asyncio
async def test_energy_and_auto_receipts_change_permanent_profile():
    users, service = upgrade_service()
    energy = await service.prepare(7, 'energy')
    auto = await service.prepare(7, 'auto')
    assert (await service.receive(7, payment(energy['payload'], 'charge-2', 50)))['state'] == 'fulfilled'
    assert (await service.receive(7, payment(auto['payload'], 'charge-3', 1000)))['state'] == 'fulfilled'
    data = await service.snapshot(7)
    assert data['energy_purchases'] == 1 and data['energy_bonus'] == 100
    assert data['auto_collect'] is True
    with pytest.raises(GameError, match='уже включён'):
        await service.prepare(7, 'auto')


@pytest.mark.asyncio
async def test_max_pickaxe_and_invalid_payments_are_rejected():
    users, service = upgrade_service({'id': 7, 'coins': 0, 'dojo_pickaxe_level': 100})
    with pytest.raises(GameError, match='100 уровня'):
        await service.prepare(7, 'pickaxe')
    order = await service.prepare(7, 'energy')
    with pytest.raises(GameError):
        await service.checkout(order['payload'], 8, 'XTR', 50)
    with pytest.raises(GameError):
        await service.receive(7, payment(order['payload'], 'charge', 10))
    assert 'dojo_energy_purchases' not in users.docs[7]


@pytest.mark.asyncio
async def test_empty_energy_can_be_refilled_for_ten_stars():
    users = Users([{'id': 7, 'coins': 0}])
    miners = Miners()
    db = SimpleNamespace(
        users=users, dojo_miners=miners,
        dojo_orders=Users(), dojo_payments=Users(),
    )
    dojo = DojoMinerService(
        SimpleNamespace(database=db),
        SimpleNamespace(process_game_win=AsyncMock()),
    )
    service = DojoUpgradeService(SimpleNamespace(
        mongo_client=SimpleNamespace(database=db),
        dojo_miner_service=dojo,
    ))
    with patch.object(miner.time, 'time', return_value=1000):
        await dojo.start(7)
    with patch.object(miner.time, 'time', return_value=1000 + 3600):
        state = await dojo.state(7)
        assert state['energy'] == 0
        assert state['energy_refill_available'] is True
        assert state['energy_refill_stars'] == 10
        order = await service.prepare(7, 'refill')
        assert order['stars'] == 10
        await service.checkout(order['payload'], 7, 'XTR', 10)
        receipt = await service.receive(
            7, payment(order['payload'], 'charge-refill', 10))
        assert receipt['state'] == 'fulfilled'
        state = await dojo.state(7)
        assert state['energy'] == 100
        assert state['energy_refill_available'] is False
        # One full-power hour replaces an hour that would have run at 10%.
        assert state['reward'] == 34
        assert (await service.receive(
            7, payment(order['payload'], 'charge-refill', 10)))['state'] == 'fulfilled'
        # A second paid refill cannot land while the bar is already positive.
        assert await dojo.apply_energy_refill(7, 'charge-refill-2') is False
    assert len(miners.docs[7]['energy_refills']) == 1


@pytest.mark.asyncio
async def test_energy_refill_requires_a_running_empty_cycle():
    users = Users([{'id': 7, 'coins': 0}])
    db = SimpleNamespace(
        users=users, dojo_miners=Miners(),
        dojo_orders=Users(), dojo_payments=Users(),
    )
    dojo = DojoMinerService(
        SimpleNamespace(database=db),
        SimpleNamespace(process_game_win=AsyncMock()),
    )
    service = DojoUpgradeService(SimpleNamespace(
        mongo_client=SimpleNamespace(database=db),
        dojo_miner_service=dojo,
    ))
    with patch.object(miner.time, 'time', return_value=1000):
        with pytest.raises(GameError, match='нулевой энергии'):
            await service.prepare(7, 'refill')
        await dojo.start(7)
    with patch.object(miner.time, 'time', return_value=1100):
        with pytest.raises(GameError, match='нулевой энергии'):
            await service.prepare(7, 'refill')


@pytest.mark.asyncio
async def test_pickaxe_and_energy_budget_drive_the_cycle():
    db = SimpleNamespace(
        users=Users([{'id': 7, 'coins': 500, 'dojo_pickaxe_level': 3,
                      'dojo_energy_purchases': 7}]),
        dojo_miners=Miners(),
    )
    dojo = DojoMinerService(SimpleNamespace(database=db),
                            SimpleNamespace(process_game_win=AsyncMock()))
    with patch.object(miner.time, 'time', return_value=1000):
        state = await dojo.state(7)
        started = await dojo.start(7)
    assert state['base_rate'] == 45 and state['energy_max'] == 800
    assert state["reward"] == 180 and state["next_reward"] == 180
    assert started['energy_start'] == 800 and started["reward"] == 180
    with patch.object(miner.time, 'time', return_value=1000 + 4 * 3600):
        mid = await dojo.state(7)
    assert mid['energy'] == 400 and mid['current_rate'] == 45
    with patch.object(miner.time, 'time', return_value=1000 + 8 * 3600):
        done = await dojo.state(7)
    assert done['phase'] == 'ready_to_collect'
    assert done['progress_percent'] == 100 and done['energy'] == 400


@pytest.mark.asyncio
async def test_task_energy_extends_budget():
    db = SimpleNamespace(
        users=Users([{'id': 7, 'coins': 0}]),
        dojo_miners=Miners(),
    )
    tasks = SimpleNamespace(energy_bonus_total=AsyncMock(return_value=100))
    dojo = DojoMinerService(SimpleNamespace(database=db),
                            SimpleNamespace(process_game_win=AsyncMock()), tasks)
    with patch.object(miner.time, 'time', return_value=1000):
        state = await dojo.state(7)
    assert state['energy_max'] == 200
    assert state['reward'] == 33


@pytest.mark.asyncio
async def test_auto_collect_starts_and_renews_cycles():
    db = SimpleNamespace(
        users=Users([{'id': 7, 'coins': 0, 'dojo_auto_collect': True}]),
        dojo_miners=Miners(),
    )
    economy = SimpleNamespace(process_game_win=AsyncMock(return_value={
        'success': True, 'new_coins': 500}))
    dojo = DojoMinerService(SimpleNamespace(database=db), economy)
    with patch.object(miner.time, 'time', return_value=1000):
        assert await dojo.auto_tick() == 1
    first = dojo.miners.docs[7]
    assert first['started_at'] == 1000 and not first['collected']
    with patch.object(miner.time, 'time', return_value=1000 + 14400):
        assert await dojo.auto_tick() == 1
    economy.process_game_win.assert_awaited_once()
    second = dojo.miners.docs[7]
    assert second['started_at'] == 1000 + 14400
    assert second['finish_at'] == 1000 + 2 * 14400
    assert second['collected'] is False


@pytest.mark.asyncio
async def test_bank_summary_uses_the_cached_admin_snapshot():
    stats = StatsService(SimpleNamespace(database=SimpleNamespace(
        users=SimpleNamespace(), bank=SimpleNamespace(),
        transactions=SimpleNamespace(), tickets=SimpleNamespace())))
    stats.get_admin_stats = AsyncMock(return_value={
        'users': {'total': 3}, 'circulation': 450,
        'bank': {'balance': 1000, 'total_supply': 1450,
                 'initial_coins': 1_000_000_000.0},
    })
    data = await stats.get_bank_summary()
    assert data['bank_balance'] == 1000
    assert data['single_balance'] == 1000
    assert data['legacy_balance'] == 0
    assert data['circulation'] == 450
    assert data['total_supply'] == 1450
    assert data['total_emitted'] == 1450
    assert data['emission_cap'] == 10_000_000_000.0
    assert data['emission_remaining'] == 10_000_000_000.0 - 1450
    assert data['initial_coins'] == 1_000_000_000.0
    assert data['users'] == 3
    stats.get_admin_stats.assert_awaited_once()
