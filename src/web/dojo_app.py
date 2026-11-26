"""SenseiCoin miner Mini App: one start runs a three-hour bank-funded cycle."""
import math
import asyncio
import logging
import os
import re
from urllib.parse import parse_qsl
import secrets
from pathlib import Path

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultArticle,
    InputTextMessageContent,
    LabeledPrice,
)
from aiohttp import web

from src.services.dojo_invite_tasks import InviteTasks, SLUGS as INVITE_SLUGS
from src.services.dojo_miner_service import CYCLE_HOURS
from src.services.dojo_task_service import TaskTargetTaken
from src.services.hedgehog_service import GameError
from src.services.maintenance_service import MaintenanceService
from src.web.telegram_auth import verify_init_data

ROOT = Path(__file__).parent / 'dojo'
ASSETS = {
    'index.html',
    'style.css',
    'miner.js',
    'motion.js',
    'assets/dojo-arena.jpg',
    'assets/ninja-fighter.jpg',
    'assets/dojo-temple-bg.jpg',
    'assets/ninja-sensei-1.png',
    'assets/ninja-sensei-2.png',
    'assets/sticker-hero-vs.jpg',
    'assets/duel-court.webp',
    'assets/sensei.webp',
    'assets/loading-hero.webp',
    'assets/senseicoin-wordmark.svg',
    'assets/unbounded-variable.woff2',
    'assets/golos-text-variable.woff2',
    'assets/dseg7-classic-regular.woff2',
    'assets/sensei-style-400.woff2',
    'assets/sensei-style-700.woff2',
}


def _referral_level(value) -> int:
    try:
        level = int(value)
    except (TypeError, ValueError):
        return 1
    return level if level in (1, 2, 3) else 1


def _cycle_label() -> str:
    hours = int(CYCLE_HOURS)
    word = 'час' if hours == 1 else 'часа' if 2 <= hours <= 4 else 'часов'
    return f'{hours} {word}'


REFERRAL_SHARE_BODY = (
    '🥷 Добывай SenseiCoin вместе со мной — заходи в додзё Сенсея '
    'и запускай майнинг!\n\n'
    f'⛏ {_cycle_label()} — один цикл\n'
    '💠 Награда приходит из SenseiBank\n'
    '🎁 Новичку — стартовый набор: 3 000 Coin, 1 уровень и катана 10 см'
)


async def _referral_link(container, user_id: int) -> str:
    bot = getattr(container, 'bot', None)
    if bot is None:
        return ''
    try:
        me = await asyncio.wait_for(bot.get_me(), timeout=5)
        username = getattr(me, 'username', None)
        if not username:
            return ''
        # Main Mini App must first be configured in BotFather. Preserve the
        # working bot deep link until an operator explicitly enables it.
        parameter = 'startapp' if os.getenv('DOJO_DIRECT_REFERRALS', '').lower() in ('1', 'true', 'yes') else 'start'
        return f'https://t.me/{username}?{parameter}=ref_{user_id}'
    except Exception:
        # A missing bot username must not make the whole tab unavailable.
        logging.getLogger(__name__).warning('Dojo referrals link unavailable')
        return ''


async def _prepare_referral_share(container, user_id: int) -> dict:
    """Prepare an inline message with the link and a «Майнинг» button."""
    link = await _referral_link(container, user_id)
    if not link:
        raise GameError('Ссылка приглашения пока недоступна.')
    bot = getattr(container, 'bot', None)
    save = getattr(bot, 'save_prepared_inline_message', None)
    if save is None:
        raise GameError('Поделиться временно недоступно.')
    text = f'{REFERRAL_SHARE_BODY}\n\n{link}'
    result = InlineQueryResultArticle(
        id=f'dojo-ref-{user_id}-{secrets.token_hex(4)}',
        title='Добывай SenseiCoin',
        description='Майнинг из SenseiBank · стартовый набор новичку',
        input_message_content=InputTextMessageContent(
            message_text=text, parse_mode=None),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text='⛏ Майнинг', url=link),
        ]]),
    )
    prepared = await asyncio.wait_for(
        save(user_id=user_id, result=result, allow_user_chats=True,
             allow_group_chats=True, allow_channel_chats=True),
        timeout=10,
    )
    return {
        'prepare_id': prepared.id,
        'expires_at': prepared.expiration_date,
        'link': link,
        'text': text,
    }


async def _referrals_payload(container, user_id: int, level, page=0) -> dict:
    """Reuse the /senseireferal data source so chat and Mini App never diverge."""
    level = _referral_level(level)
    if type(page) is not int or not 0 <= page <= 2**31:
        raise GameError('Неверная страница.')
    service = container.referral_service
    stats, members = await asyncio.gather(
        service.get_stats(user_id),
        service.get_level_members(user_id, level=level, limit=11, offset=10 * page),
    )

    link = await _referral_link(container, user_id)
    rank, next_rank = stats.rank, stats.next_rank
    return {
        'link': link,
        'share_body': REFERRAL_SHARE_BODY,
        'share_text': f'{REFERRAL_SHARE_BODY}\n\n{link}' if link else '',
        'earned': float(stats.total_coins_earned),
        'levels': [
            {'level': n, 'count': getattr(stats, f'level_{n}_count'),
             'active': getattr(stats, f'level_{n}_active')}
            for n in (1, 2, 3)
        ],
        'level': level,
        'page': page, 'has_next': len(members) > 10,
        'members': members[:10],
        'rank': {
            'id': rank.id_,
            'emoji': rank.emoji,
            'title': rank.title,
            'progress': round(stats.progress_to_next, 1),
            'next': None if next_rank is None else {
                'emoji': next_rank.emoji,
                'title': next_rank.title,
                'required': next_rank.required,
            },
        },
        'bonus': {
            'eligible': bool(stats.bonus_eligible),
            'paid': bool(stats.bonus_paid),
            'activity_days': int(stats.activity_days),
            'paid_upgrade': bool(stats.paid_upgrade),
        },
    }


def setup_dojo(app, container=None):
    headers = {
        'Cache-Control': 'no-store',
        'X-Content-Type-Options': 'nosniff',
        'Referrer-Policy': 'no-referrer',
    }

    async def page(request):
        name = request.match_info.get('asset', 'index.html')
        if request.path.startswith('/miniapp/dojo/assets/'):
            name = 'assets/' + name
        if name not in ASSETS:
            raise web.HTTPNotFound()
        response = web.FileResponse(ROOT / name, headers=headers)
        if name.endswith('.webp'):
            response.headers['Content-Type'] = 'image/webp'
        elif name.endswith(('.jpg', '.jpeg')):
            response.headers['Content-Type'] = 'image/jpeg'
        elif name.endswith('.png'):
            response.headers['Content-Type'] = 'image/png'
        response.headers['Content-Security-Policy'] = (
            "default-src 'none'; script-src 'self' https://telegram.org; style-src 'self'; "
            "img-src 'self' data:; font-src 'self'; connect-src 'self'; base-uri 'none'; "
            "form-action 'none'; frame-ancestors 'self' https://web.telegram.org https://*.telegram.org"
        )
        return response

    async def api(request):
        if container is None:
            return web.json_response(
                {'error': 'Майнер недоступен.'}, status=503, headers=headers)
        try:
            payload = await request.json()
            if not isinstance(payload, dict):
                raise ValueError()
            user = verify_init_data(payload.get('initData'), container.settings.bot_token)
        except (ValueError, TypeError, KeyError):
            return web.json_response(
                {'error': 'Откройте майнер внутри Telegram.'}, status=401, headers=headers)
        if container.settings.maintenance_mode or MaintenanceService.is_enabled():
            return web.json_response(
                {'error': 'Сенсей на техобслуживании. Попробуйте позже.'},
                status=503, headers=headers)
        action = request.match_info['action']
        is_admin = user['id'] in getattr(container.settings, 'admin_ids', ())
        if action.startswith('admin_') and not is_admin:
            return web.json_response({'error': 'Доступ только для администраторов.'}, status=403, headers=headers)
        try:
            service = container.dojo_miner_service
            if action.startswith('vs_'):
                from src.services.dojo_duel import arena, publish, chat_choices, open_invitation
                uid = user['id']
                if action in ('vs_invite', 'vs_accept'):
                    param = dict(parse_qsl(payload['initData'])).get('start_param', '')
                    match = re.fullmatch(r'vs_([1-9][0-9]{0,15})_([0-9a-f]{24})', param)
                    if not match:
                        raise GameError('Открой приглашение из Telegram.')
                    result = await open_invitation(container, uid, int(match[1]), match[2], accept=action == 'vs_accept')
                elif action == 'vs_private_share':
                    from src.services.dojo_duel import prepare_private_share
                    result = await prepare_private_share(container, uid, user.get('first_name') or 'Игрок', payload.get('bet'))
                elif action == 'vs_share_result':
                    from src.services.dojo_duel import finish_private_share
                    result = await finish_private_share(container, uid, payload.get('token'), payload.get('sent'))
                elif action == 'vs_chats':
                    result = await chat_choices(container, uid)
                elif action == 'vs_rooms':
                    # Комната никому не адресована: её видит любой игрок и
                    # может подключиться, когда удобно.
                    result = await container.dojo_rooms.list_open(uid)
                elif action == 'vs_room_create':
                    result = await container.dojo_rooms.create(
                        uid, user.get('first_name') or 'Сэнсэй', payload.get('bet'))
                    result['rooms'] = (await container.dojo_rooms.list_open(uid))['rooms']
                elif action == 'vs_room_join':
                    result = await container.dojo_rooms.join(uid, payload.get('token'))
                elif action == 'vs_room_close':
                    result = await container.dojo_rooms.close(uid, payload.get('token'))
                elif action == 'vs_publish':
                    result = await publish(container, uid, user.get('first_name') or 'Игрок', payload.get('bet'), payload.get('chat'), payload.get('rematch'), payload.get('recipient'))
                else:
                    if action == 'vs_commit':
                        if type(payload.get('id')) is not int or type(payload.get('round')) is not int:
                            raise GameError('Неверный раунд.')
                        msg = await container.duel_service.commit_dojo_move(payload['id'], uid, payload['round'], payload.get('attack'), payload.get('dodge'))
                        if msg != 'Принято.':
                            raise GameError(msg)
                    elif action == 'vs_move':
                        move = payload.get('move')
                        if (move not in ('hit_l', 'hit_r', 'dodge_l', 'dodge_r') or
                                type(payload.get('id')) is not int or type(payload.get('round')) is not int):
                            raise GameError('Некорректный ход.')
                        msg = await container.duel_service.process_move(payload['id'], uid, move, expected_round=payload['round'])
                        if msg != 'Принято.':
                            raise GameError(msg)
                    result = await arena(container, uid)
            elif action == 'entry':
                # Only use start_param from initData after signature verification.
                # Existing users without a referrer may bind; already-linked
                # users are never reassigned by the server-side transaction.
                fields = dict(parse_qsl(payload['initData'], keep_blank_values=True))
                referral = fields.get('start_param', '')
                from src.services.referral_service import parse_referrer_code
                if parse_referrer_code(referral) is not None:
                    await container.user_service.get_or_create(
                        user_id=user['id'], username=user.get('username'),
                        first_name=user.get('first_name', ''), last_name=user.get('last_name'),
                        is_bot=user.get('is_bot', False))
                    await container.referral_service.process_referral(user['id'], referral)
                result = await service.state(user['id'])
            elif action == 'state':
                result = await service.state(user['id'])
            elif action == 'profile':
                # Identity is derived only from verified Telegram initData.
                profile = await container.user_service.get_profile(user['id'])
                if not profile or profile.get('is_banned'):
                    raise GameError('Профиль недоступен.')
                fields = ('first_name', 'last_name', 'username', 'level', 'level_name',
                          'xp', 'xp_next', 'coins', 'tickets', 'messages', 'streak',
                          'has_katana', 'katana_length', 'achievements_count',
                          'wins', 'losses', 'role')
                result = {'profile': {key: profile.get(key) for key in fields}}
                if profile.get('has_katana'):
                    from src.widgets.katana_models import model_caption
                    result['profile']['katana_caption'] = model_caption(profile.get('katana_length') or 0)

            elif action == 'start':
                result = await service.start(user['id'])
            elif action == 'circle':
                request_id = payload.get('request_id')
                cycle = payload.get('cycle')
                if not isinstance(request_id, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{8,64}', request_id) or type(cycle) not in (int, float) or not 0 < cycle < 10**12 or not math.isfinite(cycle):
                    raise GameError('Неверный запрос пополнения.')
                outcome = await service.add_circle_energy(user['id'], cycle, request_id)
                result = await service.state(user['id'])
                result['circle'] = outcome
            elif action in ('daily', 'daily_claim', 'chest'):
                from src.services.dojo_daily_service import DojoDailyService
                daily = DojoDailyService(container.mongo_client)
                if action == 'daily_claim':
                    result = {'claim': await daily.claim(user['id'])}
                elif action == 'chest':
                    request_id = payload.get('request_id')
                    if not isinstance(request_id, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{8,64}', request_id):
                        raise GameError('Неверный идентификатор открытия.')
                    result = {'prize': await daily.open_chest(user['id'], request_id)}
                else:
                    result = {}
                result['daily'] = await daily.state(user['id'])
            elif action == 'admin_tasks':
                result = {'tasks': await container.dojo_task_service.all_tasks()}
            elif action == 'admin_save':
                result = {'task': await container.dojo_task_service.save_admin_task(payload.get('task'), user['id'])}
            elif action == 'admin_toggle':
                await container.dojo_task_service.set_admin_task_active(payload.get('slug'), payload.get('active'), user['id'])
                result = {'success': True}
            elif action == 'admin_grant':
                from src.services.dojo_daily_service import DojoDailyService
                request_id, username, amount = payload.get('request_id'), payload.get('username'), payload.get('amount')
                if not isinstance(request_id, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{8,64}', request_id):
                    raise GameError('Неверный идентификатор выдачи.')
                if not isinstance(username, str):
                    raise GameError('Укажи @username игрока.')
                receipt = await DojoDailyService(container.mongo_client).grant_admin_chests(
                    username.strip().lstrip('@'), amount, user['id'], f'web:{user["id"]}:{request_id}')
                result = {'username': receipt['username'], 'amount': receipt['amount']}
            elif action == 'tasks':
                from src.services.dojo_profile_tasks import DojoProfileTasks
                tasks = await container.dojo_task_service.list_tasks(user['id'])
                tasks.extend(await DojoProfileTasks(container).list_tasks(user['id']))
                tasks.append(await InviteTasks(container.mongo_client).current(user['id']))
                result = {'tasks': tasks}
            elif action == 'task':
                from src.services.dojo_profile_tasks import DojoProfileTasks, TASK_IDS
                slug = payload.get('slug')
                if isinstance(slug, str) and slug in TASK_IDS:
                    claim = await DojoProfileTasks(container).claim(user['id'], slug)
                elif isinstance(slug, str) and slug in INVITE_SLUGS:
                    claim = await InviteTasks(container.mongo_client).claim(user['id'], slug)
                else:
                    claim = await container.dojo_task_service.claim(user['id'], slug)
                result = await service.state(user['id'])
                result['balance'] = claim.get('new_coins', result.get('balance', 0))
                result['task'] = claim['task']
                result['reward_coins'] = claim['reward_coins']
                result['energy_bonus'] = claim['energy_bonus']
                result['reward_gram_hundredths'] = claim.get('reward_gram_hundredths', 0)
                result['reward_chests'] = claim.get('reward_chests', 0)
                stats = getattr(container, 'stats_service', None)
                invalidate = getattr(stats, 'invalidate', None)
                if invalidate is not None:
                    invalidate()
            elif action == 'upgrades':
                result = {'upgrades': await container.dojo_upgrade_service.snapshot(
                    user['id'])}
            elif action == 'buy':
                order = await container.dojo_upgrade_service.prepare(
                    user['id'], payload.get('kind'))
                if container.bot is None:
                    raise GameError('Оплата временно недоступна.')
                try:
                    link = await asyncio.wait_for(
                        container.bot.create_invoice_link(
                            title=order['title'],
                            description=order['description'],
                            payload=order['payload'],
                            currency='XTR',
                            provider_token='',
                            prices=[LabeledPrice(
                                label=order['title'], amount=order['stars'])],
                        ),
                        timeout=10,
                    )
                except Exception:
                    logging.getLogger(__name__).error(
                        'Dojo upgrade invoice failed kind=%s', payload.get('kind'))
                    raise GameError('Не удалось создать счёт. Попробуй позже.')
                if not link:
                    raise GameError('Не удалось создать счёт. Попробуй позже.')
                result = {'invoice_url': link, 'kind': order['kind'],
                          'stars': order['stars']}
            elif action == 'bank':
                result = await container.stats_service.get_bank_summary()
            elif action == 'burn':
                request_id = payload.get('request_id')
                if request_id:
                    burn = await container.burn_service.burn(
                        user['id'], payload.get('amount'), request_id)
                else:
                    burn = await container.burn_service.burn(
                        user['id'], payload.get('amount'))
                result = await service.state(user['id'])
                result['balance'] = burn['balance']
                result['burn'] = burn
                stats = getattr(container, 'stats_service', None)
                invalidate = getattr(stats, 'invalidate', None)
                if invalidate is not None:
                    invalidate()
            elif action == 'referrals':
                result = await _referrals_payload(container, user['id'],
                                                   payload.get('level', 1), payload.get('page', 0))
            elif action == 'ref_claim':
                result = await service.claim_referral_mining(user['id'], payload.get('token'))
            elif action == 'share':
                result = await _prepare_referral_share(container, user['id'])
            else:
                result = await service.collect(user['id'])
                # The bank/emission tab must not show a snapshot older than the
                # collect that just moved coins from the bank to this player.
                stats = getattr(container, 'stats_service', None)
                invalidate = getattr(stats, 'invalidate', None)
                if invalidate is not None:
                    invalidate()
            if isinstance(result, dict) and 'phase' in result:
                result['is_admin'] = is_admin
            return web.json_response(result, headers=headers)
        except GameError as exc:
            # Отказ виден игроку, но раньше не попадал в лог: по записи
            # «admin_save 409» нельзя было понять, что именно не так.
            # Пишем только текст ошибки — initData и токены не трогаем.
            logger = logging.getLogger(__name__)
            logger.info('Dojo action rejected: action=%s reason=%s', action, exc)
            body = {'error': str(exc)}
            if isinstance(exc, TaskTargetTaken):
                # Мини-апп сам откроет существующее задание на редактирование.
                body.update(code='task_exists', slug=exc.slug, title=exc.title)
            return web.json_response(body, status=409, headers=headers)
        except Exception:
            # Never log initData, Telegram tokens or raw payloads.
            logging.getLogger(__name__).exception('Dojo miner API failed: action=%s', action)
            return web.json_response(
                {'error': 'Майнер не ответил. Попробуйте ещё раз.'}, status=503,
                headers=headers)

    app.router.add_get('/miniapp/dojo', page)
    app.router.add_get('/miniapp/dojo/', page)
    app.router.add_get(
        '/miniapp/dojo/{asset:style\\.css|miner\\.js|motion\\.js}', page)
    app.router.add_get(
        '/miniapp/dojo/assets/{asset:dojo-arena\\.jpg|ninja-fighter\\.jpg|dojo-temple-bg\\.jpg|ninja-sensei-1\\.png|ninja-sensei-2\\.png|sticker-hero-vs\\.jpg|duel-court\\.webp|sensei\\.webp|loading-hero\\.webp|senseicoin-wordmark\\.svg|unbounded-variable\\.woff2|golos-text-variable\\.woff2|dseg7-classic-regular\\.woff2|sensei-style-(?:400|700)\\.woff2}', page)
    app.router.add_post(
        '/miniapp/dojo/api/{action:admin_tasks|admin_save|admin_toggle|admin_grant|entry|state|profile|start|circle|collect|tasks|task|upgrades|buy|bank|burn|referrals|vs_private_share|vs_share_result|vs_chats|vs_invite|vs_accept|vs_state|vs_publish|vs_commit|vs_move|vs_rooms|vs_room_create|vs_room_join|vs_room_close|ref_claim|share|daily|daily_claim|chest}',
        api)
