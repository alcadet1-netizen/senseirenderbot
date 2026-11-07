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
    container.settings.bot_token = 'test-token'
    reward, session = await service.claim(7)
    token = session['token']
    now = time.time()
    await service.activate(token, 7, now)
    app = web.Application(client_max_size=16*1024)
    setup_daily_pet(app, container)
    async with TestClient(TestServer(app)) as client:
        for path in ('', '/app.css', '/app.js', '/art.webp'):
            response = await client.get('/miniapp/daily-pet'+path)
            assert response.status == 200
            assert response.headers['Cache-Control'] == 'no-store'
            assert response.headers['Referrer-Policy'] == 'no-referrer'
        assert (await client.get('/miniapp/daily-pet/../telegram_auth.py')).status == 404
        url = '/miniapp/daily-pet/api/tap'
        assert (await client.post(url, json={'session': token, 'user_id': 7})).status == 401
        body = dict(session=token, initData=signed(8, int(now)), request_id='foreign-owner')
        assert (await client.post(url, json=body)).status == 409
        body.update(initData=signed(7,int(now)), user_id=999, taps=1000, coins=1e9, received_at=now-100)
        assert (await client.post(url, json={**body,'request_id':'bad'})).status == 400
        body['request_id']='unique-touch-one'
        response = await client.post(url, json=body)
        assert response.status == 200
        data = await response.json()
        assert data['taps'] == 1 and data['extra_coins'] == reward['total_coins']//10
        duplicate = await client.post(url,json=body)
        assert (await duplicate.json())['taps'] == 1
        assert db.users.docs[7]['daily_pet']['deadline'] == now+10
        db.users.docs[7]['daily_pet']['deadline'] = now-1
        late = await client.post(url,json={**body,'request_id':'late-touch-two','received_at':now-2})
        data = await late.json()
        assert data['state'] == 'done' and data['taps'] == 1
        assert db.users.docs[7]['xp'] == 500+reward['total_xp']
        assert (await client.post(url,data='x'*20000)).status == 413
        container.settings.maintenance_mode = True
        assert (await client.post(url,json=body)).status == 503


@pytest.mark.asyncio
async def test_authenticated_server_arrival_before_deadline_can_settle_after_it():
    db, service, _, _ = setup()
    _, token = await issue(service)
    with patch('src.services.daily_pet_service.time.time', return_value=120):
        result = await service.widget_action(token,7,'p','web:arrived-in-time',received_at=109.8)
        assert result['state'] == 'done' and result['taps'] == 1
        same = await service.widget_action(token,7,'p','web:arrived-in-time',received_at=109.8)
        assert same['taps'] == 1
        late = await service.widget_action(token,7,'p','web:late-request',received_at=110)
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
async def test_private_webapp_url_uses_render_origin_and_never_resets_or_pays(monkeypatch):
    from src.bot.presenters.daily_hedgehog import open_pet
    db, service, container, _ = setup()
    _, token = await issue(service)
    container.settings.mini_app_url = ''
    monkeypatch.setenv('RENDER_EXTERNAL_URL','https://sensei-cnsh.onrender.com')
    message = SimpleNamespace(chat=SimpleNamespace(id=7,type='private'),answer=AsyncMock())
    await open_pet(message,SimpleNamespace(id=7),container,token)
    url = message.answer.call_args.kwargs['reply_markup'].inline_keyboard[0][0].web_app.url
    assert url == f'https://sensei-cnsh.onrender.com/miniapp/daily-pet#session={token}'
    assert '?session=' not in url
    assert db.users.docs[7]['daily_pet']['taps'] == 0


@pytest.mark.asyncio
async def test_non_https_webapp_config_does_not_create_button_or_change_money(monkeypatch):
    from src.bot.presenters.daily_hedgehog import open_pet
    db, service, container, _ = setup()
    _, token = await issue(service)
    before=db.users.docs[7]['coins']
    container.settings.mini_app_url='http://insecure.example'
    message=SimpleNamespace(chat=SimpleNamespace(id=7,type='private'),answer=AsyncMock())
    await open_pet(message,SimpleNamespace(id=7),container,token)
    assert 'reply_markup' not in message.answer.call_args.kwargs
    assert db.users.docs[7]['coins']==before


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
