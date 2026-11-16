"""Майнер /dojo: лаунчер, статика и подписанный API старта/сбора."""
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from src.bot.handlers.dojo import cmd_dojo, dojo_url
from src.web.dojo_app import setup_dojo
from tests.unit.test_hedgehog_game import signed


@pytest.mark.parametrize('url', ['http://example.com', 'https://u:p@example.com',
                                 'javascript:foo', 'https://example.com:bad'])
def test_bad_url(url):
    assert dojo_url(SimpleNamespace(dojo_app_url=url)) is None


def test_render_default(monkeypatch):
    monkeypatch.setenv('RENDER_EXTERNAL_URL', 'https://example.com/')
    assert dojo_url(SimpleNamespace(dojo_app_url='')) == 'https://example.com/miniapp/dojo'


@pytest.mark.asyncio
async def test_launcher():
    msg = SimpleNamespace(chat=SimpleNamespace(type='private'), answer=AsyncMock())
    await cmd_dojo(msg, SimpleNamespace(
        settings=SimpleNamespace(dojo_app_url='https://example.com/miniapp/dojo')))
    button = msg.answer.call_args.kwargs['reply_markup'].inline_keyboard[0][0]
    assert button.web_app.url.endswith('/miniapp/dojo')
    assert 'Начать майнинг' in button.text
    text = msg.answer.call_args.args[0]
    assert '8 часов' in text and 'SenseiCoin' in text and '15 Coin/ч' in text
    assert 'SenseiBank' in text and 'Задания' in text and 'Улучшения' in text


@pytest.mark.asyncio
async def test_miner_assets_and_csp():
    app = web.Application()
    setup_dojo(app)
    async with TestClient(TestServer(app)) as client:
        for path in ('/miniapp/dojo', '/miniapp/dojo/', '/miniapp/dojo/style.css',
                     '/miniapp/dojo/miner.js', '/miniapp/dojo/assets/sensei.webp'):
            response = await client.get(path)
            assert response.status == 200, path
            assert "connect-src 'self'" in response.headers['Content-Security-Policy']
            assert 'https://telegram.org' in response.headers['Content-Security-Policy']
        webp = await client.get('/miniapp/dojo/assets/sensei.webp')
        assert webp.headers['Content-Type'] == 'image/webp'
        assert (await client.get('/miniapp/dojo/game.js')).status == 404
        assert (await client.get('/miniapp/dojo/renderer.js')).status == 404
        assert (await client.get('/miniapp/dojo/assets/kick.webp')).status == 404
        assert (await client.get('/miniapp/dojo/assets/mining.webp')).status == 404
        assert (await client.get('/miniapp/dojo/ws')).status == 404
        assert (await client.post('/miniapp/dojo/api/state', json={})).status == 503


@pytest.mark.asyncio
async def test_api_requires_signature_and_dispatches_actions():
    state = AsyncMock(return_value={'phase': 'ready', 'reward': 26, 'balance': 1000})
    start = AsyncMock(return_value={'phase': 'mining', 'reward': 26})
    collect = AsyncMock(return_value={'phase': 'ready', 'mined': 120, 'balance': 1000})
    list_tasks = AsyncMock(return_value=[{'slug': 'senseidurova', 'claimed': False}])
    claim = AsyncMock(return_value={
        'task': {'slug': 'senseidurova', 'claimed': True},
        'reward_coins': 10_000, 'energy_bonus': 100, 'new_coins': 20_000,
    })
    upgrades = AsyncMock(return_value={'pickaxe_level': 0, 'pickaxe_max': 100})
    prepare = AsyncMock(return_value={
        'kind': 'pickaxe', 'stars': 10, 'payload': 'dojobuy:v1:7:pickaxe:10:abc',
        'title': 'Кирка +10 Coin/ч', 'description': 'Постоянный бонус.',
    })
    create_invoice = AsyncMock(return_value='https://t.me/invoice/1')
    bank = AsyncMock(return_value={
        'bank_balance': 900, 'circulation': 100, 'total_supply': 1000, 'users': 2})
    container = SimpleNamespace(
        settings=SimpleNamespace(bot_token='test-token', maintenance_mode=False),
        dojo_miner_service=SimpleNamespace(state=state, start=start, collect=collect),
        dojo_task_service=SimpleNamespace(list_tasks=list_tasks, claim=claim),
        dojo_upgrade_service=SimpleNamespace(snapshot=upgrades, prepare=prepare),
        stats_service=SimpleNamespace(get_bank_summary=bank),
        bot=SimpleNamespace(create_invoice_link=create_invoice))
    app = web.Application()
    setup_dojo(app, container)
    async with TestClient(TestServer(app)) as client:
        assert (await client.post('/miniapp/dojo/api/state', json={})).status == 401
        assert (await client.post('/miniapp/dojo/api/state', json={
            'initData': signed(now=int(time.time())) + '&user=evil'})).status == 401
        auth = signed(now=int(time.time()))
        response = await client.post('/miniapp/dojo/api/state', json={'initData': auth})
        assert response.status == 200 and (await response.json())['phase'] == 'ready'
        state.assert_awaited_once_with(7)
        response = await client.post('/miniapp/dojo/api/start', json={'initData': auth})
        assert response.status == 200 and (await response.json())['phase'] == 'mining'
        start.assert_awaited_once_with(7)
        response = await client.post('/miniapp/dojo/api/collect', json={'initData': auth})
        assert response.status == 200 and (await response.json())['mined'] == 120
        collect.assert_awaited_once_with(7)
        response = await client.post('/miniapp/dojo/api/tasks', json={'initData': auth})
        assert response.status == 200
        assert (await response.json())['tasks'][0]['slug'] == 'senseidurova'
        list_tasks.assert_awaited_once_with(7)
        response = await client.post('/miniapp/dojo/api/task', json={
            'initData': auth, 'slug': 'senseidurova'})
        data = await response.json()
        assert response.status == 200 and data['phase'] == 'ready'
        assert data['reward_coins'] == 10_000 and data['energy_bonus'] == 100
        assert data['balance'] == 20_000 and data['task']['claimed'] is True
        claim.assert_awaited_once_with(7, 'senseidurova')
        response = await client.post('/miniapp/dojo/api/upgrades', json={'initData': auth})
        assert response.status == 200
        assert (await response.json())['upgrades']['pickaxe_max'] == 100
        upgrades.assert_awaited_once_with(7)
        response = await client.post('/miniapp/dojo/api/buy', json={
            'initData': auth, 'kind': 'pickaxe'})
        assert response.status == 200
        assert (await response.json())['invoice_url'] == 'https://t.me/invoice/1'
        prepare.assert_awaited_once_with(7, 'pickaxe')
        create_invoice.assert_awaited_once()
        response = await client.post('/miniapp/dojo/api/bank', json={'initData': auth})
        assert response.status == 200 and (await response.json())['total_supply'] == 1000
        bank.assert_awaited_once()
        assert (await client.post('/miniapp/dojo/api/kick', json={'initData': auth})).status == 404
        assert (await client.post('/miniapp/dojo/api/nope', json={'initData': auth})).status == 404
