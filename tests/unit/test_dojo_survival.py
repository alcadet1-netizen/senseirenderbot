"""Без production-запросов: новый launcher и статический маршрут."""
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from src.web.dojo_app import setup_dojo
from src.bot.handlers.dojo import dojo_url, cmd_dojo


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
    assert 'балансом бота' in msg.answer.call_args.args[0]


@pytest.mark.asyncio
async def test_new_routes_only():
    app = web.Application()
    setup_dojo(app)
    async with TestClient(TestServer(app)) as client:
        for path in ('/miniapp/dojo', '/miniapp/dojo/', '/miniapp/dojo/style.css', '/miniapp/dojo/game.js'):
            response = await client.get(path)
            assert response.status == 200
            assert "connect-src 'none'" in response.headers['Content-Security-Policy']
        assert (await client.get('/miniapp/dojo/ws')).status == 404
        assert (await client.post('/miniapp/dojo/rooms')).status == 404
