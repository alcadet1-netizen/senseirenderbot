"""Mini App admin authorization and atomic task rewards."""
import copy
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from src.services.dojo_task_service import DojoTaskService
from src.services.hedgehog_service import GameError
from src.web.dojo_app import setup_dojo
from tests.unit.test_hedgehog_game import signed
from tests.unit.test_dojo_tasks import service


@pytest.mark.asyncio
async def test_admin_task_create_edit_and_validate():
    container, tasks, _, bot = service()
    bot.id = 99
    bot.get_chat = AsyncMock(return_value=SimpleNamespace(id=-100123, type='channel', title='Test'))
    bot.get_chat_member.return_value = SimpleNamespace(status='administrator')
    data = {'kind': 'channel', 'title': 'Канал', 'target': '@MyChannel',
            'reward_coins': 20, 'energy_bonus': 30, 'reward_gram_hundredths': 5,
            'reward_chests': 2, 'create_key': 'request-12345'}
    task = await tasks.save_admin_task(data, 7)
    assert task['kind'] == 'channel' and task['reward_gram_hundredths'] == 5
    assert task['reward_chests'] == 2
    repeat = await tasks.save_admin_task(data, 7)
    assert repeat['slug'] == task['slug']  # retry cannot create a second task
    doc = await tasks.tasks.find_one({'_id': task['slug']})
    assert doc['channel_id'] == -100123 and doc['reward_schema'] == 2
    changed = await tasks.save_admin_task({**data, 'slug': task['slug'], 'kind': 'link',
                                           'target': 'https://t.me/example_bot?start=abc'}, 7)
    assert changed['slug'] == task['slug'] and changed['button_label'] == 'Запустить'
    for field, bad in [('reward_coins', True), ('reward_chests', -1), ('energy_bonus', 1001),
                       ('reward_gram_hundredths', 100001)]:
        with pytest.raises(GameError):
            await tasks.save_admin_task({**data, field: bad}, 7)
    with pytest.raises(GameError):
        await tasks.save_admin_task({**data, 'kind': 'link', 'target': 'javascript:alert(1)'}, 7)
    bot.get_chat_member.return_value = SimpleNamespace(status='member')
    with pytest.raises(GameError, match='не администратор'):
        await tasks.save_admin_task(data, 7)


@pytest.mark.asyncio
async def test_admin_api_checks_signed_user_for_every_action():
    admin_tasks = AsyncMock(return_value=[])
    container = SimpleNamespace(
        settings=SimpleNamespace(bot_token='test-token', maintenance_mode=False, admin_ids=[]),
        dojo_miner_service=SimpleNamespace(state=AsyncMock(return_value={'phase': 'ready'})),
        dojo_task_service=SimpleNamespace(all_tasks=admin_tasks,
            save_admin_task=AsyncMock(), set_admin_task_active=AsyncMock()),
    )
    app = web.Application(); setup_dojo(app, container)
    auth = signed(now=int(time.time()))  # user 7
    async with TestClient(TestServer(app)) as client:
        response = await client.post('/miniapp/dojo/api/state', json={'initData': auth})
        assert (await response.json())['is_admin'] is False
        for action in ('admin_tasks', 'admin_save', 'admin_toggle', 'admin_grant'):
            assert (await client.post(f'/miniapp/dojo/api/{action}', json={'initData': auth})).status == 403
            assert (await client.post(f'/miniapp/dojo/api/{action}', json={})).status == 401
        admin_tasks.assert_not_awaited()
        container.settings.admin_ids = [7]
        response = await client.post('/miniapp/dojo/api/state', json={'initData': auth})
        assert (await response.json())['is_admin'] is True
        response = await client.post('/miniapp/dojo/api/admin_tasks', json={'initData': auth})
        assert response.status == 200 and (await response.json())['tasks'] == []
        admin_tasks.assert_awaited_once()
        response = await client.post('/miniapp/dojo/api/admin_grant', json={'initData': auth, 'request_id': 'bad'})
        assert response.status == 409


def atomic_service(monkeypatch, *, miner_doc=None, bank_ok=True):
    task = {'_id': 'task-demo', 'kind': 'link', 'active': True, 'username': 'example.org',
            'title': 'Example', 'url': 'https://example.org/', 'reward_schema': 2,
            'reward_coins': 40, 'energy_bonus': 30, 'reward_gram_hundredths': 15, 'reward_chests': 2}
    async def tx(mongo, fn):
        return await fn('session')
    monkeypatch.setattr('src.services.dojo_task_service.transaction', tx)
    tasks = SimpleNamespace(find_one=AsyncMock(return_value=copy.deepcopy(task)))
    claims = SimpleNamespace(find_one=AsyncMock(return_value=None), insert_one=AsyncMock())
    db = SimpleNamespace(dojo_tasks=tasks, dojo_task_claims=claims,
        users=SimpleNamespace(find_one=AsyncMock(return_value={'id': 7, 'coins': 100}), update_one=AsyncMock()),
        bank=SimpleNamespace(update_one=AsyncMock(return_value=SimpleNamespace(matched_count=int(bank_ok)))),
        transactions=SimpleNamespace(insert_one=AsyncMock()),
        dojo_daily=SimpleNamespace(update_one=AsyncMock()),
        dojo_miners=SimpleNamespace(find_one=AsyncMock(return_value=miner_doc),
            update_one=AsyncMock(return_value=SimpleNamespace(matched_count=1)), insert_one=AsyncMock()))
    container = SimpleNamespace(mongo_client=SimpleNamespace(database=db), economy_service=SimpleNamespace())
    return DojoTaskService(container), db, task


@pytest.mark.asyncio
async def test_atomic_task_grants_all_parts_with_same_session(monkeypatch):
    svc, db, task = atomic_service(monkeypatch)
    result = await svc._claim_atomic(7, task, '7:task-demo')
    assert (result['reward_coins'], result['energy_bonus'], result['reward_gram_hundredths'], result['reward_chests']) == (40, 30, 15, 2)
    assert result['new_coins'] == 140
    assert db.dojo_daily.update_one.await_args.args[1] == {'$inc': {'gram_hundredths': 15, 'chests': 2}}
    assert db.dojo_miners.insert_one.await_args.args[0]['task_energy_pending'][0]['amount'] == 30
    for call in (db.users.find_one, db.bank.update_one, db.users.update_one, db.transactions.insert_one,
                 db.dojo_daily.update_one, db.dojo_miners.insert_one, db.dojo_task_claims.insert_one):
        assert call.await_args.kwargs['session'] == 'session'


@pytest.mark.asyncio
async def test_atomic_task_replay_and_insufficient_bank(monkeypatch):
    svc, db, task = atomic_service(monkeypatch, bank_ok=False)
    with pytest.raises(GameError, match='SenseiBank'):
        await svc._claim_atomic(7, task, '7:task-demo')
    db.dojo_daily.update_one.assert_not_awaited()
    db.dojo_task_claims.insert_one.assert_not_awaited()
    db.dojo_task_claims.find_one.return_value = {'_id': '7:task-demo'}
    with pytest.raises(GameError, match='уже получена'):
        await svc._claim_atomic(7, task, '7:task-demo')
    db.users.update_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_atomic_task_energy_adds_to_running_cycle(monkeypatch):
    now = time.time()
    doc = {'_id': 7, 'started_at': now - 4000, 'finish_at': now + 6000,
           'collected': False, 'energy_start': 100, 'energy_max': 100, 'base_rate': 15,
           'amount': 18, 'version': 5}
    svc, db, task = atomic_service(monkeypatch, miner_doc=doc)
    await svc._claim_atomic(7, task, '7:task-demo')
    query, update = db.dojo_miners.update_one.await_args.args
    assert query == {'_id': 7, 'version': 5}
    assert update['$set']['task_energy_bonuses'][0]['amount'] == 30
    assert update['$set']['amount'] == 22


@pytest.mark.asyncio
async def test_admin_api_dispatches_save_toggle_and_chest_grant(monkeypatch):
    save = AsyncMock(return_value={'slug': 'task-id'})
    toggle = AsyncMock()
    grant = AsyncMock(return_value={'username': 'PlayerName', 'amount': 10})
    monkeypatch.setattr('src.services.dojo_daily_service.DojoDailyService',
                        lambda mongo: SimpleNamespace(grant_admin_chests=grant))
    container = SimpleNamespace(
        settings=SimpleNamespace(bot_token='test-token', maintenance_mode=False, admin_ids=[7]),
        dojo_miner_service=SimpleNamespace(), mongo_client=object(),
        dojo_task_service=SimpleNamespace(save_admin_task=save, set_admin_task_active=toggle))
    app = web.Application(); setup_dojo(app, container)
    auth = signed(now=int(time.time()))
    async with TestClient(TestServer(app)) as client:
        response = await client.post('/miniapp/dojo/api/admin_save', json={'initData': auth, 'task': {'title': 'Test'}})
        assert response.status == 200 and (await response.json())['task']['slug'] == 'task-id'
        save.assert_awaited_once_with({'title': 'Test'}, 7)
        response = await client.post('/miniapp/dojo/api/admin_toggle', json={'initData': auth, 'slug': 'task-id', 'active': False})
        assert response.status == 200
        toggle.assert_awaited_once_with('task-id', False, 7)
        data = {'initData': auth, 'request_id': 'grant-request-id', 'username': '@PlayerName', 'amount': 10}
        response = await client.post('/miniapp/dojo/api/admin_grant', json=data)
        assert response.status == 200 and (await response.json()) == {'username': 'PlayerName', 'amount': 10}
        grant.assert_awaited_once_with('PlayerName', 10, 7, 'web:7:grant-request-id')


@pytest.mark.asyncio
async def test_atomic_claim_rechecks_task_and_refuses_changed_subscription(monkeypatch):
    svc, db, task = atomic_service(monkeypatch)
    db.dojo_tasks.find_one.return_value = {**task, 'url': 'https://changed.example/'}
    with pytest.raises(GameError, match='изменилось'):
        await svc._claim_atomic(7, task, '7:task-demo')
    db.bank.update_one.assert_not_awaited()
    db.dojo_task_claims.insert_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_profile_admin_controls_are_hidden_and_do_not_use_html_for_titles():
    app = web.Application(); setup_dojo(app)
    async with TestClient(TestServer(app)) as client:
        html = await (await client.get('/miniapp/dojo')).text()
        js = await (await client.get('/miniapp/dojo/miner.js')).text()
    profile = html.split('<section id="view-profile"', 1)[1].split('</section>', 1)[0]
    assert 'id="admin-open"' in profile and 'id="admin-panel"' in profile
    assert 'id="admin-task-form"' in profile and 'id="admin-grant-form"' in profile
    assert 'model?.is_admin' in js and 'title.textContent = task.title' in js
    assert 'Подтвердить выдачу' in js


@pytest.mark.asyncio
async def test_admin_task_duplicate_channel_is_rejected():
    """Один канал — одно задание: иначе игрок «подписывается» дважды.

    Slug считается от случайного create_key, поэтому раньше каждое нажатие
    «Новое задание» добавляло ещё одну запись на тот же самый канал.
    """
    container, tasks, _, bot = service()
    bot.id = 99
    bot.get_chat = AsyncMock(return_value=SimpleNamespace(id=-100123, type='channel'))
    bot.get_chat_member.return_value = SimpleNamespace(status='administrator')
    data = {'kind': 'channel', 'title': 'Канал', 'target': '@MyChannel',
            'reward_coins': 20, 'create_key': 'request-12345'}
    first = await tasks.save_admin_task(data, 7)

    # Другой create_key = другая форма, но канал тот же.
    with pytest.raises(GameError, match='уже есть'):
        await tasks.save_admin_task({**data, 'title': 'Дубль',
                                     'create_key': 'request-67890'}, 7)

    # Регистр username не должен обходить проверку.
    with pytest.raises(GameError, match='уже есть'):
        await tasks.save_admin_task({**data, 'target': '@mychannel',
                                     'create_key': 'request-99999'}, 7)

    # При редактировании тот же канал — это не дубль.
    edited = await tasks.save_admin_task(
        {**data, 'slug': first['slug'], 'title': 'Обновлено'}, 7)
    assert edited['slug'] == first['slug'] and edited['title'] == 'Обновлено'


@pytest.mark.asyncio
async def test_admin_task_duplicate_link_is_rejected():
    container, tasks, _, bot = service()
    bot.id = 99
    base = {'kind': 'link', 'title': 'Приложение', 'target': 'https://t.me/dupe_bot?start=1',
            'reward_coins': 20, 'create_key': 'link-key-0001'}
    await tasks.save_admin_task(base, 7)
    with pytest.raises(GameError, match='уже есть'):
        await tasks.save_admin_task({**base, 'create_key': 'link-key-0002'}, 7)


@pytest.mark.asyncio
async def test_admin_save_returns_slug_of_existing_task_on_duplicate():
    """409 должен не просто ругаться, а нести slug — иначе UI не подскажет выход."""
    container, tasks, _, bot = service()
    bot.id = 99
    bot.get_chat = AsyncMock(return_value=SimpleNamespace(id=-100123, type='channel'))
    bot.get_chat_member.return_value = SimpleNamespace(status='administrator')
    saved = await tasks.save_admin_task(
        {'kind': 'channel', 'title': 'Первый', 'target': '@dupechannel',
         'reward_coins': 20, 'create_key': 'dupe-key-0001'}, 7)

    container.settings = SimpleNamespace(bot_token='test-token', maintenance_mode=False,
                                         admin_ids=[7])
    container.dojo_miner_service = SimpleNamespace(state=AsyncMock(return_value={'phase': 'ready'}))
    container.dojo_task_service = tasks
    app = web.Application(); setup_dojo(app, container)
    auth = signed(now=int(time.time()))
    async with TestClient(TestServer(app)) as client:
        response = await client.post('/miniapp/dojo/api/admin_save', json={
            'initData': auth,
            'task': {'kind': 'channel', 'title': 'Второй', 'target': '@dupechannel',
                     'reward_coins': 20, 'create_key': 'dupe-key-0002'},
        })
        assert response.status == 409
        body = await response.json()
        assert body['code'] == 'task_exists'
        assert body['slug'] == saved['slug'] and body['title'] == 'Первый'
        assert 'уже есть' in body['error']
