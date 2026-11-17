"""SenseiCoin miner Mini App: one start runs a four-hour bank-funded cycle."""
import asyncio
import logging
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

from src.services.dojo_miner_service import CYCLE_HOURS
from src.services.hedgehog_service import GameError
from src.services.maintenance_service import MaintenanceService
from src.web.telegram_auth import verify_init_data

ROOT = Path(__file__).parent / 'dojo'
ASSETS = {
    'index.html',
    'style.css',
    'miner.js',
    'assets/sensei.webp',
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
        return f'https://t.me/{username}?start=ref_{user_id}' if username else ''
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


async def _referrals_payload(container, user_id: int, level) -> dict:
    """Reuse the /senseireferal data source so chat and Mini App never diverge."""
    level = _referral_level(level)
    service = container.referral_service
    stats, members = await asyncio.gather(
        service.get_stats(user_id),
        service.get_level_members(user_id, level=level, limit=10),
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
        'members': members,
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
        response.headers['Content-Security-Policy'] = (
            "default-src 'none'; script-src 'self' https://telegram.org; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; base-uri 'none'; "
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
        try:
            service = container.dojo_miner_service
            if action == 'state':
                result = await service.state(user['id'])
            elif action == 'start':
                result = await service.start(user['id'])
            elif action == 'tasks':
                tasks = await container.dojo_task_service.list_tasks(user['id'])
                result = {'tasks': tasks}
            elif action == 'task':
                claim = await container.dojo_task_service.claim(
                    user['id'], payload.get('slug'))
                result = await service.state(user['id'])
                result['balance'] = claim.get('new_coins', result.get('balance', 0))
                result['task'] = claim['task']
                result['reward_coins'] = claim['reward_coins']
                result['energy_bonus'] = claim['energy_bonus']
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
                                                   payload.get('level', 1))
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
            return web.json_response(result, headers=headers)
        except GameError as exc:
            return web.json_response({'error': str(exc)}, status=409, headers=headers)
        except Exception:
            # Never log initData, Telegram tokens or raw payloads.
            logging.getLogger(__name__).error('Dojo miner API failed: action=%s', action)
            return web.json_response(
                {'error': 'Майнер не ответил. Попробуйте ещё раз.'}, status=503,
                headers=headers)

    app.router.add_get('/miniapp/dojo', page)
    app.router.add_get('/miniapp/dojo/', page)
    app.router.add_get(
        '/miniapp/dojo/{asset:style\\.css|miner\\.js}', page)
    app.router.add_get(
        '/miniapp/dojo/assets/{asset:sensei\\.webp}', page)
    app.router.add_post(
        '/miniapp/dojo/api/{action:state|start|collect|tasks|task|upgrades|buy|bank|burn|referrals|share}',
        api)
