"""Майнер /dojo: лаунчер, статика и подписанный API старта/сбора."""
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from src.bot.handlers.dojo import cmd_dojo, dojo_url
from src.domain.entities.referral import ReferralStats
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
    assert '3 часа' in text and 'SenseiCoin' in text and '15 Coin/ч' in text
    assert 'SenseiBank' in text and 'Задания' in text and 'Улучшения' in text


@pytest.mark.asyncio
async def test_miner_assets_and_csp():
    app = web.Application()
    setup_dojo(app)
    async with TestClient(TestServer(app)) as client:
        for path in ('/miniapp/dojo', '/miniapp/dojo/', '/miniapp/dojo/style.css',
                     '/miniapp/dojo/miner.js', '/miniapp/dojo/assets/sensei.webp',
                     '/miniapp/dojo/assets/loading-hero.webp'):
            response = await client.get(path)
            assert response.status == 200, path
            assert "connect-src 'self'" in response.headers['Content-Security-Policy']
            assert 'https://telegram.org' in response.headers['Content-Security-Policy']
        page = await client.get('/miniapp/dojo')
        html = await page.text()
        assert 'data-tab="referrals"' in html and 'id="view-referrals"' in html
        webp = await client.get('/miniapp/dojo/assets/sensei.webp')
        assert webp.headers['Content-Type'] == 'image/webp'
        hero = await client.get('/miniapp/dojo/assets/loading-hero.webp')
        assert hero.headers['Content-Type'] == 'image/webp'
        assert (await client.get('/miniapp/dojo/game.js')).status == 404
        assert (await client.get('/miniapp/dojo/renderer.js')).status == 404
        assert (await client.get('/miniapp/dojo/assets/kick.webp')).status == 404
        assert (await client.get('/miniapp/dojo/assets/mining.webp')).status == 404
        assert (await client.get('/miniapp/dojo/ws')).status == 404
        assert (await client.post('/miniapp/dojo/api/state', json={})).status == 503


@pytest.mark.asyncio
async def test_miner_has_boot_screen():
    app = web.Application()
    setup_dojo(app)
    async with TestClient(TestServer(app)) as client:
        html = await (await client.get('/miniapp/dojo')).text()
        css = await (await client.get('/miniapp/dojo/style.css')).text()
        js = await (await client.get('/miniapp/dojo/miner.js')).text()
    assert 'id="boot"' in html
    assert '/miniapp/dojo/assets/loading-hero.webp' in html
    assert 'id="boot-bar"' in html and 'id="boot-percent"' in html
    assert 'ЗАГРУЗКА…' in html and 'SENSEI' in html and 'POINTS' in html
    assert 'role="progressbar"' in html
    assert '.boot-puff' in css and '.boot-spark' in css
    assert '@keyframes boot-smoke-drift' in css
    assert '.boot.is-done' in css
    assert 'prefers-reduced-motion' in css
    assert 'function seedBoot' in js
    assert 'function bootSetGoal' in js
    assert 'allSettled' in js and '9000' in js
    assert '"ЗАГРУЗКА…": "LOADING…"' in js


@pytest.mark.asyncio
async def test_miner_has_language_switch_and_scrollable_stage():
    app = web.Application()
    setup_dojo(app)
    async with TestClient(TestServer(app)) as client:
        html = await (await client.get('/miniapp/dojo')).text()
        assert 'data-lang="en"' in html and 'data-lang="ru"' in html
        assert 'data-i18n="ТВОИ ОЧКИ"' in html
        assert 'data-i18n="Майнинг"' in html
        assert 'data-i18n-aria="Разделы майнера"' in html
        css = await (await client.get('/miniapp/dojo/style.css')).text()
        assert '.lang-switch' in css
        assert '#app.tabs-open .stage' in css
        assert 'overflow-y: hidden' in css
        assert 'overflow-y: auto' in css
        assert 'max-height: none' in css
        js = await (await client.get('/miniapp/dojo/miner.js')).text()
        assert 'const EN =' in js
        assert 'Майнинг: "Mining"' in js
        assert 'applyTranslations' in js


@pytest.mark.asyncio
async def test_api_requires_signature_and_dispatches_actions():
    state = AsyncMock(return_value={'phase': 'ready', 'reward': 20, 'balance': 1000})
    start = AsyncMock(return_value={'phase': 'mining', 'reward': 20})
    collect = AsyncMock(return_value={'phase': 'ready', 'mined': 20, 'balance': 1000})
    list_tasks = AsyncMock(return_value=[{'slug': 'senseidurova', 'claimed': False}])
    claim = AsyncMock(return_value={
        'task': {'slug': 'senseidurova', 'claimed': True},
        'reward_coins': 10_000, 'energy_bonus': 100, 'new_coins': 20_000,
    })
    upgrades = AsyncMock(return_value={'pickaxe_level': 0, 'pickaxe_max': 100})
    prepare = AsyncMock(return_value={
        'kind': 'pickaxe', 'stars': 10, 'payload': 'dojobuy:v1:7:pickaxe:10:abc',
        'title': 'Кирка +10 Coin/ч', 'description': 'Постоянный бонус.',
    })
    create_invoice = AsyncMock(return_value='https://t.me/invoice/1')
    prepare_share = AsyncMock(return_value=SimpleNamespace(
        id='prep-7', expiration_date=123456))
    bank = AsyncMock(return_value={
        'bank_balance': 900, 'circulation': 100, 'total_supply': 1000, 'users': 2})
    burn = AsyncMock(return_value={'success': True, 'amount': 100, 'balance': 900})
    referral_stats = ReferralStats(
        user_id=7, level_1_count=3, level_1_active=2, level_2_count=1,
        level_3_count=4, level_3_active=1, total_coins_earned=125.5,
        bonus_eligible=True, activity_days=2, paid_upgrade=True)
    referral_stats = AsyncMock(return_value=referral_stats)
    referral_members = AsyncMock(return_value=[
        {'name': 'Sensei', 'username': 'sensei', 'active': True}])
    container = SimpleNamespace(
        settings=SimpleNamespace(bot_token='test-token', maintenance_mode=False),
        dojo_miner_service=SimpleNamespace(state=state, start=start, collect=collect),
        dojo_task_service=SimpleNamespace(list_tasks=list_tasks, claim=claim),
        dojo_upgrade_service=SimpleNamespace(snapshot=upgrades, prepare=prepare),
        stats_service=SimpleNamespace(get_bank_summary=bank),
        burn_service=SimpleNamespace(burn=burn),
        referral_service=SimpleNamespace(
            get_stats=referral_stats, get_level_members=referral_members),
        bot=SimpleNamespace(
            create_invoice_link=create_invoice,
            save_prepared_inline_message=prepare_share,
            get_me=AsyncMock(return_value=SimpleNamespace(username='sensei_bot'))))
    app = web.Application()
    setup_dojo(app, container)
    async with TestClient(TestServer(app)) as client:
        assert (await client.post('/miniapp/dojo/api/state', json={})).status == 401
        assert (await client.post('/miniapp/dojo/api/referrals', json={
            'level': 1})).status == 401
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
        assert response.status == 200 and (await response.json())['mined'] == 20
        collect.assert_awaited_once_with(7)
        response = await client.post('/miniapp/dojo/api/tasks', json={'initData': auth})
        assert response.status == 200
        assert (await response.json())['tasks'][0]['slug'] == 'senseidurova'
        list_tasks.assert_awaited_once_with(7)
        response = await client.post('/miniapp/dojo/api/task', json={
            'initData': auth, 'slug': 'senseidurova'})
        data = await response.json()
        assert response.status == 200 and data['phase'] == 'ready'
        assert data['reward_coins'] == 10_000 and data['energy_bonus'] == 100
        assert data['balance'] == 20_000 and data['task']['claimed'] is True
        claim.assert_awaited_once_with(7, 'senseidurova')
        response = await client.post('/miniapp/dojo/api/upgrades', json={'initData': auth})
        assert response.status == 200
        assert (await response.json())['upgrades']['pickaxe_max'] == 100
        upgrades.assert_awaited_once_with(7)
        response = await client.post('/miniapp/dojo/api/buy', json={
            'initData': auth, 'kind': 'pickaxe'})
        assert response.status == 200
        assert (await response.json())['invoice_url'] == 'https://t.me/invoice/1'
        prepare.assert_awaited_once_with(7, 'pickaxe')
        create_invoice.assert_awaited_once()
        response = await client.post('/miniapp/dojo/api/bank', json={'initData': auth})
        assert response.status == 200 and (await response.json())['total_supply'] == 1000
        bank.assert_awaited_once()
        response = await client.post('/miniapp/dojo/api/burn', json={
            'initData': auth, 'amount': 100})
        data = await response.json()
        assert response.status == 200
        assert data['burn']['amount'] == 100 and data['balance'] == 900
        burn.assert_awaited_once_with(7, 100)
        response = await client.post('/miniapp/dojo/api/burn', json={
            'initData': auth, 'amount': 100,
            'request_id': 'burn-request-1234'})
        assert response.status == 200
        burn.assert_awaited_with(7, 100, 'burn-request-1234')
        response = await client.post('/miniapp/dojo/api/referrals', json={
            'initData': auth, 'level': 2})
        data = await response.json()
        assert response.status == 200
        assert data['link'] == 'https://t.me/sensei_bot?start=ref_7'
        assert data['earned'] == 125.5 and data['level'] == 2
        assert [item['count'] for item in data['levels']] == [3, 1, 4]
        assert data['members'][0]['username'] == 'sensei'
        assert data['rank']['title'] == 'Новичок'
        assert data['rank']['next']['title'] == 'Ученик'
        assert data['rank']['progress'] == 60.0
        assert data['bonus'] == {
            'eligible': True, 'paid': False, 'activity_days': 2,
            'paid_upgrade': True}
        assert data['share_body'].startswith('🥷') and '3 часа' in data['share_body']
        assert data['share_text'].endswith('start=ref_7')
        referral_members.assert_awaited_once_with(7, level=2, limit=10)
        response = await client.post('/miniapp/dojo/api/share', json={
            'initData': auth})
        assert response.status == 200
        shared = await response.json()
        assert shared['prepare_id'] == 'prep-7'
        prepared = prepare_share.await_args.kwargs
        assert prepared['user_id'] == 7
        assert prepared['allow_user_chats'] is True
        assert prepared['allow_group_chats'] is True
        article = prepared['result']
        assert 'start=ref_7' in article.input_message_content.message_text
        button = article.reply_markup.inline_keyboard[0][0]
        assert button.text == '⛏ Майнинг'
        assert button.url == 'https://t.me/sensei_bot?start=ref_7'
        assert (await client.post('/miniapp/dojo/api/kick', json={'initData': auth})).status == 404
        assert (await client.post('/miniapp/dojo/api/nope', json={'initData': auth})).status == 404


@pytest.mark.asyncio
async def test_miner_keeps_action_slot_and_renders_new_layers():
    app = web.Application()
    setup_dojo(app)
    async with TestClient(TestServer(app)) as client:
        html = await (await client.get('/miniapp/dojo')).text()
        css = await (await client.get('/miniapp/dojo/style.css')).text()
        js = await (await client.get('/miniapp/dojo/miner.js')).text()
    # The progress meter stays in flow in every phase, so starting or
    # collecting never removes a block and pushes the orb down.
    assert 'id="mine-meter" class="mine-meter is-idle"' in html
    assert 'id="orb" class="orb"' in html
    assert '.mine-meter.is-idle' in css
    assert '.orb,' in css and '.phase-mining .orb,' in css
    assert 'grid-template-rows' in css
    # The central sticker is only a small ROAD MAP button; the complete
    # English roadmap lives on its own full-screen view.
    assert 'id="roadmap"' in html and 'class="roadmap-sticker"' in html
    assert '>ROAD MAP</b>' in html
    assert 'id="burn"' in html and 'class="burn-sticker"' in html
    assert 'id="burn-sheet"' in html and 'id="burn-confirm"' in html
    assert 'AIRDROP' in html and 'Q4 2026' in html
    assert 'id="roadmap-sheet"' in html and 'roadmap-screen' in html
    assert 'TGE · FINISH MINE' in html and 'WHEN ALL COINS ARE MINED' in html
    assert 'DEX LISTING' in html and 'PLANNED · NO DATE' in html
    assert 'No listing or trading is guaranteed.' in html
    assert 'Three-hour mining cycles.' in html
    assert 'Four-hour mining cycles.' not in html
    assert 'id="energy-card"' in html and 'id="energy-refill"' in html
    assert '5 ⭐ · ПОПОЛНИТЬ' in html
    assert 'Баланс (как в чате)' not in html
    assert 'data-i18n="Баланс"' in html
    assert 'id="chain-panel"' in html and 'id="chain-feed"' in html
    assert 'id="ref-share" class="ref-share-button"' in html
    assert 'id="ref-link" class="ref-link"' in html
    assert '3 часа' in html and '8 часов' not in html
    assert '3 ЧАСА' in js and '8 ЧАСОВ' not in js
    assert 'seedMiningParticles' in js and 'paintChain' in js
    assert 'makeChainRow' in js and 'chain-row' in css


@pytest.mark.asyncio
async def test_miner_has_centred_blade_timer_and_layered_ambient():
    app = web.Application()
    setup_dojo(app)
    async with TestClient(TestServer(app)) as client:
        html = await (await client.get('/miniapp/dojo')).text()
        css = await (await client.get('/miniapp/dojo/style.css')).text()
        js = await (await client.get('/miniapp/dojo/miner.js')).text()
    # A dedicated vector face sits inside the orb instead of a text clock.
    assert 'id="timer-face"' in html and 'id="timer-digits"' in html
    assert 'id="timer-glyphs"' in html and 'viewBox="0 0 181 48"' in html
    assert 'TIMER_SEGMENTS' in js and 'TIMER_DIGITS' in js and 'TIMER_LAYOUT' in js
    assert 'function buildTimerFace' in js and 'function paintTimerFace' in js
    assert '.orb-button.is-timer .orb-label' in css and '.timer-seg.is-on' in css
    # HUD rails use one shared max width and the timer canvas is centred.
    assert '--hud-max: 448px' in css and '--hud-gutter' in css
    assert 'place-items: center' in css and 'width: min(94%, 166px)' in css
    # The flame is an inline sibling of the caption, never behind the glyphs.
    assert 'class="burn-flame"' in html and 'class="burn-title"' in html
    assert '.burn-sticker' in css and '.burn-title' in css
    assert 'align-items: center' in css
    # Ambient depth: aura, ray, mist, dust, petals, matrix and scanline.
    for layer in ('.ambient-aura', '.ambient-ray', '.ambient-puff',
                  '.ambient-mote', '.sakura-leaf', '.matrix-col', '.ambient-scan'):
        assert layer in css or layer in js
    assert 'function seedAmbient' in js
    assert 'prefers-reduced-motion' in css


@pytest.mark.asyncio
async def test_direct_referral_link_requires_explicit_configuration(monkeypatch):
    from src.web.dojo_app import _referral_link
    container = SimpleNamespace(bot=SimpleNamespace(
        get_me=AsyncMock(return_value=SimpleNamespace(username='sensei_bot'))))
    monkeypatch.delenv('DOJO_DIRECT_REFERRALS', raising=False)
    assert await _referral_link(container, 7) == 'https://t.me/sensei_bot?start=ref_7'
    monkeypatch.setenv('DOJO_DIRECT_REFERRALS', 'true')
    assert await _referral_link(container, 7) == 'https://t.me/sensei_bot?startapp=ref_7'


@pytest.mark.asyncio
async def test_signed_direct_referral_binds_only_new_player():
    registration = AsyncMock(side_effect=[{'created': True}, {'created': False}])
    bind = AsyncMock(return_value=(True, 'ok'))
    state = AsyncMock(return_value={'phase': 'ready'})
    container = SimpleNamespace(
        settings=SimpleNamespace(bot_token='test-token', maintenance_mode=False),
        dojo_miner_service=SimpleNamespace(state=state),
        user_service=SimpleNamespace(get_or_create=registration),
        referral_service=SimpleNamespace(process_referral=bind))
    app = web.Application()
    setup_dojo(app, container)
    async with TestClient(TestServer(app)) as client:
        auth = signed(now=int(time.time()), start_param='ref_42')
        for _ in range(2):
            assert (await client.post('/miniapp/dojo/api/state', json={'initData': auth})).status == 200
        bind.assert_awaited_once_with(7, 'ref_42')
        forged = signed(now=int(time.time())) + '&start_param=ref_99'
        assert (await client.post('/miniapp/dojo/api/state', json={'initData': forged})).status == 401
        bind.assert_awaited_once()


@pytest.mark.asyncio
async def test_daily_and_chest_interface_describes_prizes_without_percentages():
    app = web.Application()
    setup_dojo(app)
    async with TestClient(TestServer(app)) as client:
        html = await (await client.get('/miniapp/dojo')).text()
        js = await (await client.get('/miniapp/dojo/miner.js')).text()
    daily = html.split('<div id="daily-sheet"', 1)[1].split('<div id="roadmap-sheet"', 1)[0]
    assert 'id="daily-calendar"' in daily and 'id="daily-milestone"' in daily
    assert 'id="chest-result"' in daily and 'Виртуальный GRAM не является реальным активом' in daily
    assert 'Вероятности наград различаются' in daily and '%' not in daily
    assert 'id="chest-spin"' in daily and 'ВЫВОД ОТ 3 GRAM · НЕДОСТУПЕН' in daily
    assert 'day <= Math.min(weekStart + 6, 90)' in js
    assert 'Твоя награда:' in js
    assert 'class="chest-pointer"' in daily and 'class="chest-art"' in daily
    assert 'Лента — анимация, результат определяет сервер.' in daily
    assert 'track.children[22]' in js and 'target.offsetWidth / 2' in js
    assert 'prefers-reduced-motion: reduce' in js
    assert js.index('await animateChest(data.prize)') < js.index('sessionStorage.removeItem(key)')


@pytest.mark.asyncio
async def test_sensei_font_and_compact_chest_assets():
    app = web.Application()
    setup_dojo(app)
    async with TestClient(TestServer(app)) as client:
        for weight in (400, 700):
            response = await client.get(f'/miniapp/dojo/assets/sensei-style-{weight}.woff2')
            assert response.status == 200
            assert (await response.read()).startswith(b'wOF2')
            assert "font-src 'self'" in response.headers['Content-Security-Policy']
        html = await (await client.get('/miniapp/dojo')).text()
        css = await (await client.get('/miniapp/dojo/style.css')).text()
        js = await (await client.get('/miniapp/dojo/miner.js')).text()
    assert 'rail-path-dot' in html and 'id="chest-open"' in html
    assert '@font-face' in css and 'font-family: "Sensei Style"' in css
    assert 'sensei-border-dot' in css and 'sensei-tile-pulse' in css
    assert '#chest-sheet .daily-card' in css and 'overflow: hidden' in css
    assert 'class="chest-prizes"' in html
    for reward in ('0.01', '0.02', '0.03'):
        assert reward in html and reward in js
    assert 'track.children[22]' in js


@pytest.mark.asyncio
async def test_magic_trail_is_visual_only_bounded_and_respects_reduced_motion():
    app = web.Application()
    setup_dojo(app)
    async with TestClient(TestServer(app)) as client:
        html = await (await client.get('/miniapp/dojo')).text()
        js = await (await client.get('/miniapp/dojo/miner.js')).text()
        css = await (await client.get('/miniapp/dojo/style.css')).text()
    assert 'id="magic-trail"' in html and 'aria-hidden="true"' in html
    assert 'function setupMagicTrail()' in js
    assert 'MAX_POINTS = 64' in js and 'MAX_SPARKS = 90' in js
    assert 'pointercancel' in js and 'lostpointercapture' in js
    assert 'motionQuery?.matches' in js and 'document.hidden' in js
    assert 'phase-mining' in js and 'activeTab === "mining"' in js
    assert 'touch-action: none' in css and 'pointer-events: none' in css
    assert '.magic-trail { display: none; }' in css


@pytest.mark.asyncio
async def test_bonus_menu_and_placeholder_rewards():
    app = web.Application()
    setup_dojo(app)
    async with TestClient(TestServer(app)) as client:
        html = await (await client.get('/miniapp/dojo')).text()
        js = await (await client.get('/miniapp/dojo/miner.js')).text()
    main = html.split('<div class="utility-rail main-utilities">', 1)[1].split('<div class="stage">', 1)[0]
    bonus = html.split('<div id="bonus-sheet"', 1)[1].split('<div id="daily-sheet"', 1)[0]
    assert 'id="bonus-open"' in main and 'id="burn"' in main
    for identifier in ('daily-open', 'chest-open', 'roadmap'):
        assert f'id="{identifier}"' in bonus and f'id="{identifier}"' not in main
    for item in ('1', '3'):
        assert f'{{kind: "GRAM", value: "{item}"}}' in js
    assert '{kind: "PLACEHOLDER", value: "NFT"}' in js
    assert 'НЕ ВЫПАДАЕТ' not in js and 'НЕ ВЫПАДАЕТ' not in html
    assert 'kind === "GRAM" ? " is-gram"' in js
    assert 'kind === "GRAM" ? "GRAM" : kind === "CHEST"' in js
    assert '<small>GRAM</small>' in html
    assert 'const kind = chosen ? (isGram ? "GRAM" : isChest ? "CHEST" : "COIN")' in js
    assert 'closeBonus();' in js and 'aria-expanded' in js
