from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.services.dojo_daily_service import DojoDailyService, day_number, reward_for_day
from src.services.hedgehog_service import GameError


def test_streak_and_rewards():
    today = date(2026, 1, 10)
    assert day_number(today, None, 0) == 1
    assert day_number(today, today - timedelta(days=2), 70) == 1
    assert day_number(today, today - timedelta(days=1), 89) == 90
    assert day_number(today, today - timedelta(days=1), 90) == 1
    assert day_number(today, today, 7) == 7
    assert [reward_for_day(n) for n in (1, 2, 3, 7, 90)] == [100, 200, 600, 600, 600]


def service(monkeypatch, doc=None, bank_ok=True):
    async def tx(mongo, fn):
        return await fn('session')
    monkeypatch.setattr('src.services.dojo_daily_service.transaction', tx)
    users = SimpleNamespace(find_one=AsyncMock(return_value={'id': 42}), update_one=AsyncMock())
    bank = SimpleNamespace(find_one=AsyncMock(return_value={'coins': 1000}), update_one=AsyncMock(return_value=SimpleNamespace(matched_count=int(bank_ok))))
    daily = SimpleNamespace(find_one=AsyncMock(return_value=doc), update_one=AsyncMock())
    receipts = SimpleNamespace(find_one=AsyncMock(return_value=None), insert_one=AsyncMock())
    transactions = SimpleNamespace(insert_one=AsyncMock())
    db = SimpleNamespace(users=users, bank=bank, dojo_daily=daily, dojo_chest_receipts=receipts, transactions=transactions)
    return DojoDailyService(SimpleNamespace(database=db)), db


@pytest.mark.asyncio
async def test_claim_weekly_chests(monkeypatch):
    yesterday = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
    svc, db = service(monkeypatch, {'last_day': yesterday, 'streak': 13})
    result = await svc.claim(42)
    assert result == {'day': 14, 'reward': 600, 'chests_added': 2}
    assert db.dojo_daily.update_one.call_args.args[1]['$inc']['chests'] == 2
    assert db.bank.update_one.call_args.args[1] == {'$inc': {'coins': -600}}


@pytest.mark.asyncio
async def test_failed_bank_does_not_pay(monkeypatch):
    svc, db = service(monkeypatch, bank_ok=False)
    with pytest.raises(GameError):
        await svc.claim(42)
    db.users.update_one.assert_not_awaited()
    db.dojo_daily.update_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_chest_replay_returns_recorded_prize(monkeypatch):
    svc, db = service(monkeypatch)
    db.dojo_chest_receipts.find_one.return_value = {'result': {'kind': 'coin', 'amount': 300}}
    assert await svc.open_chest(42, 'test-id-123') == {'kind': 'coin', 'amount': 300}
    db.bank.update_one.assert_not_awaited()
    db.dojo_daily.update_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_chest_cannot_open_twice_without_bonus(monkeypatch):
    svc, db = service(monkeypatch, {'free_day': datetime.now(timezone.utc).date().isoformat(), 'chests': 0})
    with pytest.raises(GameError):
        await svc.open_chest(42, 'test-id-123')
    db.bank.update_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_virtual_gram_is_credited_without_bank_debit(monkeypatch):
    svc, db = service(monkeypatch)
    monkeypatch.setattr('src.services.dojo_daily_service.secrets.randbelow', lambda n: 0)
    result = await svc.open_chest(42, 'test-id-123')
    assert result == {'kind': 'gram', 'amount': 1}
    assert db.dojo_daily.update_one.call_args.args[1]['$inc']['gram_hundredths'] == 1
    db.bank.update_one.assert_not_awaited()
    db.dojo_chest_receipts.insert_one.assert_awaited_once()


@pytest.mark.asyncio
async def test_chest_all_outcomes_blocked_if_bank_cannot_cover_prizes(monkeypatch):
    svc, db = service(monkeypatch)
    db.bank.find_one.return_value = {'coins': 499}
    monkeypatch.setattr('src.services.dojo_daily_service.secrets.randbelow', lambda n: 0)
    with pytest.raises(GameError):
        await svc.open_chest(42, 'test-id-123')
    db.dojo_daily.update_one.assert_not_awaited()


def grant_service(monkeypatch, users=None, receipt=None):
    from unittest.mock import MagicMock
    async def tx(mongo, fn):
        return await fn('session')
    monkeypatch.setattr('src.services.dojo_daily_service.transaction', tx)
    cursor = SimpleNamespace(to_list=AsyncMock(return_value=users or []))
    cursor.limit = MagicMock(return_value=cursor)
    db = SimpleNamespace(
        users=SimpleNamespace(find=MagicMock(return_value=cursor)),
        dojo_daily=SimpleNamespace(update_one=AsyncMock()),
        dojo_admin_chest_grants=SimpleNamespace(
            find_one=AsyncMock(return_value=receipt), insert_one=AsyncMock()),
    )
    return DojoDailyService(SimpleNamespace(database=db)), db


@pytest.mark.asyncio
async def test_admin_grants_bonus_chests_and_records_audit(monkeypatch):
    svc, db = grant_service(monkeypatch, [{'id': 42, 'username': 'SenseiUser'}])
    result = await svc.grant_admin_chests('senseiuser', 10, 7, '123:456')
    assert result['user_id'] == 42 and result['admin_id'] == 7 and result['amount'] == 10
    db.dojo_daily.update_one.assert_awaited_once_with(
        {'_id': 42}, {'$inc': {'chests': 10}}, upsert=True, session='session')
    db.dojo_admin_chest_grants.insert_one.assert_awaited_once_with(result, session='session')
    assert db.users.find.call_args.args[0]['username']['$options'] == 'i'


@pytest.mark.asyncio
async def test_admin_grant_replay_does_not_credit_twice(monkeypatch):
    receipt = {'_id': '123:456', 'user_id': 42, 'admin_id': 7, 'amount': 10, 'username': 'SenseiUser'}
    svc, db = grant_service(monkeypatch, receipt=receipt)
    assert await svc.grant_admin_chests('senseiuser', 10, 7, '123:456') == receipt
    db.dojo_daily.update_one.assert_not_awaited()
    db.dojo_admin_chest_grants.insert_one.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('users', [[], [{'id': 1, 'username': 'SenseiUser'}, {'id': 2, 'username': 'senseiuser'}]])
async def test_admin_grant_rejects_missing_or_ambiguous_user(monkeypatch, users):
    svc, db = grant_service(monkeypatch, users)
    with pytest.raises(GameError):
        await svc.grant_admin_chests('senseiuser', 10, 7, '123:456')
    db.dojo_daily.update_one.assert_not_awaited()
    db.dojo_admin_chest_grants.insert_one.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('username,amount', [('not valid', 10), ('sensei', 0), ('sensei', 10001), ('sensei', True)])
async def test_admin_grant_rejects_invalid_input(monkeypatch, username, amount):
    svc, db = grant_service(monkeypatch)
    with pytest.raises(GameError):
        await svc.grant_admin_chests(username, amount, 7, '123:456')
    db.users.find.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize('free,starting,expected', [(True, 0, 2), (False, 3, 1)])
async def test_two_chests_are_credited_in_same_receipt(monkeypatch, free, starting, expected):
    today = datetime.now(timezone.utc).date().isoformat()
    svc, db = service(monkeypatch, {'free_day': None if free else today, 'chests': starting})
    monkeypatch.setattr('src.services.dojo_daily_service.secrets.randbelow', lambda n: 10)
    assert await svc.open_chest(42, 'chest-win-id') == {'kind': 'chest', 'amount': 2}
    assert db.dojo_daily.update_one.call_args.args[1]['$inc']['chests'] == expected
    assert db.dojo_chest_receipts.insert_one.call_args.args[0]['result'] == {'kind': 'chest', 'amount': 2}
    db.bank.update_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_admin_grant_rejects_reused_key_with_different_payload(monkeypatch):
    receipt = {'_id': 'web:7:request-id', 'user_id': 42, 'admin_id': 7, 'amount': 10, 'username': 'SenseiUser'}
    svc, db = grant_service(monkeypatch, receipt=receipt)
    with pytest.raises(GameError, match='уже использован'):
        await svc.grant_admin_chests('SenseiUser', 11, 7, 'web:7:request-id')
    db.dojo_daily.update_one.assert_not_awaited()
