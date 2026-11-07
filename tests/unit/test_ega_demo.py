"""Visual /ega never touches economy services or a daily receipt."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
import zlib

import pytest

from src.bot.handlers.widget_check import cmd_ega
from src.widgets.daily_pet import to_daily_pet_html


def fixtures(uid=7, chat='private'):
    message = SimpleNamespace(chat=SimpleNamespace(id=7, type=chat),
        from_user=SimpleNamespace(id=uid) if uid else None, answer=AsyncMock(), bot=AsyncMock())
    # Deliberately no database/daily/reward service: the handler must not need one.
    container = SimpleNamespace(settings=SimpleNamespace(admin_ids=[7], BASE_DIR=Path('.')))
    return message, container


@pytest.mark.asyncio
@pytest.mark.parametrize('uid,chat', [(8,'private'), (7,'supergroup'), (7,'group'), (None,'private')])
async def test_ega_rejects_non_admin_or_non_private(uid, chat):
    message, container = fixtures(uid, chat)
    with patch('src.bot.handlers.widget_check.send_native_widget', new_callable=AsyncMock) as send:
        await cmd_ega(message, container)
        send.assert_not_called()
    assert 'только администратору' in message.answer.call_args.args[0]


@pytest.mark.asyncio
async def test_ega_sends_local_demo_without_queries_or_services():
    message, container = fixtures()
    with patch('src.bot.handlers.widget_check.send_native_widget', new_callable=AsyncMock) as send:
        await cmd_ega(message, container)
    send.assert_awaited_once()
    assert send.call_args.args[2] == 7
    html = send.call_args.args[3]
    assert send.call_args.kwargs == {'allow_queries': False}
    assert 'TelegramWidget.request' not in html
    assert 'Тестовый бонус (без начисления)' in html
    assert 'https://t.me/airchatton' in html
    assert '15000' in html
    assert len(zlib.compress(html.encode(),9)) <= 3900


@pytest.mark.asyncio
async def test_ega_reports_local_error():
    message, container = fixtures()
    with patch('src.widgets.daily_pet.to_daily_pet_html', side_effect=ValueError('bad')):
        await cmd_ega(message, container)
    assert 'Не удалось собрать' in message.answer.call_args.args[0]


def test_production_renderer_still_uses_server_requests():
    snapshot = dict(state='playing', remaining_ms=15000, taps=0, extra_coins=0, base_coins=55)
    live = to_daily_pet_html('B'*32, Path('.'), snapshot)
    demo = to_daily_pet_html('B'*32, Path('.'), snapshot, demo=True)
    assert 'TelegramWidget.request' in live and 'TelegramWidget.request' not in demo
    assert 'B'*32 not in demo
    assert 'Тест завершён. Награды не начислялись.' in demo
