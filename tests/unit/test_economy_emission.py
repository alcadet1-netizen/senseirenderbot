"""Payouts must spend existing bank coins, never recreate an empty bank."""
from types import SimpleNamespace as NS
import copy
import asyncio

import pytest

from src.services.economy_service import EconomyService
from tests.unit.test_emission_service import Collection, Users


class UserCollection(Users):
    async def find_one(self, query, **kwargs):
        return await super().find_one(query)

    async def update_one(self, query, changes, **kwargs):
        return await super().update_one(query, changes)

    async def insert_one(self, document, **kwargs):
        from uuid import uuid4
        document = copy.deepcopy(document)
        key = document.get('_id', document.get('id', uuid4().hex))
        self.docs[key] = document
        return NS(inserted_id=key)


class BankCollection(Collection):
    async def find_one(self, query, **kwargs):
        return await super().find_one(query)
    async def update_one(self, query, changes, **kwargs):
        return await super().update_one(query, changes, **{k: v for k, v in kwargs.items() if k != "session"})


@pytest.fixture(autouse=True)
def fake_transactions(monkeypatch):
    lock = asyncio.Lock()
    async def tx(mongo, callback):
        async with lock:
            cols = (mongo.database.bank, mongo.database.users, mongo.database.transactions, mongo.database.tickets)
            snapshots = [copy.deepcopy(c.docs) for c in cols]
            try: return await callback("snapshot")
            except BaseException:
                for collection, saved in zip(cols, snapshots): collection.docs = saved
                raise
    monkeypatch.setattr("src.services.economy_service.transaction", tx)


def economy(bank_docs, user_coins=1_000):
    db = NS(
        users=UserCollection([{"_id": 7, "id": 7, "coins": user_coins, "xp": 0,
                           "is_banned": False, "messages_count": 0}]),
        bank=BankCollection(bank_docs),
        transactions=UserCollection(),
        tickets=UserCollection(),
    )
    return EconomyService(NS(database=db)), db


@pytest.mark.asyncio
async def test_reading_or_losing_does_not_refill_the_bank():
    economy_service, db = economy([{
        "_id": "single", "coins": 0, "total_emitted": 1_000,
        "emission_cap": 10_000,
    }])
    assert await economy_service._get_bank_balance() == 0
    assert (await db.bank.find_one({"_id": "single"}))["coins"] == 0

    result = await economy_service.process_game_win(7, coins=100)
    assert result["success"] is False
    assert result["reason"] == "insufficient_bank"
    assert (await db.bank.find_one({"_id": "single"}))["coins"] == 0
    assert db.users.docs[7]["coins"] == 1_000


@pytest.mark.asyncio
async def test_message_reward_pays_only_what_the_bank_covers():
    economy_service, db = economy([{
        "_id": "single", "coins": 4, "total_emitted": 1_000,
        "emission_cap": 10_000,
    }])
    result = await economy_service.process_message_reward(
        7, username="u", first_name="U", apply_rewards=True)
    assert result["success"] is True
    assert result["coins_earned"] == 4
    assert db.users.docs[7]["coins"] == 1_004
    assert (await db.bank.find_one({"_id": "single"}))["coins"] == 0


@pytest.mark.asyncio
async def test_starter_kit_uses_the_global_reservation():
    economy_service, db = economy([{
        "_id": "single", "coins": 0, "total_emitted": 9_999_999_999,
        "emission_cap": 10_000_000_000,
    }], user_coins=0)
    db.users.docs.clear()
    result = await economy_service.process_game_win(8, coins=0, xp=0)
    assert result["success"] is True
    user = db.users.docs[8]
    assert user["coins"] == 0  # only 1 coin of headroom, not a full 10k kit
    # A reservation that would cross the ceiling is refused, so the counter
    # remains at its previous value instead of being rounded up.
    assert (await db.bank.find_one({"_id": "single"}))["total_emitted"] == 9_999_999_999


@pytest.mark.asyncio
async def test_game_win_moves_bank_coins_without_emission():
    """Mining and game rewards must never increase the emission counter."""
    economy_service, db = economy([{
        "_id": "single", "coins": 1_000.0, "total_emitted": 1_000.0,
        "emission_cap": 10_000_000_000,
    }])
    result = await economy_service.process_game_win(
        7, coins=125, xp=5, description="Dojo miner test")
    assert result["success"] is True
    assert result["new_coins"] == 1_125.0
    bank = await db.bank.find_one({"_id": "single"})
    assert bank["coins"] == 875.0
    # A bank -> player transfer is not minting: the lifetime counter stays put.
    assert bank["total_emitted"] == 1_000.0
    assert bank["emission_cap"] == 10_000_000_000


@pytest.mark.asyncio
@pytest.mark.parametrize('emitted,expected', [(0, 3000), (9_999_999_999, 0)])
async def test_message_creation_exposes_actual_starter_only_once(emitted, expected):
    economy_service, db = economy([{
        '_id': 'single', 'coins': 0, 'total_emitted': emitted, 'burned': 0,
        'emission_cap': 10_000_000_000,
    }], user_coins=0)
    db.users.docs.clear()
    first = await economy_service.process_message_reward(8, first_name='New', apply_rewards=False)
    assert first['success'] is True and first['starter_coins'] == expected
    assert db.users.docs[8]['coins'] == expected
    second = await economy_service.process_message_reward(8, first_name='New', apply_rewards=False)
    assert second['success'] is True and second['starter_coins'] is None
    assert db.users.docs[8]['coins'] == expected


@pytest.mark.asyncio
async def test_game_payout_journal_failure_rolls_back_bank_and_player():
    svc, db = economy([{'_id': 'single', 'coins': 70, 'total_emitted': 1000},
                       {'_id': 'main', 'balance': 80}])
    async def fail(*args, **kwargs):
        raise RuntimeError('receipt unavailable')
    db.transactions.insert_one = fail
    with pytest.raises(RuntimeError, match='receipt unavailable'):
        await svc.process_game_win(7, coins=100, xp=5)
    assert db.bank.docs['single']['coins'] == 70
    assert db.bank.docs['main']['balance'] == 80
    assert db.users.docs[7]['coins'] == 1000 and db.users.docs[7]['xp'] == 0


@pytest.mark.asyncio
async def test_game_payout_funds_from_both_bank_accounts():
    svc, db = economy([{'_id': 'single', 'coins': 70, 'total_emitted': 1000},
                       {'_id': 'main', 'balance': 80}])
    result = await svc.process_game_win(7, coins=100, xp=5)
    assert result['new_coins'] == 1100 and result['new_xp'] == 5
    assert db.bank.docs['single']['coins'] == 0 and db.bank.docs['main']['balance'] == 50
    assert len(db.transactions.docs) == 1


@pytest.mark.asyncio
async def test_simultaneous_game_payouts_do_not_overspend_bank():
    svc, db = economy([{'_id': 'single', 'coins': 100, 'total_emitted': 1000}])
    db.users.docs[8] = {'_id': 8, 'id': 8, 'coins': 0, 'xp': 0, 'is_banned': False}
    other = EconomyService(NS(database=db))
    results = await asyncio.gather(svc.process_game_win(7, coins=80),
                                   other.process_game_win(8, coins=80))
    assert sum(result['success'] for result in results) == 1
    assert db.bank.docs['single']['coins'] == 20
    assert db.users.docs[7]['coins'] + db.users.docs[8]['coins'] == 1080


@pytest.mark.asyncio
@pytest.mark.parametrize('entrypoint', ['user', 'daily', 'message', 'game'])
@pytest.mark.parametrize('duplicate', [False, True])
async def test_starter_reservation_only_released_on_definite_duplicate(entrypoint, duplicate):
    from unittest.mock import AsyncMock
    from pymongo.errors import DuplicateKeyError
    from src.services.user_service import UserService
    from src.services.daily_service import DailyService

    svc, db = economy([{'_id': 'single', 'coins': 0, 'total_emitted': 100, 'burned': 0}])
    db.users.docs.clear()
    db.daily_claims = UserCollection()
    db.user_achievements = UserCollection()
    db.users.insert_one = AsyncMock(side_effect=DuplicateKeyError('duplicate') if duplicate else TimeoutError('unknown outcome'))
    mongo = NS(database=db)
    if entrypoint == 'user':
        svc = UserService(mongo)
        run = lambda: svc.get_or_create(8)
    elif entrypoint == 'daily':
        svc = DailyService(mongo)
        run = lambda: svc.claim_daily(8)
    elif entrypoint == 'message':
        run = lambda: svc.process_message_reward(8, apply_rewards=False)
    else:
        run = lambda: svc.process_game_win(8, coins=0, xp=0)
    svc.emission.reserve_starter = AsyncMock(return_value=3000)
    svc.emission.release = AsyncMock()
    with pytest.raises(DuplicateKeyError if duplicate else TimeoutError):
        await run()
    if duplicate:
        svc.emission.release.assert_awaited_once_with(3000, 'starter:8')
    else:
        svc.emission.release.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('source', ['admin', 'zov'])
async def test_bank_transfer_uses_both_accounts_and_does_not_change_emission(source):
    svc, db = economy([{'_id': 'single', 'coins': 3, 'total_emitted': 100, 'burned': 5},
                       {'_id': 'main', 'balance': 7}])
    if source == 'admin':
        result = await svc.admin_add_coins(7, 8, 42)
        assert result['success'] and result['new_balance'] == 1008
        assert list(db.transactions.docs.values())[0]['tx_type'] == 'admin_grant'
    else:
        assert await svc.distribute_zov_reward(7, 8)
        assert not db.transactions.docs
    assert db.bank.docs['single']['coins'] == 0
    assert db.bank.docs['main']['balance'] == 2
    assert db.bank.docs['single']['total_emitted'] == 100
    assert db.bank.docs['single']['burned'] == 5
    assert db.users.docs[7]['coins'] == 1008


@pytest.mark.asyncio
@pytest.mark.parametrize('source', ['admin', 'zov'])
async def test_bank_transfer_missing_user_and_insufficient_bank_do_not_debit(source):
    svc, db = economy([{'_id': 'single', 'coins': 3, 'total_emitted': 100}])
    call = (lambda uid, amount: svc.admin_add_coins(uid, amount, 42)) if source == 'admin' else svc.distribute_zov_reward
    for uid, amount in ((999, 2), (7, 4)):
        result = await call(uid, amount)
        assert (result['success'] if source == 'admin' else result) is False
    assert db.bank.docs['single']['coins'] == 3
    assert db.users.docs[7]['coins'] == 1000
    assert not db.transactions.docs


@pytest.mark.asyncio
@pytest.mark.parametrize('amount', [float('nan'), float('inf'), -1, 0])
async def test_admin_rejects_nonfinite_or_nonpositive_amounts(amount):
    svc, db = economy([{'_id': 'single', 'coins': 10, 'total_emitted': 100}])
    assert not (await svc.admin_add_coins(7, amount, 42))['success']
    assert db.bank.docs['single']['coins'] == 10 and db.users.docs[7]['coins'] == 1000


@pytest.mark.asyncio
async def test_admin_journal_failure_rolls_back_transfer():
    svc, db = economy([{'_id': 'single', 'coins': 3, 'total_emitted': 100},
                       {'_id': 'main', 'balance': 7}])
    async def fail(*args, **kwargs):
        raise RuntimeError('journal down')
    db.transactions.insert_one = fail
    with pytest.raises(RuntimeError, match='journal down'):
        await svc.admin_add_coins(7, 8, 42)
    assert db.bank.docs['single']['coins'] == 3
    assert db.bank.docs['main']['balance'] == 7
    assert db.users.docs[7]['coins'] == 1000


@pytest.mark.asyncio
async def test_concurrent_admin_and_zov_cannot_overspend_bank():
    svc, db = economy([{'_id': 'single', 'coins': 10, 'total_emitted': 100}])
    other = EconomyService(NS(database=db))
    admin, zov = await asyncio.gather(svc.admin_add_coins(7, 8, 42), other.distribute_zov_reward(7, 8))
    assert int(admin['success']) + int(zov) == 1
    assert db.bank.docs['single']['coins'] == 2
    assert db.users.docs[7]['coins'] == 1008


@pytest.mark.asyncio
async def test_fractional_transfer_across_accounts_does_not_reject_rounding():
    svc, db = economy([{'_id': 'single', 'coins': 0.1, 'total_emitted': 100},
                       {'_id': 'main', 'balance': 0.2}], user_coins=0)
    assert (await svc.admin_add_coins(7, 0.3, 42))['success']
    assert db.bank.docs['single']['coins'] == 0
    assert db.bank.docs['main']['balance'] == 0
    assert db.users.docs[7]['coins'] == 0.3


@pytest.mark.asyncio
async def test_message_reward_journal_failure_rolls_back_all_changes():
    svc, db = economy([{'_id': 'single', 'coins': 4, 'total_emitted': 1000},
                       {'_id': 'main', 'balance': 10}], user_coins=100)
    before = copy.deepcopy(db.users.docs[7])
    async def fail(*args, **kwargs):
        raise RuntimeError('journal unavailable')
    db.transactions.insert_one = fail
    with pytest.raises(RuntimeError, match='journal unavailable'):
        await svc.process_message_reward(7)
    assert db.users.docs[7] == before
    assert db.bank.docs['single']['coins'] == 4
    assert db.bank.docs['main']['balance'] == 10
    assert not db.transactions.docs and not db.tickets.docs


@pytest.mark.asyncio
async def test_message_ticket_failure_rolls_back_reward_and_count():
    svc, db = economy([{'_id': 'single', 'coins': 100, 'total_emitted': 1000}], user_coins=100)
    db.users.docs[7]['messages_count'] = 299
    before = copy.deepcopy(db.users.docs[7])
    async def fail(*args, **kwargs):
        raise RuntimeError('tickets unavailable')
    db.tickets.insert_one = fail
    with pytest.raises(RuntimeError, match='tickets unavailable'):
        await svc.process_message_reward(7)
    assert db.users.docs[7] == before
    assert db.bank.docs['single']['coins'] == 100
    assert not db.transactions.docs and not db.tickets.docs


@pytest.mark.asyncio
async def test_message_reward_race_never_overdraws_bank_and_records_actual_payout():
    svc, db = economy([{'_id': 'single', 'coins': 10, 'total_emitted': 1000}], user_coins=100)
    db.users.docs[8] = {'_id': 8, 'id': 8, 'coins': 0, 'xp': 0, 'messages_count': 0, 'is_banned': False}
    other = EconomyService(NS(database=db))
    a, b = await asyncio.gather(svc.process_message_reward(7), other.process_message_reward(8))
    assert a['success'] and b['success']
    assert a['coins_earned'] + b['coins_earned'] == 10
    assert db.bank.docs['single']['coins'] == 0
    assert db.users.docs[7]['coins'] + db.users.docs[8]['coins'] == 110
    assert sum(tx['coins_change'] for tx in db.transactions.docs.values()) == 10
