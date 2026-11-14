"""Local authoritative PvP tests; Telegram and time are mocked, not live calls."""
import hashlib
import hmac
import json
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import urlencode

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from src.bot.handlers.dojo import cmd_dojo_invite
from src.web.dojo_app import setup_dojo
from src.web.dojo_battle import Battle, load_rules
from src.web.dojo_multiplayer import Hub, Room

TOKEN = '123456:local-test-only'


def signed(uid, **extra):
    data = dict(auth_date=str(int(time.time())), user=json.dumps(dict(id=uid, first_name=f'P{uid}')), **extra)
    secret = hmac.new(b'WebAppData', TOKEN.encode(), hashlib.sha256).digest()
    data['hash'] = hmac.new(secret, '\n'.join(f'{k}={v}' for k, v in sorted(data.items())).encode(), hashlib.sha256).hexdigest()
    return urlencode(data)


def container():
    return SimpleNamespace(settings=SimpleNamespace(bot_token=TOKEN, dojo_app_url=''))


def bot():
    return SimpleNamespace(get_me=AsyncMock(return_value=SimpleNamespace(username='test_dojo_bot')),
                           save_prepared_inline_message=AsyncMock(return_value=SimpleNamespace(id='prepared')))


def test_battle_validates_resources_and_types():
    b = Battle(load_rules())
    assert b.players[0] == b.players[1]
    before = b.players[0]['energy']
    for index in (True, -1, 8, '0', {}, None):
        assert not b.command(0, 'summon', index)
    assert b.command(0, 'summon', 0)
    assert not b.command(0, 'summon', 0)
    assert b.players[0]['energy'] == before - 6
    assert not b.command(0, 'tower')
    assert not b.command(0, 'boost')
    assert not b.command(0, 'summon', 7)
    assert b.command(0, 'upgrade')
    assert b.players[0]['level'] == 2
    b.finish(1, 'leave')
    assert not b.command(0, 'qi')
    b.step(.05)
    assert b.elapsed == 0


def test_cap_projectile_reuse_and_long_match():
    r = load_rules()
    b = Battle(r)
    for _ in range(48):
        assert b.spawn(0, r['cards'][0])
    assert not b.spawn(0, r['cards'][0])
    target = next(u for u in b.units if u['active'])
    b.fire(1, target['x'], 0, target, 9000)
    target['active'] = False
    b.spawn(0, r['cards'][0])
    b.step(.05)
    assert target['hp'] == target['maxHp']
    # Every card, tower, upgrade, end condition and snapshot must serialize.
    b = Battle(r)
    for p in b.players:
        p.update(level=6, tower=3, energy=3500)
        p['charges'] = [c['cd'] for c in r['cards']]
    b.elapsed = 31
    for i in range(8):
        for side in (0, 1):
            assert b.command(side, 'summon', i)
    for _ in range(2400):
        b.step(.05)
    json.dumps(b.snapshot())
    assert len(b.units) == 96 and len(b.shots) == 80
    assert any(p['hp'] < p['maxHp'] for p in b.players) or len(b.snapshot()['units']) < 16


def test_room_lifecycle_and_tab_replacement():
    room = Room('x'*22, dict(id=1), load_rules(), 0)
    a, b, newer = object(), object(), object()
    assert room.join(dict(id=1), a, 0)[0] == 0
    assert room.join(dict(id=1), newer, 0)[1] is a
    room.detach(0, a, 0)
    assert room.links[0] is newer
    room.join(dict(id=2), b, 0)
    with pytest.raises(ValueError):
        room.join(dict(id=3), object(), 0)
    room.advance(.05, 1)
    assert room.status == 'countdown'
    room.advance(.05, 4)
    assert room.status == 'playing'
    room.detach(1, b, 5)
    room.advance(.05, 6)
    elapsed = room.battle.elapsed
    room.advance(.05, 30)
    assert room.status == 'paused' and room.battle.elapsed == elapsed
    room.join(dict(id=2), b, 31)
    room.advance(.05, 31)
    room.advance(.05, 34)
    assert room.status == 'playing'
    room.detach(1, b, 35)
    room.advance(.05, 81)
    assert room.status == 'ended' and room.battle.winner == 0


async def test_hub_native_invite_and_expiry():
    clock = [0]
    api = bot()
    h = Hub(container(), api, clock=lambda:clock[0])
    room = await h.create(dict(id=1))
    again = await h.create(dict(id=1))
    assert room is again and len(h.rooms) == 1
    assert api.save_prepared_inline_message.await_count == 1
    button = api.save_prepared_inline_message.call_args.kwargs['result'].reply_markup.inline_keyboard[0][0]
    assert button.url == room.invite_url
    assert '?start=dojo_' in button.url
    assert room.prepared_id == 'prepared'
    clock[0] = 601
    room.advance(.05, clock[0])
    h.reap()
    assert not h.members
    clock[0] = 662
    h.reap()
    assert not h.rooms


async def test_invite_deep_link():
    message = SimpleNamespace(text='/start dojo_'+'A'*22, chat=SimpleNamespace(type='private'), answer=AsyncMock())
    await cmd_dojo_invite(message, SimpleNamespace(settings=SimpleNamespace(dojo_app_url='https://example.com/miniapp/dojo')))
    button = message.answer.call_args.kwargs['reply_markup'].inline_keyboard[0][0]
    assert button.web_app.url.endswith('?room='+'A'*22)


async def receive_type(ws, kind):
    for _ in range(40):
        data = await ws.receive_json(timeout=3)
        if data['type'] == kind:
            return data
    raise AssertionError(f'No {kind} packet')


async def test_http_websocket_auth_sync_and_reconnect():
    app = web.Application(client_max_size=16*1024)
    setup_dojo(app, container(), bot())
    async with TestClient(TestServer(app)) as client:
        origin = str(client.make_url('')).rstrip('/')
        headers = dict(Origin=origin)
        path = '/miniapp/dojo/rooms'
        assert (await client.post(path, json=dict(initData=signed(1)))).status == 403
        assert (await client.post(path, headers=dict(Origin='https://evil.example'), json=dict(initData=signed(1)))).status == 403
        assert (await client.post(path, headers=headers, json=dict(initData='fake'))).status == 401
        resp = await client.post(path, headers=headers, json=dict(initData=signed(1)))
        assert resp.status == 200
        invite = await resp.json()
        room = invite['room']
        assert len(room) == 22 and 'prepared_id' in invite
        a = await client.ws_connect('/miniapp/dojo/ws', headers=headers)
        await a.send_json(dict(type='hello', room=room, initData=signed(1)))
        assert (await receive_type(a, 'welcome'))['side'] == 0
        assert (await receive_type(a, 'state'))['status'] == 'waiting'
        b = await client.ws_connect('/miniapp/dojo/ws', headers=headers)
        await b.send_json(dict(type='hello', room=room, initData=signed(2)))
        assert (await receive_type(b, 'welcome'))['side'] == 1
        third = await client.ws_connect('/miniapp/dojo/ws', headers=headers)
        await third.send_json(dict(type='hello', room=room, initData=signed(3)))
        assert (await receive_type(third, 'fatal'))['error']
        await third.close()
        state = await receive_type(a, 'state')
        while state['status'] != 'playing':
            state = await receive_type(a, 'state')
        assert state['players'][0] == state['players'][1]
        # The server ignores payload health/cost/damage and duplicate sequences.
        await a.send_json(dict(action='summon', card=0, seq=1, hp=1e9, damage=1e9, cost=0))
        await a.send_json(dict(action='summon', card=0, seq=1))
        state = await receive_type(a, 'state')
        while not state['units']:
            state = await receive_type(a, 'state')
        assert len(state['units']) == 1 and state['units'][0]['maxHp'] == 85
        remote = await receive_type(b, 'state')
        while not remote['units']:
            remote = await receive_type(b, 'state')
        assert remote['units'][0]['seed'] == state['units'][0]['seed']
        await b.close()
        state = await receive_type(a, 'state')
        while state['status'] != 'paused':
            state = await receive_type(a, 'state')
        b = await client.ws_connect('/miniapp/dojo/ws', headers=headers)
        await b.send_json(dict(type='hello', room=room, initData=signed(2)))
        assert (await receive_type(b, 'welcome'))['side'] == 1
        await b.send_json(dict(action='leave', seq=1))
        state = await receive_type(a, 'state')
        while state['status'] != 'ended':
            state = await receive_type(a, 'state')
        assert state['winner'] == 0 and state['reason'] == 'leave'
        await a.close()
        await b.close()


async def test_factions_are_validated_and_survive_reconnect():
    from src.web.dojo_multiplayer import HUB_KEY
    app = web.Application()
    setup_dojo(app, container(), bot())
    async with TestClient(TestServer(app)) as client:
        headers = dict(Origin=str(client.make_url('')).rstrip('/'))
        res = await client.post('/miniapp/dojo/rooms', headers=headers, json=dict(initData=signed(1)))
        token = (await res.json())['room']
        bad = await client.ws_connect('/miniapp/dojo/ws', headers=headers)
        await bad.send_json(dict(type='hello', room=token, initData=signed(1), faction=True))
        assert (await receive_type(bad, 'fatal'))['error']
        await bad.close()
        a = await client.ws_connect('/miniapp/dojo/ws', headers=headers)
        await a.send_json(dict(type='hello', room=token, initData=signed(1), faction=1))
        await receive_type(a, 'welcome')
        assert (await receive_type(a, 'state'))['factions'][0] == 1
        await a.close()
        a = await client.ws_connect('/miniapp/dojo/ws', headers=headers)
        await a.send_json(dict(type='hello', room=token, initData=signed(1), faction=0))
        await receive_type(a, 'welcome')
        state = await receive_type(a, 'state')
        assert state['factions'][0] == 1
        # Teams are cosmetic; a mirror matchup is supported and still equal.
        b = await client.ws_connect('/miniapp/dojo/ws', headers=headers)
        await b.send_json(dict(type='hello', room=token, initData=signed(2), faction=1))
        await receive_type(b, 'welcome')
        assert (await receive_type(b, 'state'))['factions'] == [1, 1]
        room = app[HUB_KEY].rooms[token]
        assert room.battle.players[0] == room.battle.players[1]
        await a.close()
        await b.close()
