"""Server authority, signed Telegram identity and idempotent daily game rewards."""
import asyncio
import copy
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from urllib.parse import urlencode
from unittest.mock import patch

import pytest

from src.core.exceptions import DailyAlreadyClaimedError
from src.services.daily_service import DailyService
from src.services.hedgehog_service import GameError, HedgehogService, utc_day
from src.web.telegram_auth import verify_init_data


def signed(user_id=7, now=1000, token='test-token', **extra):
    fields = {'user': json.dumps({'id': user_id, 'first_name': 'Ёж'}), 'auth_date': str(now), **extra}
    check = '\n'.join(f'{k}={v}' for k, v in sorted(fields.items()))
    secret = hmac.new(b'WebAppData', token.encode(), hashlib.sha256).digest()
    fields['hash'] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


def test_telegram_hmac_identity():
    assert verify_init_data(signed(), 'test-token', now=1001)['id'] == 7


@pytest.mark.parametrize('value', ['', 'garbage', signed() + '&user=evil', signed(user_id=-1), signed(now=1), signed(now=5000)])
def test_bad_expired_future_or_duplicated_auth_rejected(value):
    with pytest.raises((ValueError, TypeError)):
        verify_init_data(value, 'test-token', now=4000)


def test_tampered_user_or_wrong_bot_token_rejected():
    with pytest.raises(ValueError):
        verify_init_data(signed(), 'other-token', now=1001)
    with pytest.raises(ValueError):
        verify_init_data(signed().replace('auth_date=1000', 'auth_date=1001'), 'test-token', now=1001)


class Collection:
    """Small atomic fake implementing only the Mongo operators this feature uses."""
    def __init__(self, docs=()):
        self.docs = {d.get('_id', d.get('id')): copy.deepcopy(d) for d in docs}
        self.writes = []

    def matches(self, doc, query):
        for key, value in query.items():
            actual = doc.get(key)
            if isinstance(value, dict):
                if '$ne' in value and actual == value['$ne']:
                    return False
                if '$gte' in value and (actual is None or actual < value['$gte']):
                    return False
            elif actual != value:
                return False
        return True

    async def find_one(self, query):
        return next((copy.deepcopy(d) for d in self.docs.values() if self.matches(d, query)), None)

    async def find_one_and_update(self, query, changes, upsert=False, **kwargs):
        self.writes.append((copy.deepcopy(query), copy.deepcopy(changes)))
        found = next((d for d in self.docs.values() if self.matches(d, query)), None)
        if found is None:
            if not upsert:
                return None
            found = {k: v for k, v in query.items() if not isinstance(v, dict)}
            found.update(copy.deepcopy(changes.get('$setOnInsert', {})))
            self.docs[found.get('_id', found.get('id'))] = found
        found.update(copy.deepcopy(changes.get('$set', {})))
        for key, value in changes.get('$inc', {}).items():
            found[key] = found.get(key, 0) + value
        return copy.deepcopy(found)

    async def update_one(self, query, changes, **kwargs):
        return await self.find_one_and_update(query, changes, **kwargs)

    async def create_index(self, *args, **kwargs):
        pass


def services():
    db = SimpleNamespace(
        users=Collection([{'id': 7, 'is_banned': False, 'coins': 1000, 'xp': 500,
                           'daily_streak': 8, 'last_daily': datetime.now(timezone.utc) - timedelta(days=1)}]),
        bank=Collection([{'_id': 'main', 'balance': 100000}]),
        daily_claims=Collection(), transactions=Collection(), hedgehog_games=Collection(),
    )
    mongo = SimpleNamespace(database=db)
    daily = DailyService(mongo)
    return db, daily, HedgehogService(mongo, daily)


@pytest.mark.asyncio
async def test_reload_cannot_reroll_or_restart_clock():
    db, daily, game = services()
    invitation = await game.issue(7)
    assert (await game.issue(7))['token'] == invitation['token']
    with patch('src.services.hedgehog_service.time.time', return_value=100), \
         patch('src.services.hedgehog_service.secrets.randbelow', return_value=96) as roll:
        first = await game.start(invitation['token'], 7)
        second = await game.start(invitation['token'], 7)
    assert first == second
    assert roll.call_count == 1
    assert 'won' not in first


@pytest.mark.asyncio
async def test_probability_exactly_95_of_100_server_rolls():
    wins = 0
    for roll in range(100):
        db, daily, game = services()
        token = (await game.issue(7))['token']
        with patch('src.services.hedgehog_service.secrets.randbelow', return_value=roll):
            await game.start(token, 7)
        wins += next(iter(db.hedgehog_games.docs.values()))['won']
    assert wins == 95


@pytest.mark.asyncio
async def test_cannot_finish_early_or_play_another_users_game():
    db, daily, game = services()
    token = (await game.issue(7))['token']
    with pytest.raises(GameError):
        await game.start(token, 8)
    with pytest.raises(GameError):
        await game.finish(token, 7)
    with patch('src.services.hedgehog_service.time.time', return_value=100):
        await game.start(token, 7)
        response = await game.finish(token, 7)
    assert response['state'] == 'playing'
    assert db.users.docs[7]['coins'] == 1000


@pytest.mark.asyncio
async def test_failure_resets_only_streak_and_consumes_day():
    db, daily, game = services()
    token = (await game.issue(7))['token']
    with patch('src.services.hedgehog_service.secrets.randbelow', return_value=99), \
         patch('src.services.hedgehog_service.time.time', return_value=100):
        await game.start(token, 7)
    with patch('src.services.hedgehog_service.time.time', return_value=112):
        response = await game.finish(token, 7)
        assert await game.finish(token, 7) == response
    assert response['result']['success'] is False
    assert 'Вы не смогли погладить ежа' in response['result']['message']
    assert db.users.docs[7]['daily_streak'] == 0
    assert db.users.docs[7]['coins'] == 1000
    assert db.users.docs[7]['xp'] == 500
    assert not db.bank.writes and not db.transactions.writes
    assert all('$inc' not in change for _, change in db.users.writes)
    with pytest.raises(DailyAlreadyClaimedError):
        await game.issue(7)


@pytest.mark.asyncio
async def test_parallel_finish_and_restart_do_not_double_reward():
    db, daily, game = services()
    token = (await game.issue(7))['token']
    with patch('src.services.hedgehog_service.secrets.randbelow', return_value=0), \
         patch('src.services.hedgehog_service.time.time', return_value=100):
        await game.start(token, 7)
    with patch('src.services.hedgehog_service.time.time', return_value=112):
        a, b = await asyncio.gather(game.finish(token, 7), game.finish(token, 7))
    assert a == b and a['result']['success'] is True
    assert db.users.docs[7]['xp'] == 500 + a['result']['total_xp']
    assert db.users.docs[7]['coins'] == 1000 + a['result']['total_coins']
    assert db.users.docs[7]['daily_streak'] == 9
    assert len(db.transactions.docs) == 1
    # A different process/service instance still reads the atomic user receipt.
    again = await DailyService(SimpleNamespace(database=db)).settle_hedgehog(7, True, utc_day())
    assert again == a['result']
    assert len(db.users.writes) == 1
    query, changes = db.users.writes[0]
    assert query['hedgehog_day'] == {'$ne': utc_day()}
    assert changes['$set']['hedgehog_result'] == again


@pytest.mark.asyncio
async def test_new_day_cannot_settle_old_game():
    db, daily, game = services()
    token = (await game.issue(7))['token']
    with patch('src.services.hedgehog_service.utc_day', return_value='2000-01-01'):
        with pytest.raises(GameError):
            await game.start(token, 7)
    with pytest.raises(GameError):
        await daily.settle_hedgehog(7, True, '2000-01-01')
    assert not db.users.writes


@pytest.mark.asyncio
async def test_banned_user_cannot_claim_game():
    db, daily, game = services()
    db.users.docs[7]['is_banned'] = True
    with pytest.raises(GameError):
        await game.issue(7)
    with pytest.raises(GameError):
        await daily.settle_hedgehog(7, True, utc_day())
    assert not db.users.writes


@pytest.mark.asyncio
async def test_http_routes_auth_identity_and_reward_picture():
    import time
    from aiohttp import web
    from aiohttp.test_utils import TestClient, TestServer
    from pathlib import Path
    from src.web.hedgehog_app import setup_hedgehog
    db, daily, game = services()
    token = (await game.issue(7))['token']
    container = SimpleNamespace(hedgehog_service=game, settings=SimpleNamespace(
        BASE_DIR=Path(__file__).resolve().parents[2], bot_token='test-token', maintenance_mode=False))
    app = web.Application(client_max_size=16 * 1024)
    setup_hedgehog(app, container)
    async with TestClient(TestServer(app)) as client:
        for route in ['/miniapp/hedgehog', '/miniapp/hedgehog/app.css', '/miniapp/hedgehog/app.js']:
            response = await client.get(route)
            assert response.status == 200, route
            assert response.headers['Cache-Control'] == 'no-store'
            assert 'telegram.org' in response.headers['Content-Security-Policy']
        assert (await client.get('/miniapp/hedgehog/picture/0')).status == 200
        assert (await client.get('/miniapp/hedgehog/picture/999999')).status == 404
        url = '/miniapp/hedgehog/api/start'
        assert (await client.post(url, json={'session': token, 'user_id': 7})).status == 401
        assert (await client.post(url, json={'session': token, 'initData': signed(8, int(time.time()))})).status == 409
        payload = {'session': token, 'initData': signed(7, int(time.time())), 'won': True, 'user_id': 999}
        with patch('src.services.hedgehog_service.secrets.randbelow', return_value=0):
            response = await client.post(url, json=payload)
        assert response.status == 200
        data = await response.json()
        assert data['state'] == 'playing' and 'won' not in data
        doc = next(iter(db.hedgehog_games.docs.values()))
        doc['started_at'] -= 12
        response = await client.post('/miniapp/hedgehog/api/finish', json=payload)
        result = await response.json()
        assert result['result']['success'] is True
        assert result['image'].startswith('/miniapp/hedgehog/picture/')
        assert (await client.get(result['image'])).status == 200
        assert db.users.docs[7]['hedgehog_result'] == result['result']
        assert (await client.post(url, data='x' * 20000)).status == 413


@pytest.mark.asyncio
async def test_launch_native_widget_in_private_and_group_without_https():
    from pathlib import Path
    from unittest.mock import AsyncMock
    from src.bot.presenters.hedgehog_presenter import launch_hedgehog
    from src.bot.native_widgets import SendWidget
    db, daily, game = services()
    user = SimpleNamespace(id=7, username='petter', first_name='Ёж', last_name=None, is_bot=False)
    container = SimpleNamespace(settings=SimpleNamespace(BASE_DIR=Path(__file__).resolve().parents[2]),
                                user_service=SimpleNamespace(get_or_create=AsyncMock()), hedgehog_service=game)
    bot = AsyncMock()
    message = SimpleNamespace(chat=SimpleNamespace(type='private', id=7), answer=AsyncMock(), bot=bot)
    await launch_hedgehog(message, user, container)
    request = bot.call_args.args[0]
    assert isinstance(request, SendWidget)
    assert request.chat_id == 7 and request.allow_queries and not request.is_shared
    assert 'TelegramWidget.request' in request.html
    assert '/miniapp/' not in request.html
    message.chat.type = 'supergroup'
    message.chat.id = -1001234
    await launch_hedgehog(message, user, container)
    assert bot.call_args.args[0].chat_id == -1001234
    message.answer.assert_not_called()
    assert not db.users.writes


@pytest.mark.asyncio
async def test_crash_after_user_commit_recovers_without_double_credit():
    db, daily, game = services()
    token = (await game.issue(7))['token']
    with patch('src.services.hedgehog_service.secrets.randbelow', return_value=0), \
         patch('src.services.hedgehog_service.time.time', return_value=100):
        await game.start(token, 7)
    with patch('src.services.hedgehog_service.time.time', return_value=112):
        with patch.object(db.hedgehog_games, 'update_one', side_effect=RuntimeError('connection lost')):
            with pytest.raises(RuntimeError):
                await game.finish(token, 7)
        before = copy.deepcopy(db.users.docs[7])
        restarted = HedgehogService(SimpleNamespace(database=db), DailyService(SimpleNamespace(database=db)))
        result = await restarted.finish(token, 7)
    assert result['result'] == before['hedgehog_result']
    assert db.users.docs[7] == before
    assert len(db.users.writes) == 1


def test_native_html_limits_inline_image_and_no_miniapp():
    import re
    import zlib
    from pathlib import Path
    from src.widgets.hedgehog import to_hedgehog_html
    images = Path(__file__).resolve().parents[2] / 'src/infra/storage/ega'
    for token in ['A' * 32, 'z' * 32, '_' * 32, '-' * 32]:
        html = to_hedgehog_html(token, images)
        assert len(html.encode()) <= 32768
        assert len(zlib.compress(html.encode(), 9)) <= 4096
        assert 'data:image/jpeg;base64,' in html
        assert 'TelegramWidget.request' in html
        assert not re.search(r'https?://|fetch\(|WebApp|<iframe', html)
    with pytest.raises(ValueError):
        to_hedgehog_html('</script>', images)


@pytest.mark.asyncio
@pytest.mark.parametrize('roll', [0, 99])
async def test_native_queries_survive_real_aiogram_dispatch_and_pay_once(roll):
    from unittest.mock import AsyncMock
    from aiogram import Dispatcher, Bot
    from aiogram.types import Update
    from src.bot.native_widgets import HedgehogWidgetMiddleware
    db, daily, game = services()
    token = (await game.issue(7))['token']
    container = SimpleNamespace(settings=SimpleNamespace(maintenance_mode=False), hedgehog_service=game)
    dp = Dispatcher()
    dp.update.outer_middleware(HedgehogWidgetMiddleware(container))
    # Real Bot identity and Update model, with a mocked HTTP session only.
    bot = Bot('123456:TEST')
    bot.session = AsyncMock(return_value=True)
    def update(action, number):
        return Update.model_validate({'update_id': number, 'widget_query': {
            'id': str(number), 'from': {'id': 7}, 'chat': {'id': -1001234, 'type': 'supergroup'},
            'message_id': 3, 'data': f'hg:{action}:{token}'}})
    try:
        with patch('src.services.hedgehog_service.secrets.randbelow', return_value=roll), \
             patch('src.services.hedgehog_service.time.time', return_value=100):
            await dp.feed_update(bot, update('s', 1))
        first = json.loads(bot.session.call_args.args[1].data)
        assert first['state'] == 'playing' and 'won' not in first
        with patch('src.services.hedgehog_service.time.time', return_value=112):
            await dp.feed_update(bot, update('f', 2))
            await dp.feed_update(bot, update('f', 3))
        request = bot.session.call_args.args[1]
        final = json.loads(request.data)
        assert request.__api_method__ == 'answerWidgetQuery'
        assert final['result']['success'] is (roll < 95)
        assert len(request.data.encode()) <= 1024
        assert len(db.users.writes) == 1
        assert db.users.docs[7]['coins'] == 1000 + final['result']['total_coins']
        assert db.users.docs[7]['xp'] == 500 + final['result']['total_xp']
    finally:
        await bot.session.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['other_owner', 'copy', 'malformed', 'banned', 'maintenance'])
async def test_native_queries_reject_untrusted_actions(kind):
    from aiogram.types import Update
    from unittest.mock import AsyncMock
    from src.bot.native_widgets import HedgehogWidgetMiddleware
    db, daily, game = services()
    token = (await game.issue(7))['token']
    container = SimpleNamespace(settings=SimpleNamespace(maintenance_mode=kind == 'maintenance'), hedgehog_service=game)
    query = {'id': 'q', 'from': {'id': 8 if kind == 'other_owner' else 7}, 'chat': {'id': 7},
             'message_id': 1, 'data': 'broken' if kind == 'malformed' else f'hg:s:{token}'}
    if kind == 'banned':
        db.users.docs[7]['is_banned'] = True
    key = 'shared_widget_query' if kind == 'copy' else 'widget_query'
    event = Update.model_validate({'update_id': 1, key: query})
    bot = AsyncMock()
    handler = AsyncMock()
    await HedgehogWidgetMiddleware(container)(handler, event, {'bot': bot})
    assert 'error' in json.loads(bot.call_args.args[0].data)
    handler.assert_not_called()
    assert not db.users.writes
    assert next(iter(db.hedgehog_games.docs.values()))['state'] == 'issued'


@pytest.mark.asyncio
async def test_native_unsupported_api_does_not_spend_attempt_or_open_webapp():
    from pathlib import Path
    from unittest.mock import AsyncMock
    from aiogram.exceptions import TelegramNotFound
    from src.bot.native_widgets import SendWidget
    from src.bot.presenters.hedgehog_presenter import launch_hedgehog
    db, daily, game = services()
    user = SimpleNamespace(id=7, username=None, first_name='Ёж', last_name=None, is_bot=False)
    container = SimpleNamespace(settings=SimpleNamespace(BASE_DIR=Path(__file__).resolve().parents[2]),
                                user_service=SimpleNamespace(get_or_create=AsyncMock()), hedgehog_service=game)
    bot = AsyncMock(side_effect=TelegramNotFound(method=SendWidget(chat_id=7, html=''), message='Not Found'))
    message = SimpleNamespace(chat=SimpleNamespace(id=7), bot=bot, answer=AsyncMock())
    await launch_hedgehog(message, user, container)
    assert 'Попытка не потрачена' in message.answer.call_args.args[0]
    assert 'reply_markup' not in message.answer.call_args.kwargs
    assert not db.users.writes
    assert next(iter(db.hedgehog_games.docs.values()))['state'] == 'issued'


@pytest.mark.asyncio
async def test_native_beta_endpoint_requires_explicit_opt_in(monkeypatch):
    from src.bot import loader
    monkeypatch.setattr(loader.settings, 'telegram_widget_beta', True)
    bot = loader.create_bot()
    try:
        assert bot.session.api.api_url('TEST', 'sendWidget') == 'https://api.telegram.org/beta/botTEST/test/sendWidget'
    finally:
        await bot.session.close()
    monkeypatch.setattr(loader.settings, 'telegram_widget_beta', False)
    bot = loader.create_bot()
    try:
        assert bot.session.api.api_url('TEST', 'sendWidget') == 'https://api.telegram.org/botTEST/sendWidget'
    finally:
        await bot.session.close()
