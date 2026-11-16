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
    assert '8 часов' in text and 'SenseiCoin' in text and '120' in text
    assert 'SenseiBank' in text


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
    state = AsyncMock(return_value={'phase': 'ready', 'reward': 120})
    start = AsyncMock(return_value={'phase': 'mining', 'reward': 120})
    collect = AsyncMock(return_value={'phase': 'ready', 'mined': 120, 'balance': 1000})
    container = SimpleNamespace(
        settings=SimpleNamespace(bot_token='test-token', maintenance_mode=False),
        dojo_miner_service=SimpleNamespace(state=state, start=start, collect=collect))
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
        assert (await client.post('/miniapp/dojo/api/kick', json={'initData': auth})).status == 404
        assert (await client.post('/miniapp/dojo/api/nope', json={'initData': auth})).status == 404
