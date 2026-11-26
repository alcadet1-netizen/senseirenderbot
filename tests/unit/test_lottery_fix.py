from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest

from src.services.lottery_service import LotteryService


class Cursor:
    def __init__(self, docs):
        self.docs = docs
    def sort(self, spec):
        assert spec == [('user_id', 1), ('_id', 1)]
        self.docs.sort(key=lambda doc: (doc['user_id'], doc['_id']))
        return self
    def batch_size(self, size):
        assert size == 200
        return self
    async def close(self):
        pass
    def __aiter__(self):
        async def iterator():
            for doc in self.docs:
                yield doc
        return iterator()


def member(uid, status='member', is_member=True, is_bot=False):
    return NS(status=status, is_member=is_member,
              user=NS(id=uid, is_bot=is_bot, first_name=f'User{uid}', last_name=None, username=None))


def setup(monkeypatch, tickets, members):
    active = [t.copy() for t in tickets if not t.get('burned') and not t.get('is_burned')
              and isinstance(t.get('code'), str)]
    collection = NS(find=lambda query, projection: Cursor(active),
                    update_one=AsyncMock(return_value=NS(matched_count=1)))
    mongo = NS(database=NS(tickets=collection, users=NS()))
    async def lookup(chat_id, uid):
        assert chat_id == -100
        result = members[uid]
        if isinstance(result, Exception):
            raise result
        return result
    bot = NS(get_chat_member=AsyncMock(side_effect=lookup))
    async def transaction(_mongo, callback):
        return await callback('session')
    monkeypatch.setattr('src.services.referral_economy.transaction', transaction)
    return LotteryService(mongo), collection, bot


@pytest.mark.asyncio
async def test_lottery_only_chat_members_and_active_tickets(monkeypatch):
    tickets = [
        {'_id': 1, 'user_id': 1, 'code': 'one', 'burned': False},
        {'_id': 2, 'user_id': 1, 'code': 'two'},  # historical missing flag
        {'_id': 3, 'user_id': 2, 'code': 'left'},
        {'_id': 4, 'user_id': 3, 'code': 'restricted'},
        {'_id': 5, 'user_id': 4, 'code': 'present'},
        {'_id': 6, 'user_id': 4, 'code': 'already', 'is_burned': True},
        {'_id': 7, 'user_id': 5, 'code': 'bot'},
    ]
    svc, collection, bot = setup(monkeypatch, tickets, {
        1: member(1), 2: member(2, 'left'), 3: member(3, 'restricted', False),
        4: member(4, 'restricted', True), 5: member(5, is_bot=True)})
    winners = await svc.run_lottery(10, chat_id=-100, bot=bot)
    assert {w['ticket_code'] for w in winners} == {'one', 'two', 'present'}
    assert collection.update_one.await_count == 3
    assert [call.args[1] for call in bot.get_chat_member.await_args_list].count(1) == 2
    for call in collection.update_one.await_args_list:
        assert call.kwargs['session'] == 'session'
        assert call.args[1]['$set']['burned'] is True
        assert call.args[1]['$set']['is_burned'] is True


@pytest.mark.asyncio
async def test_membership_error_aborts_before_any_burn(monkeypatch):
    svc, collection, bot = setup(monkeypatch, [
        {'_id': 1, 'user_id': 1, 'code': 'A'}, {'_id': 2, 'user_id': 2, 'code': 'B'}],
        {1: member(1), 2: RuntimeError('Telegram unavailable')})
    with pytest.raises(RuntimeError, match='Telegram unavailable'):
        await svc.run_lottery(1, chat_id=-100, bot=bot)
    collection.update_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_membership_change_aborts_before_any_burn(monkeypatch):
    svc, collection, bot = setup(monkeypatch, [{'_id': 1, 'user_id': 1, 'code': 'A'}], {1: member(1)})
    bot.get_chat_member.side_effect = [member(1), member(1, 'left')]
    with pytest.raises(RuntimeError, match='Membership changed'):
        await svc.run_lottery(1, chat_id=-100, bot=bot)
    collection.update_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_lottery_uses_reservoir_over_tickets(monkeypatch):
    svc, collection, bot = setup(monkeypatch, [
        {'_id': i, 'user_id': 1, 'code': str(i)} for i in range(1, 5)], {1: member(1)})
    # Reservoir keeps the last two tickets when every random position is zero.
    monkeypatch.setattr('src.services.lottery_service.random.randrange', lambda n: 0)
    result = await svc.run_lottery(2, chat_id=-100, bot=bot)
    assert {w['ticket_code'] for w in result} == {'2', '4'}
    assert collection.update_one.await_count == 2


@pytest.mark.asyncio
async def test_lottery_accepts_bson_int64_telegram_ids(monkeypatch):
    from bson.int64 import Int64
    uid = 9876543210
    svc, collection, bot = setup(monkeypatch,
        [{'_id': 1, 'user_id': Int64(uid), 'code': 'A'}], {uid: member(uid)})
    winners = await svc.run_lottery(1, chat_id=-100, bot=bot)
    assert winners[0]['user_id'] == uid
