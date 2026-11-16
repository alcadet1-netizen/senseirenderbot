"""Без production-запросов: новый launcher и статический маршрут."""
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from src.web.dojo_app import setup_dojo
from src.bot.handlers.dojo import dojo_url, cmd_dojo
from tests.unit.test_hedgehog_game import signed


@pytest.mark.parametrize('url', ['http://example.com', 'https://u:p@example.com', 'javascript:foo', 'https://example.com:bad'])
def test_bad_url(url):
    assert dojo_url(SimpleNamespace(dojo_app_url=url)) is None


def test_render_default(monkeypatch):
    monkeypatch.setenv('RENDER_EXTERNAL_URL', 'https://example.com/')
    assert dojo_url(SimpleNamespace(dojo_app_url='')) == 'https://example.com/miniapp/dojo'


@pytest.mark.asyncio
async def test_launcher(monkeypatch):
    msg = SimpleNamespace(chat=SimpleNamespace(type='private'), answer=AsyncMock())
    await cmd_dojo(msg, SimpleNamespace(settings=SimpleNamespace(dojo_app_url='https://example.com/miniapp/dojo')))
    button = msg.answer.call_args.kwargs['reply_markup'].inline_keyboard[0][0]
    assert button.web_app.url.endswith('/miniapp/dojo')
    assert 'SenseiCoin' in msg.answer.call_args.args[0]
    assert '30 Coin' in msg.answer.call_args.args[0]


@pytest.mark.asyncio
async def test_new_routes_only():
    app = web.Application()
    setup_dojo(app)
    async with TestClient(TestServer(app)) as client:
        for path in ('/miniapp/dojo', '/miniapp/dojo/', '/miniapp/dojo/style.css',
                     '/miniapp/dojo/game.js', '/miniapp/dojo/economy.js'):
            response = await client.get(path)
            assert response.status == 200
            assert "connect-src 'self'" in response.headers['Content-Security-Policy']
            assert 'https://telegram.org' in response.headers['Content-Security-Policy']
        assert (await client.get('/miniapp/dojo/ws')).status == 404
        assert (await client.post('/miniapp/dojo/rooms')).status == 404


@pytest.mark.asyncio
async def test_reward_api_requires_signature_and_returns_payout():
    start, claim = AsyncMock(return_value={'run': 'x', 'coins': 14}), AsyncMock(return_value={'coins': 14})
    container = SimpleNamespace(
        settings=SimpleNamespace(bot_token='test-token', maintenance_mode=False),
        dojo_service=SimpleNamespace(start=start, claim=claim))
    app = web.Application()
    setup_dojo(app, container)
    async with TestClient(TestServer(app)) as client:
        assert (await client.post('/miniapp/dojo/api/start', json={})).status == 401
        assert (await client.post('/miniapp/dojo/api/start', json={
            'initData': signed(now=int(time.time())) + '&user=evil'})).status == 401
        auth = signed(now=int(time.time()))
        response = await client.post('/miniapp/dojo/api/start', json={'initData': auth})
        assert response.status == 200 and (await response.json())['run'] == 'x'
        start.assert_awaited_once_with(7)
        response = await client.post('/miniapp/dojo/api/claim', json={
            'initData': auth, 'run': 'x', 'wave': 5, 'victory': True})
        assert response.status == 200 and (await response.json())['coins'] == 14
        claim.assert_awaited_once_with(7, 'x', 5, True)
