"""Bounded single-process WebSocket rooms, authenticated by signed Telegram initData.

Only transient matches live in RAM. No persistent queue, file storage or rewards.
Deploy ONE bot/web process; restarts cancel rooms. Mongo remains the bot's sole DB.
"""
import asyncio
import contextlib
import json
import logging
import re
import secrets
import time
from urllib.parse import urlsplit

from aiohttp import WSMsgType, web
from aiogram.types import (InlineKeyboardButton, InlineKeyboardMarkup,
                           InlineQueryResultArticle, InputTextMessageContent)

from src.web.dojo_battle import Battle, load_rules
from src.web.telegram_auth import verify_init_data

log = logging.getLogger(__name__)
TOKEN = re.compile(r'^[A-Za-z0-9_-]{22}$')
HUB_KEY = web.AppKey('dojo_hub', object)


class Room:
    def __init__(self, token, user, rules, now):
        self.token = token
        self.users = [user, None]
        self.factions = [None, None]
        self.links = [None, None]
        self.missing = [now, now]
        self.last_seq = [0, 0]
        self.battle = Battle(rules)
        self.status = 'waiting'
        self.created = now
        self.changed = now
        self.countdown = None
        self.invite_url = ''
        self.prepared_id = None

    def finish(self, winner, reason, now):
        self.battle.finish(winner, reason)
        self.status, self.changed = 'ended', now

    def join(self, user, link, now):
        side = next((i for i, u in enumerate(self.users) if u and u['id'] == user['id']), None)
        if self.status == 'ended' and side is None:
            raise ValueError('Бой уже завершён.')
        if side is None:
            if self.users[1] is not None:
                raise ValueError('В комнате уже два игрока.')
            side = 1
            self.users[1] = user
        old = self.links[side]
        self.links[side], self.missing[side] = link, None
        return side, old

    def detach(self, side, link, now):
        # A replaced tab must not disconnect its replacement.
        if self.links[side] is link:
            self.links[side], self.missing[side] = None, now

    def advance(self, dt, now):
        if self.status == 'ended':
            return
        if self.status == 'waiting' and now - self.created > 600:
            self.finish(None, 'expired', now)
            return
        both = all(self.links)
        if both:
            if self.status in {'waiting', 'paused'}:
                self.status, self.countdown = 'countdown', now + 3
            if self.status == 'countdown' and now >= self.countdown:
                self.status = 'playing'
            if self.status == 'playing':
                self.battle.step(dt)
                if self.battle.ended:
                    self.status, self.changed = 'ended', now
        elif self.status in {'playing', 'countdown', 'paused'}:
            self.status = 'paused'
            expired = [i for i, since in enumerate(self.missing) if since is not None and now - since >= 45]
            if expired:
                connected = [i for i, link in enumerate(self.links) if link]
                self.finish(connected[0] if len(connected) == 1 else None, 'disconnect', now)

    def snapshot(self, now):
        data = self.battle.snapshot()
        data.update(type='state', status=self.status, room=self.token, seq=self.last_seq,
                    factions=[f if f is not None else i for i, f in enumerate(self.factions)],
                    names=[str((u or {}).get('first_name', 'Соперник'))[:48] for u in self.users],
                    connected=[bool(link) for link in self.links],
                    countdown=max(0, round((self.countdown or now) - now, 1)),
                    reconnectSeconds=max(0, round(45 - max((now - s for s in self.missing if s is not None), default=0))))
        return data


class Hub:
    MAX_ROOMS = 8

    def __init__(self, container, bot=None, clock=time.monotonic):
        self.container = container
        self.bot = bot
        self.clock = clock
        self.rules = load_rules()
        self.rooms = {}
        self.members = {}
        self.username = None
        self.task = None
        self.closed = False
        self.sockets = set()

    def authenticate(self, raw):
        user = verify_init_data(raw, self.container.settings.bot_token)
        if user.get('is_bot'):
            raise ValueError('Нужен пользователь Telegram.')
        return user

    async def create(self, user):
        if not self.username:
            me = await self.bot.get_me()
            self.username = me.username
            if not self.username or not re.fullmatch(r'[A-Za-z0-9_]{5,32}', self.username):
                raise ValueError('Не удалось получить имя бота.')
        # Recheck after await, so concurrent creates cannot reserve two rooms.
        existing = self.members.get(user['id'])
        if existing and existing in self.rooms:
            room = self.rooms[existing]
            if room.status != 'ended':
                if room.users[0]['id'] == user['id']:
                    return room
                raise ValueError('Сначала заверши текущий бой или выйди из него.')
        self.reap()
        if len(self.rooms) >= self.MAX_ROOMS:
            raise ValueError('Сервер занят. Повтори чуть позже.')
        token = secrets.token_urlsafe(16)
        room = Room(token, user, self.rules, self.clock())
        room.invite_url = f'https://t.me/{self.username}?start=dojo_{token}'
        self.rooms[token], self.members[user['id']] = room, token
        # Native Telegram chat picker shares a message WITH a clickable join button.
        # Older clients fall back to the same signed-room deep link via share/url.
        try:
            result = await asyncio.wait_for(self.bot.save_prepared_inline_message(
                user_id=user['id'],
                result=InlineQueryResultArticle(
                    id=token, title='⚔ Вызов на бой — Сенсей',
                    input_message_content=InputTextMessageContent(
                        message_text='⚔ Вызываю на бой в «Стенка на Стенку»!\nКомната на двоих. Без ставок и наград бота.', parse_mode=None),
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(text='⚔ Принять вызов', url=room.invite_url)]])),
                allow_user_chats=True, allow_group_chats=True,
                allow_bot_chats=False, allow_channel_chats=False,
            ), timeout=6)
            room.prepared_id = result.id
        except Exception:
            # Do not log tokens, initData, invite URLs or provider exception payloads.
            log.warning('Dojo native share unavailable; using deep-link fallback')
        return room

    def join(self, token, user, link):
        if not isinstance(token, str) or not TOKEN.fullmatch(token) or token not in self.rooms:
            raise ValueError('Комната не найдена или сервер перезапущен. Попроси новое приглашение.')
        existing = self.members.get(user['id'])
        if existing and existing != token and existing in self.rooms and self.rooms[existing].status != 'ended':
            raise ValueError('Ты уже участвуешь в другом бою.')
        room = self.rooms[token]
        side, old = room.join(user, link, self.clock())
        self.members[user['id']] = token
        return room, side, old

    def reap(self):
        now = self.clock()
        for token, room in list(self.rooms.items()):
            if room.status == 'ended':
                for user in room.users:
                    if user and self.members.get(user['id']) == token:
                        self.members.pop(user['id'], None)
                if now - room.changed > 60:
                    self.rooms.pop(token, None)

    async def run(self):
        last, accumulator, publish = self.clock(), 0., 0.
        while not self.closed:
            await asyncio.sleep(.025)
            now = self.clock()
            accumulator += min(.2, max(0., now - last))
            publish += now - last
            last = now
            while accumulator >= .05:
                for room in list(self.rooms.values()):
                    room.advance(.05, now)
                accumulator -= .05
            if publish >= .15:
                publish = 0.
                for room in self.rooms.values():
                    # Latest-only queues isolate slow sockets from the simulation.
                    packet = room.snapshot(now)
                    for link in room.links:
                        if link:
                            queue = link['queue']
                            if queue.full():
                                queue.get_nowait()
                            queue.put_nowait(packet)
                self.reap()

    async def close(self):
        self.closed = True
        if self.task:
            self.task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.task
        sockets = list(self.sockets)
        await asyncio.gather(*(ws.close(code=1001, message=b'Server restarting') for ws in sockets), return_exceptions=True)
        self.sockets.clear()
        self.rooms.clear()
        self.members.clear()


def _same_origin(request, container):
    origin = request.headers.get('Origin')
    if not origin:
        return False
    try:
        parsed = urlsplit(origin)
        configured = getattr(container.settings, 'dojo_app_url', '') if container else ''
        if configured:
            target = urlsplit(configured)
            return (parsed.scheme, parsed.netloc) == (target.scheme, target.netloc)
        # Render terminates TLS before aiohttp; compare the public authority, not
        # request.scheme, and never trust an arbitrary X-Forwarded-Host header.
        return parsed.scheme in {'http', 'https'} and parsed.netloc == request.host and not parsed.path
    except ValueError:
        return False


def setup_multiplayer(app, container, bot=None):
    hub = Hub(container, bot) if container and bot else None
    app[HUB_KEY] = hub

    def service(request):
        if not hub:
            raise web.HTTPServiceUnavailable(text='PvP требует запущенный сервер бота.')
        if not _same_origin(request, container):
            raise web.HTTPForbidden(text='Неверный origin.')
        return hub

    async def create(request):
        headers = {'Cache-Control': 'no-store'}
        try:
            h = service(request)
            payload = await request.json()
            if not isinstance(payload, dict):
                raise ValueError('Неверный запрос.')
            user = h.authenticate(payload.get('initData'))
        except (ValueError, TypeError, KeyError):
            return web.json_response({'error': 'Открой игру заново через /dojo в Telegram.'}, status=401, headers=headers)
        try:
            room = await h.create(user)
        except ValueError as exc:
            return web.json_response({'error': str(exc)}, status=409, headers=headers)
        except Exception:
            return web.json_response({'error': 'Telegram временно недоступен. Попробуй ещё.'}, status=503, headers=headers)
        return web.json_response(dict(room=room.token, invite_url=room.invite_url, prepared_id=room.prepared_id), headers=headers)

    async def socket(request):
        h = service(request)
        if len(h.sockets) >= 64:
            raise web.HTTPServiceUnavailable(text='Сервер занят.')
        ws = web.WebSocketResponse(heartbeat=15, max_msg_size=12288, receive_timeout=60)
        h.sockets.add(ws)
        try:
            await ws.prepare(request)
        except BaseException:
            h.sockets.discard(ws)
            raise
        room = side = sender = link = None
        try:
            first = await asyncio.wait_for(ws.receive_json(), timeout=10)
            if not isinstance(first, dict) or first.get('type') != 'hello':
                raise ValueError('Нужна авторизация Telegram.')
            user = h.authenticate(first.get('initData'))
            faction = first.get('faction', 0)
            if type(faction) is not int or faction not in (0, 1):
                raise ValueError('Неверный клан.')
            link = dict(ws=ws, queue=asyncio.Queue(maxsize=1))
            room, side, old = h.join(first.get('room'), user, link)
            # Choice is immutable after first connection, including reconnects.
            if room.factions[side] is None:
                room.factions[side] = faction
            if old:
                await old['ws'].close(code=4001, message=b'Opened in another tab')
            await ws.send_json(dict(type='welcome', side=side, room=room.token, seq=room.last_seq[side]))

            async def send():
                try:
                    while not ws.closed:
                        data = await link['queue'].get()
                        await asyncio.wait_for(ws.send_json(data), timeout=3)
                except (TimeoutError, ConnectionError, RuntimeError):
                    await ws.close()

            sender = asyncio.create_task(send())
            link['queue'].put_nowait(room.snapshot(h.clock()))
            rate_start, commands = h.clock(), 0
            async for msg in ws:
                if msg.type != WSMsgType.TEXT:
                    break
                if room.links[side] is not link:
                    break
                payload = json.loads(msg.data)
                if not isinstance(payload, dict):
                    raise ValueError('Неверная команда.')
                now = h.clock()
                if now - rate_start >= 1:
                    rate_start, commands = now, 0
                commands += 1
                if commands > 20:
                    raise ValueError('Слишком много команд.')
                seq = payload.get('seq')
                if type(seq) is not int or not 0 < seq < 2**53:
                    raise ValueError('Неверный номер команды.')
                if seq <= room.last_seq[side]:
                    continue
                room.last_seq[side] = seq
                if payload.get('action') == 'leave':
                    room.finish(1 - side if room.users[1 - side] else None, 'leave', now)
                elif room.status == 'playing':
                    accepted = room.battle.command(side, payload.get('action'), payload.get('card'))
                    if not accepted:
                        await ws.send_json(dict(type='error', error='Команда недоступна: проверь энергию, уровень и заряд.'))
                else:
                    await ws.send_json(dict(type='error', error='Дождись начала или восстановления связи.'))
        except (ValueError, TypeError, KeyError, TimeoutError):
            if not ws.closed:
                # Never echo invalid payloads or authentication exception internals.
                await ws.send_json(dict(type='fatal', error='Соединение недоступно. Проверь приглашение и открой игру через /dojo.'))
        except (ConnectionError, RuntimeError):
            pass
        finally:
            if room is not None and side is not None:
                room.detach(side, link, h.clock())
            if sender:
                sender.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await sender
            await ws.close()
            h.sockets.discard(ws)
        return ws

    async def startup(app):
        if hub:
            hub.task = asyncio.create_task(hub.run())

    async def cleanup(app):
        if hub:
            await hub.close()

    app.router.add_post('/miniapp/dojo/rooms', create)
    app.router.add_get('/miniapp/dojo/ws', socket)
    app.on_startup.append(startup)
    app.on_cleanup.append(cleanup)
