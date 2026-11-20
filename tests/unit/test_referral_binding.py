"""Bot and Mini App referral binding must share one race-safe graph rule."""
import asyncio
import copy
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

import pytest

from src.services.referral_economy import bind
from src.services.referral_service import ReferralService


class Users:
    def __init__(self, docs):
        self.docs = {d['id']: copy.deepcopy(d) for d in docs}

    async def find_one(self, query, **kwargs):
        return copy.deepcopy(self.docs.get(query['id']))

    async def update_one(self, query, update, **kwargs):
        user = self.docs.get(query['id'])
        if not user:
            return NS(matched_count=0)
        user.update(update.get('$set', {}))
        for key, value in update.get('$inc', {}).items():
            user[key] = user.get(key, 0) + value
        return NS(matched_count=1)


@pytest.fixture
def graph(monkeypatch):
    users = Users([{'id': 1}, {'id': 2}, {'id': 3}, {'id': 4}])
    db = NS(users=users, referral_locks=NS(update_one=AsyncMock()))
    mongo = NS(database=db)
    lock = asyncio.Lock()
    async def tx(client, callback):
        async with lock:
            snapshot = copy.deepcopy(users.docs)
            try:
                return await callback('tx')
            except BaseException:
                users.docs = snapshot
                raise
    monkeypatch.setattr('src.services.referral_economy.transaction', tx)
    return mongo, users, db.referral_locks


@pytest.mark.asyncio
async def test_existing_user_can_bind_once_and_never_change_parent(graph):
    mongo, users, locks = graph
    users.docs[1].update(referral_binding_closed=True, created_at=None)
    assert (await bind(mongo, 1, 2))['success']
    assert not (await bind(mongo, 1, 3))['success']
    assert users.docs[1]['referrer_id'] == 2
    assert users.docs[2]['referral_count'] == 1
    assert users.docs[3].get('referral_count', 0) == 0
    assert locks.update_one.await_count == 2
    assert all(call.kwargs.get('session') == 'tx'
               for call in locks.update_one.await_args_list if '$inc' in call.args[1])


@pytest.mark.asyncio
async def test_competing_links_and_cycle_are_serialized(graph):
    mongo, users, _ = graph
    results = await asyncio.gather(bind(mongo, 1, 2), bind(mongo, 1, 3))
    assert sum(result['success'] for result in results) == 1
    assert sum(users.docs[i].get('referral_count', 0) for i in (2, 3)) == 1
    parent = users.docs[1]['referrer_id']
    assert not (await bind(mongo, parent, 1))['success']
    assert 'referrer_id' not in users.docs[parent]


@pytest.mark.asyncio
async def test_parallel_links_cannot_create_longer_cycle(graph):
    mongo, users, _ = graph
    users.docs[2]['referrer_id'] = 3
    users.docs[4]['referrer_id'] = 1
    # 1 -> 2 and 3 -> 4 form a cycle only if both commit.
    result = await asyncio.gather(bind(mongo, 1, 2), bind(mongo, 3, 4))
    assert sum(r['success'] for r in result) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('code', ['ref_0', 'ref_-1', 'ref_+1', 'ref_01', 'ref_1x',
                                  'ref_9223372036854775808', None])
async def test_invalid_deep_link_never_calls_bind(code):
    service = ReferralService(NS(database=NS()))
    service.user_service = NS(process_referral=AsyncMock())
    success, _ = await service.process_referral(7, code)
    assert not success
    service.user_service.process_referral.assert_not_awaited()


@pytest.mark.asyncio
async def test_existing_bot_start_tries_referral_without_regranting_starter():
    from src.bot.handlers.user_commands import cmd_start
    message = NS(chat=NS(type='private'), from_user=NS(id=7, username='old',
        first_name='Old', last_name=None, full_name='Old'), answer=AsyncMock())
    container = NS(user_service=NS(get_or_create=AsyncMock(return_value={
        'created': False, 'user': {'coins': 123}})),
        referral_service=NS(process_referral=AsyncMock(return_value=(True, 'Приглашение принято'))),
        settings=NS(dojo_app_url=''))
    await cmd_start(message, NS(args='ref_42'), container)
    container.referral_service.process_referral.assert_awaited_once_with(7, 'ref_42')
    messages = [call.args[0] for call in message.answer.await_args_list]
    assert 'Приглашение принято' in messages
    assert all('СТАРТОВЫЙ НАБОР' not in text for text in messages)


@pytest.mark.asyncio
async def test_alias_is_registered_in_command_filter():
    from src.bot.handlers.referral import router, cmd_ref
    handlers = [handler for handler in router.message.handlers if handler.callback == cmd_ref]
    assert any('rsenseireferal' in getattr(f.callback, 'commands', ())
               for h in handlers for f in h.filters)


@pytest.mark.asyncio
async def test_binding_resets_stale_progress_but_does_not_regrant_paid_bonus(graph):
    mongo, users, _ = graph
    users.docs[1].update(referral_version=2, referral_activity_days=['old1', 'old2'],
                         referral_paid_upgrade=True, referral_bonus_paid=True, coins=500)
    assert (await bind(mongo, 1, 2))['success']
    assert users.docs[1]['referral_activity_days'] == []
    assert users.docs[1]['referral_paid_upgrade'] is False
    assert users.docs[1]['referral_bonus_paid'] is True
    assert users.docs[1]['coins'] == 500


@pytest.mark.asyncio
async def test_signed_miniapp_existing_user_really_binds_once(graph):
    import time
    from aiohttp import web
    from aiohttp.test_utils import TestClient, TestServer
    from src.web.dojo_app import setup_dojo
    from tests.unit.test_hedgehog_game import signed

    mongo, users, _ = graph
    users.docs[7] = {'id': 7, 'coins': 123, 'referral_binding_closed': True}
    users.docs[42] = {'id': 42, 'coins': 0}
    ref = ReferralService(mongo)
    ref.user_service = NS(process_referral=lambda uid, parent: bind(mongo, uid, parent))
    registration = AsyncMock(return_value={'created': False, 'user': users.docs[7]})
    container = NS(settings=NS(bot_token='test-token', maintenance_mode=False),
        user_service=NS(get_or_create=registration), referral_service=ref,
        dojo_miner_service=NS(state=AsyncMock(return_value={'phase': 'ready', 'balance': 123})))
    app = web.Application()
    setup_dojo(app, container)
    async with TestClient(TestServer(app)) as client:
        auth = signed(now=int(time.time()), start_param='ref_42')
        assert (await client.post('/miniapp/dojo/api/entry', json={'initData': auth})).status == 200
        for _ in range(2):
            response = await client.post('/miniapp/dojo/api/state', json={'initData': auth})
            assert response.status == 200
        forged = signed(now=int(time.time())) + '&start_param=ref_3'
        assert (await client.post('/miniapp/dojo/api/state', json={'initData': forged})).status == 401
        too_big = signed(now=int(time.time()), start_param='ref_9223372036854775808')
        assert (await client.post('/miniapp/dojo/api/entry', json={'initData': too_big})).status == 200
    assert registration.await_count == 1
    assert users.docs[7]['referrer_id'] == 42 and users.docs[7]['coins'] == 123
    assert users.docs[42]['referral_count'] == 1 and users.docs[42]['coins'] == 0
