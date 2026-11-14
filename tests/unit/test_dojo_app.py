"""Local route/launcher checks; no Telegram credentials or production calls."""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from src.bot.handlers.dojo import cmd_dojo, dojo_url
from src.web.dojo_app import setup_dojo


@pytest.mark.parametrize('url', ['http://example.com', 'https://u:p@example.com',
                                  'javascript:alert(1)', 'https://', 'https://example.com:bad'])
def test_reject_bad_url(monkeypatch, url):
    monkeypatch.delenv('RENDER_EXTERNAL_URL', raising=False)
    assert dojo_url(SimpleNamespace(dojo_app_url=url)) is None


def test_render_origin(monkeypatch):
    monkeypatch.setenv('RENDER_EXTERNAL_URL', 'https://dojo-example.onrender.com/')
    assert dojo_url(SimpleNamespace()) == 'https://dojo-example.onrender.com/miniapp/dojo'
    assert dojo_url(SimpleNamespace(dojo_app_url='https://custom.example/game')) == 'https://custom.example/game'


async def test_launch_private(monkeypatch):
    monkeypatch.setenv('RENDER_EXTERNAL_URL', 'https://dojo-example.onrender.com')
    message = SimpleNamespace(chat=SimpleNamespace(type='private'), answer=AsyncMock())
    await cmd_dojo(message, SimpleNamespace(settings=SimpleNamespace()))
    button = message.answer.call_args.kwargs['reply_markup'].inline_keyboard[0][0]
    assert button.web_app.url == 'https://dojo-example.onrender.com/miniapp/dojo'
    assert 'балансом бота' in message.answer.call_args.args[0]


@pytest.mark.parametrize('chat_type', ['group', 'private'])
async def test_no_invalid_webapp_button(monkeypatch, chat_type):
    monkeypatch.delenv('RENDER_EXTERNAL_URL', raising=False)
    message = SimpleNamespace(chat=SimpleNamespace(type=chat_type), answer=AsyncMock())
    await cmd_dojo(message, SimpleNamespace(settings=SimpleNamespace()))
    assert 'reply_markup' not in message.answer.call_args.kwargs


async def test_page_routes():
    app = web.Application()
    setup_dojo(app)
    async with TestClient(TestServer(app)) as client:
        for path in ['/miniapp/dojo', '/miniapp/dojo/']:
            response = await client.get(path)
            assert response.status == 200
            assert response.content_type == 'text/html'
            assert response.headers['Cache-Control'] == 'no-store'
            assert 'frame-ancestors https://web.telegram.org' in response.headers['Content-Security-Policy']
            assert 'X-Frame-Options' not in response.headers
            text = await response.text()
            assert 'class GameLoop' in text
            assert 'telegram-web-app.js' in text
        assert (await client.get('/miniapp/dojo/missing')).status == 404
