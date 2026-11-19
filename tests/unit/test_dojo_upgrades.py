"""Dojo upgrades: Stars receipts, permanent levels and automatic cycles."""
import copy
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.services import dojo_miner_service as miner
from src.services.dojo_miner_service import DojoMinerService
from src.services.dojo_upgrade_service import (
    AUTOCOLLECT_STARS,
    BOOST_STARS,
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


def test_energy_curve_matches_the_three_hour_cycle():
    assert miner.estimate_amount(miner.BASE_RATE, 0) == 5
    assert miner.estimate_amount(miner.BASE_RATE, 100) == 18
    assert miner.estimate_amount(miner.BASE_RATE, 800) == 45
    assert miner.estimate_amount(miner.BASE_RATE + 10, 100) == 30


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
    assert data['energy_refill_stars'] == 5
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
async def test_empty_energy_can_be_refilled_for_five_stars():
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
        assert state['energy_refill_stars'] == 5
        order = await service.prepare(7, 'refill')
        assert order['stars'] == 5
        await service.checkout(order['payload'], 7, 'XTR', 5)
        receipt = await service.receive(
            7, payment(order['payload'], 'charge-refill', 5))
        assert receipt['state'] == 'fulfilled'
        state = await dojo.state(7)
        assert state['energy'] == 100
        assert state['energy_refill_available'] is False
        # One full-power hour replaces an hour that would have run at 10%.
        assert state['reward'] == 32
        assert (await service.receive(
            7, payment(order['payload'], 'charge-refill', 5)))['state'] == 'fulfilled'
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
    assert state["reward"] == 135 and state["next_reward"] == 135
    assert started['energy_start'] == 800 and started["reward"] == 135
    with patch.object(miner.time, 'time', return_value=1000 + 2 * 3600):
        mid = await dojo.state(7)
    assert mid['energy'] == 600 and mid['current_rate'] == 45
    with patch.object(miner.time, 'time', return_value=1000 + 3 * 3600):
        done = await dojo.state(7)
    assert done['phase'] == 'ready_to_collect'
    assert done['progress_percent'] == 100 and done['energy'] == 500


@pytest.mark.asyncio
async def test_task_energy_extends_one_budget_without_raising_the_cap():
    db = SimpleNamespace(
        users=Users([{'id': 7, 'coins': 0}]),
        dojo_miners=Miners([{
            '_id': 7,
            'collected': True,
            'task_energy_pending': [{'key': '7:senseidurova', 'amount': 100}],
            'version': 1,
        }]),
    )
    dojo = DojoMinerService(SimpleNamespace(database=db),
                            SimpleNamespace(process_game_win=AsyncMock()))
    with patch.object(miner.time, 'time', return_value=1000):
        state = await dojo.state(7)
        started = await dojo.start(7)
    assert state['energy_max'] == 100
    assert state['energy'] == 200
    assert state['reward'] == 32
    assert started['energy_max'] == 100
    assert started['energy_start'] == 200
    assert started['reward'] == 32
    # The one-time charge is spent by this cycle, not folded into the cap.
    consumed = await dojo.state(7)
    assert consumed['task_energy_pending'] == 0
    assert consumed['energy_max'] == 100


@pytest.mark.asyncio
async def test_speed_boost_costs_one_star_and_is_applied_once_per_charge():
    users = Users([{'id': 7, 'coins': 0}])
    db = SimpleNamespace(
        users=users, dojo_orders=Users(), dojo_payments=Users(),
    )
    miner_service = SimpleNamespace(apply_speed_boost=AsyncMock(return_value=True))
    service = DojoUpgradeService(SimpleNamespace(
        mongo_client=SimpleNamespace(database=db),
        dojo_miner_service=miner_service,
    ))
    order = await service.prepare(7, 'boost')
    assert order['kind'] == 'boost' and order['stars'] == BOOST_STARS == 1
    await service.checkout(order['payload'], 7, 'XTR', 1)
    assert await service._apply(7, 'boost', 'charge-speed') is True
    miner_service.apply_speed_boost.assert_awaited_once_with(7, 'charge-speed')
    snapshot = await service.snapshot(7)
    assert snapshot['boost_stars'] == 1
    assert snapshot['boost_percent'] == 50
    assert snapshot['boost_hours'] == 1
    assert snapshot['boost_once_per_cycle'] is True


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
    async def collect(user_id):
        dojo.miners.docs[user_id]['collected'] = True
    with patch.object(dojo, 'collect', side_effect=collect) as claim, \
         patch.object(miner.time, 'time', return_value=1000 + 10800):
        assert await dojo.auto_tick() == 1
    claim.assert_awaited_once_with(7)
    second = dojo.miners.docs[7]
    assert second['started_at'] == 1000 + 10800
    assert second['finish_at'] == 1000 + 2 * 10800
    assert second['collected'] is False


@pytest.mark.asyncio
async def test_bank_summary_uses_the_cached_admin_snapshot():
    stats = StatsService(SimpleNamespace(database=SimpleNamespace(
        users=SimpleNamespace(), bank=SimpleNamespace(),
        transactions=SimpleNamespace(), tickets=SimpleNamespace())))
    stats.get_admin_stats = AsyncMock(return_value={
        'users': {'total': 3, 'holders': 2}, 'circulation': 450,
        'bank': {'balance': 1000, 'total_supply': 1450,
                 'initial_coins': 1_000_000_000.0},
    })
    data = await stats.get_bank_summary()
    assert data['bank_balance'] == 1000
    assert data['single_balance'] == 1000
    assert data['legacy_balance'] == 0
    assert data['circulation'] == 450
    assert data['total_supply'] == 1450
    assert data['total_emitted'] is None
    assert data['emission_cap'] == 10_000_000_000.0
    assert data['emission_remaining'] is None
    assert data['initial_coins'] == 1_000_000_000.0
    assert data['users'] == 3
    assert data['holders'] == 2
    stats.get_admin_stats.assert_awaited_once()


@pytest.mark.asyncio
async def test_bank_snapshot_does_not_hide_supply_over_cap():
    stats = StatsService(SimpleNamespace(database=SimpleNamespace(
        users=SimpleNamespace(), bank=SimpleNamespace(),
        transactions=SimpleNamespace(), tickets=SimpleNamespace())))
    stats.get_admin_stats = AsyncMock(return_value={
        'users': {'total': 3},
        'circulation': 600,
        'bank': {
            'balance': 800,
            'total_supply': 1_400,
            'total_emitted': 1_400,
            'emission_cap': 1_000,
            'burned': 25,
            'confiscated': 75,
        },
    })
    data = await stats.get_bank_summary()
    assert data['bank_balance'] == 800
    assert data['circulation'] == 600
    assert data['total_supply'] == 1_400
    assert data['total_emitted'] == 1_400
    assert data['supply_over_cap'] is True
    assert data['burned'] == 25 and data['confiscated'] == 75


@pytest.mark.asyncio
async def test_boost_purchase_is_refused_once_per_cycle():
    users = Users([{'id': 7, 'coins': 0}])
    db = SimpleNamespace(users=users, dojo_orders=Users(), dojo_payments=Users())
    miner_service = SimpleNamespace(
        boost_cycle_status=AsyncMock(return_value={
            'cycle_key': 'c:10800000', 'purchased': True, 'active_cycle': True,
        }),
        state=AsyncMock(),
    )
    service = DojoUpgradeService(SimpleNamespace(
        mongo_client=SimpleNamespace(database=db),
        dojo_miner_service=miner_service,
    ))
    with pytest.raises(GameError, match='уже куплена'):
        await service.prepare(7, 'boost')
    snapshot = await service.snapshot(7)
    assert snapshot['boost_purchased'] is True
    assert snapshot['boost_available'] is False
    assert snapshot['boost_once_per_cycle'] is True


@pytest.mark.asyncio
async def test_previously_approved_refill_payment_survives_price_change():
    users, service = upgrade_service()
    service.container.dojo_miner_service = SimpleNamespace(apply_energy_refill=AsyncMock(return_value=True))
    payload = 'dojobuy:v1:7:refill:10:' + 'a' * 24
    service.orders.docs[payload] = {'_id': payload, 'user_id': 7, 'kind': 'refill', 'stars': 10, 'state': 'checkout'}
    result = await service.receive(7, payment(payload, 'legacy-refill', 10))
    assert result['state'] == 'fulfilled'
    service.container.dojo_miner_service.apply_energy_refill.assert_awaited_once_with(7, 'legacy-refill')


@pytest.mark.asyncio
async def test_bank_stats_use_recorded_burn_for_lifetime_headroom():
    class Cursor:
        def __init__(self, rows): self.rows = rows
        async def to_list(self, length=None): return self.rows

    users = SimpleNamespace(aggregate=lambda *a, **kw: Cursor([{'coins': 25, 'count': 1, 'holders': 1}]))
    bank = SimpleNamespace(find_one=AsyncMock(side_effect=[
        {'_id': 'single', 'coins': 75, 'total_emitted': 100, 'burned': 20, 'emission_cap': 1000}, None]))
    db = SimpleNamespace(users=users, bank=bank,
        transactions=SimpleNamespace(aggregate=lambda *a, **kw: Cursor([])),
        tickets=SimpleNamespace(count_documents=AsyncMock(return_value=0)))
    svc = StatsService(SimpleNamespace(database=db))
    stats = await svc._read_admin_stats(None)
    assert stats['bank']['lifetime_issued_estimate'] == 120
    assert stats['bank']['emission_remaining'] == 880
    assert stats['bank']['burned'] == 20
    svc.get_admin_stats = AsyncMock(return_value=stats)
    summary = await svc.get_bank_summary()
    assert summary['lifetime_issued_estimate'] == 120
    assert summary['emission_remaining'] == 880
