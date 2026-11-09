"""Safe diagnostics: API rejection is not proof of missing client support."""
import asyncio
import logging
import re
import secrets
from dataclasses import dataclass

from aiogram.exceptions import (
    TelegramAPIError, TelegramBadRequest, TelegramForbiddenError,
    TelegramNetworkError, TelegramNotFound, TelegramRetryAfter,
    TelegramServerError, TelegramUnauthorizedError,
)

from src.infra.mtproto.widgets import MtprotoWidgetError

logger = logging.getLogger(__name__)


def redact(value: str, bot=None) -> str:
    text = str(value)
    token = getattr(bot, 'token', None)
    if isinstance(token, str) and token:
        text = text.replace(token, '[REDACTED]')
    text = re.sub(r'https?://[^\s<>"\']+', '[URL REDACTED]', text)
    text = re.sub(r'\b\d{5,}:[A-Za-z0-9_-]{15,}', '[TOKEN REDACTED]', text)
    text = re.sub(r'(?i)(session[=:]\s*)[A-Za-z0-9_-]+', r'\1[REDACTED]', text)
    text = re.sub(r'[A-Za-z0-9_-]{32,}', '[REDACTED]', text)
    return ' '.join(text.split())[:700]


@dataclass(frozen=True)
class WidgetFailure:
    reference: str
    category: str
    description: str
    advice: str
    stage: str = "unknown"

    def public_text(self):
        return (f'🦔 Не удалось отправить нативного ежа. {self.advice}\n'
                f'Код диагностики: {self.category} / {self.reference}.\n'
                'Попытка не потрачена, награда не начислена. '
                'Администратор может проверить API командой /senseiwidgetcheck в личке. '
                'Mini App вместо виджета не открываю.')


def describe_failure(exc, bot=None):
    raw = getattr(exc, 'message', str(exc))
    detail = redact(raw, bot)
    lower = str(raw).lower()
    transport_category = getattr(exc, 'category', None)
    if transport_category == 'transport_runtime':
        category, advice = 'transport_runtime', 'Фоновый обработчик MTProto остановлен. Нужна проверка схемы/ошибки обновлений, а не HTML виджета.'
    elif transport_category == 'transport_closed':
        category, advice = 'transport_closed', 'MTProto-транспорт остановлен. Дождитесь завершения перезапуска бота.'
    elif transport_category == 'temporary' or lower in {'connectionerror', 'timeouterror', 'oserror'}:
        category, advice = 'temporary', 'Соединение MTProto с Telegram потеряно или не ответило вовремя. Выполнено ограниченное восстановление; повторите проверку позже.'
    elif isinstance(exc, TelegramNotFound) or ('method' in lower and ('not found' in lower or 'unknown' in lower)):
        category, advice = 'method_or_route', 'Telegram не нашёл метод или маршрут API. Нужна проверка endpoint и поддержки sendWidget.'
    elif isinstance(exc, TelegramRetryAfter):
        category, advice = 'rate_limit', 'Telegram ограничил частоту запросов. Попробуйте позже.'
    elif isinstance(exc, TelegramUnauthorizedError):
        category, advice = 'authorization', 'Telegram отклонил авторизацию бота. Администратору нужно проверить окружение.'
    elif isinstance(exc, TelegramForbiddenError) or any(s in lower for s in ('forbidden', 'not enough rights', 'chat_send_photos_forbidden')):
        category, advice = 'permissions', 'Telegram запретил отправку в этот чат. Проверьте права бота на отправку медиа.'
    elif any(s in lower for s in ('too_large', 'too large', 'html_invalid', 'html invalid', 'width', 'height')):
        category, advice = 'payload', 'Telegram отклонил содержимое или размеры виджета. Нужна проверка формата, а не переключение в beta.'
    elif 'widget_not_allowed' in lower:
        category, advice = 'widget_policy', 'Telegram отклонил этот вариант нативного виджета. Причину ограничения бота, чата или параметров нужно уточнить; транспорт не обходит серверный отказ.'
    elif 'peer_not_cached' in lower:
        category, advice = 'peer_resolution', 'Отправьте боту новое сообщение в этом чате и повторите проверку: нужен peer из MTProto.'
    elif isinstance(exc, TelegramBadRequest):
        category, advice = 'bad_request', 'Telegram отклонил параметры запроса. Это ещё не означает отсутствие поддержки виджетов.'
    elif isinstance(exc, (TelegramNetworkError, TelegramServerError)):
        category, advice = 'temporary', 'Сеть или сервер Telegram временно недоступны. Попробуйте позже.'
    else:
        category, advice = 'api_error', 'Telegram вернул ошибку API. Администратору нужна диагностика.'
    stage = getattr(exc, 'stage', None)
    if stage not in {'send_media', 'answer_inline_hedgehog', 'answer_query', 'reject_query',
                     'resolve_peer', 'reconnect_probe', 'clear_inline_hedgehog', 'forward_widget'}:
        stage = 'unknown'
    if stage == 'answer_inline_hedgehog' and category == 'widget_policy':
        advice = ('Telegram отклонил создание нативного inline-результата. '
                  'До отправки выбранного результата в группу дело не дошло; '
                  'повтор прямой отправки или включение shared_widget не устраняют этот отказ.')
    failure = WidgetFailure(secrets.token_hex(4), category, detail, advice, stage)
    # Never log the exception repr, request HTML, session token or tokenized URL.
    logger.warning('Native widget failure ref=%s category=%s type=%s stage=%s description=%s',
                   failure.reference, category, type(exc).__name__, stage, detail)
    return failure


WIDGET_TRANSPORT_ERRORS = (TelegramAPIError, TelegramNetworkError, MtprotoWidgetError)


async def widget_chat_advice(message):
    """Read permissions in the actual destination; never mutate chat rights."""
    kind = message.chat.type
    if kind == 'channel':
        return 'Канал: прямая отправка нативных виджетов в каналы сейчас не поддерживается.'
    if kind not in {'group', 'supergroup'}:
        return 'Проверка относится только к этому личному чату, не к группе.'
    try:
        async with asyncio.timeout(5):
            member = await message.bot.get_chat_member(message.chat.id, message.bot.id)
            chat = await message.bot.get_chat(message.chat.id)
    except (TelegramAPIError, TimeoutError):
        return ('Не удалось проверить права бота в этой группе. Проверьте его членство '
                'и право отправлять фото/медиа; затем /senseiwidgetcheck here в этой группе.')
    status = member.status
    if status in {'left', 'kicked'}:
        allowed = False
    elif status in {'creator', 'administrator'}:
        allowed = True
    elif status == 'restricted':
        allowed = bool(member.is_member and member.can_send_photos)
    else:
        allowed = getattr(getattr(chat, 'permissions', None), 'can_send_photos', None)
    if allowed is False:
        return ('В этой группе боту недоступна отправка фото/медиа или он не состоит в ней. '
                'Администратору группы нужно разрешить отправку фото и убедиться, что бот добавлен. '
                'После изменения прав повторите /senseidaily.')
    if allowed is True:
        return ('Право отправлять фото в этой группе есть. Это не гарантирует допуск виджетов сервером Telegram. '
                'Администратор бота может проверить именно эту группу: /senseiwidgetcheck here. '
                'Если даже minimal отклонён, оформление Ежа не причина отказа.')
    return ('Telegram не сообщил определённого разрешения на фото. Проверьте права бота; '
            'для проверки именно этой группы: /senseiwidgetcheck here.')
