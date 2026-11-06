"""Bot API 10.4 widget bridge, as specified by widget-sandbox v0.6.0.

No invented Bot API transport: these methods are documented in upstream
scripts/conformance/test-bot.ts and docs/tgw-format.md, currently beta/test.
Unknown Update fields must be intercepted before aiogram dispatches them.
"""
import json
import logging
import re
from typing import Any

from aiogram import BaseMiddleware
from aiogram.methods.base import TelegramMethod

from src.core.exceptions import DailyAlreadyClaimedError
from src.services.hedgehog_service import GameError
from src.services.maintenance_service import MaintenanceService

logger = logging.getLogger(__name__)


class SendWidget(TelegramMethod[dict[str, Any]]):
    __api_method__ = 'sendWidget'
    __returning__ = dict[str, Any]
    chat_id: int
    html: str
    width: int = 340
    height: int = 0
    allow_queries: bool = True
    is_shared: bool = False


class AnswerWidgetQuery(TelegramMethod[bool]):
    __api_method__ = 'answerWidgetQuery'
    __returning__ = bool
    widget_query_id: str
    data: str


def compact_result(response):
    if response.get('state') != 'done':
        return response
    r = response['result']
    return {'state': 'done', 'result': {k: r.get(k, 0) for k in (
        'success', 'total_xp', 'total_coins', 'streak', 'message', 'tap_bonus_coins', 'tap_count')}}


class HedgehogWidgetMiddleware(BaseMiddleware):
    def __init__(self, container):
        self.container = container

    async def __call__(self, handler, event, data):
        # aiogram keeps future Bot API fields as Pydantic extras. Do not let its
        # Update.event_type reject these before our bridge has handled them.
        fields = event.model_dump(mode='python', by_alias=True, exclude_none=True)
        query = fields.get('widget_query')
        shared = fields.get('shared_widget_query')
        if query is None and shared is None:
            return await handler(event, data)
        query = query if query is not None else shared
        if not isinstance(query, dict) or not isinstance(query.get('id'), str):
            return None
        response = {'error': 'Вызови /senseidaily для своей игры.'}
        try:
            if shared is not None or not isinstance(query.get('chat'), dict) or not query.get('message_id'):
                raise GameError('Пересланная игра не выдаёт наград. Вызови /senseidaily.')
            if self.container.settings.maintenance_mode or MaintenanceService.is_enabled():
                raise GameError('Сенсей на техобслуживании. Попробуй позже.')
            user_id = query.get('from', {}).get('id')
            if type(user_id) is not int or user_id <= 0:
                raise GameError('Неизвестный игрок.')
            value = query.get('data')
            if not isinstance(value, str) or len(value.encode()) > 64:
                raise GameError('Неверное действие.')
            parts = value.split(':')
            if len(parts) != 3 or parts[0] != 'hg' or not re.fullmatch(r'(?:s|f|t[0-9]{1,3})', parts[1]):
                raise GameError('Неверное действие.')
            # Sender comes exclusively from Telegram's update, never the HTML.
            service = self.container.hedgehog_service
            user = await service.users.find_one({'id': user_id})
            if not user or user.get('is_banned'):
                raise GameError('Профиль недоступен.')
            method = service.start if parts[1] == 's' else service.finish
            if parts[1].startswith('t'):
                response = compact_result(await service.tap(parts[2], user_id, int(parts[1][1:])))
            else:
                response = compact_result(await method(parts[2], user_id))
        except (GameError, DailyAlreadyClaimedError) as exc:
            response = {'error': str(exc)}
        except Exception:
            logger.exception('Native hedgehog request failed')
            response = {'error': 'Ёж потерял связь. Нажми ещё раз — награда не удвоится.'}
        encoded = json.dumps(response, ensure_ascii=False, separators=(',', ':'))
        if len(encoded.encode()) > 1024:
            encoded = '{"error":"Ответ ежа слишком большой. Попробуй позже."}'
        await data['bot'](AnswerWidgetQuery(widget_query_id=query['id'], data=encoded))
        return None


async def send_native_widget(bot, container, chat_id, html, *, allow_queries=True):
    """One explicit route for both real games and admin probes; no fallback."""
    transport = getattr(container, 'native_widget_transport', None)
    if transport is not None:
        return await transport.send_widget(chat_id, html, allow_queries=allow_queries)
    if getattr(container.settings, 'native_widget_transport', 'bot_api') == 'mtproto':
        from src.infra.mtproto.widgets import MtprotoWidgetError
        raise MtprotoWidgetError('MTPROTO_TRANSPORT_NOT_READY')
    return await bot(SendWidget(chat_id=chat_id, html=html, allow_queries=allow_queries))
