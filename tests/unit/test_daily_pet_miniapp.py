import asyncio
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from src.services.daily_pet_service import PetRateLimit
from src.web.daily_pet_app import setup_daily_pet
from tests.unit.test_daily_pet import setup, issue
from tests.unit.test_hedgehog_game import signed


@pytest.mark.asyncio
async def test_miniapp_assets_hmac_owner_and_immutable_reward_window():
    db, service, container, _ = setup()
    reward, token = await issue(service)
    before = db.users.docs[7]['coins']
    app = web.Application()
    setup_daily_pet(app, container)
    async with TestClient(TestServer(app)) as client:
        for path in ('', '/app.css', '/app.js', '/art.webp'):
            response = await client.get('/miniapp/daily-pet' + path)
            assert response.status == 410
            assert response.headers['Cache-Control'] == 'no-store'
        for action in ('view', 'tap'):
            response = await client.post('/miniapp/daily-pet/api/' + action,
                                         json={'session': token, 'request_id': 'old-request'})
            assert response.status == 410
        assert db.users.docs[7]['coins'] == before
        assert db.users.docs[7]['daily_pet']['taps'] == 0


@pytest.mark.asyncio
async def test_authenticated_server_arrival_before_deadline_can_settle_after_it():
    db, service, _, _ = setup()
    _, token = await issue(service)
    with patch('src.services.daily_pet_service.time.time', return_value=120):
        result = await service.widget_action(token,7,'p','web:arrived-in-time',received_at=109.8)
        assert result['state'] == 'done' and result['taps'] == 1
        same = await service.widget_action(token,7,'p','web:arrived-in-time',received_at=109.8)
        assert same['taps'] == 1
        late = await service.widget_action(token,7,'p','web:late-request',received_at=115)
        assert late['taps'] == 1


@pytest.mark.asyncio
async def test_server_rate_slots_do_not_trust_tap_counts_or_double_pay_replays():
    db, service, _, _ = setup()
    _, token = await issue(service)
    with patch('src.services.daily_pet_service.time.time',return_value=105):
        await service.tap(token,7,'web:first',received_at=105.01)
        with pytest.raises(PetRateLimit):
            await service.tap(token,7,'web:second',received_at=105.04)
        await service.tap(token,7,'web:first',received_at=105.01)
        session = await service.tap(token,7,'web:third',received_at=105.11)
    assert session['taps'] == 2


@pytest.mark.asyncio
async def test_private_native_widget_does_not_require_render_origin(monkeypatch):
    from src.bot.presenters.daily_hedgehog import open_pet
    from src.bot.native_widgets import SendWidget
    db, service, container, _ = setup()
    _, token = await issue(service)
    container.settings.mini_app_url = ''
    monkeypatch.delenv('RENDER_EXTERNAL_URL', raising=False)
    message = SimpleNamespace(chat=SimpleNamespace(id=7,type='private'),answer=AsyncMock(),bot=AsyncMock())
    await open_pet(message,SimpleNamespace(id=7),container,token)
    message.bot.assert_not_awaited()
    message.answer.assert_awaited_once()
    assert db.users.docs[7]['daily_pet']['taps'] == 0


def test_reference_atlas_has_all_eight_hd_cells_and_no_replay_reward_control():
    from PIL import Image
    root=Path('src/web/daily_pet')
    with Image.open(root/'art.webp') as im:
        assert im.size==(1536,1024)
    js=(root/'app.js').read_text()
    assert 'onpointermove' not in js
    assert "document.addEventListener('pointerdown', touch)" in js
    assert 'request_id: requestId' in js
    assert 'Math.min(deadline' in js
    assert "$('close').onclick = () => tg?.close()" in js
