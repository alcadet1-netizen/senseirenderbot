"""Launch solo campaign and authenticated friend matches; no economy operations."""
import os
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

router = Router(name='dojo')


def dojo_url(settings):
    """An explicit full URL wins; Render supplies the default public origin."""
    explicit = getattr(settings, 'dojo_app_url', '').strip()
    origin = os.environ.get('RENDER_EXTERNAL_URL', '').strip().rstrip('/')
    url = explicit or (origin + '/miniapp/dojo' if origin else '')
    try:
        parts = urlsplit(url)
        if (parts.scheme != 'https' or not parts.hostname or parts.username
                or parts.password or parts.fragment):
            return None
        _ = parts.port
    except ValueError:
        return None
    return url


@router.message(Command('dojo'))
async def cmd_dojo(message, container):
    if message.chat.type != 'private':
        await message.answer('Открой личный чат с ботом и отправь /dojo — там кнопка игры.', parse_mode=None)
        return
    url = dojo_url(container.settings)
    if not url:
        await message.answer(
            'Игра ещё не опубликована: администратору нужно настроить HTTPS-адрес '
            'DOJO_APP_URL или RENDER_EXTERNAL_URL и выполнить деплой.', parse_mode=None)
        return
    await message.answer(
        '🥷 Сенсей: Стенка на Стенку\n'
        'Кампания: 30 уровней. Или пригласи друга на бой! '
        'Одиночный прогресс сохраняется на этом устройстве. '
        'Игровые монеты не связаны с балансом бота.',
        parse_mode=None,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text='🎮 Играть', web_app=WebAppInfo(url=url)),
        ]]),
    )


@router.message(CommandStart(deep_link=True), F.text.regexp(r"^/start(?:@\w+)? dojo_[A-Za-z0-9_-]{22}$"))
async def cmd_dojo_invite(message, container):
    """Only dojo deep links; ordinary /start/referrals retain their handlers."""
    if message.chat.type != 'private':
        return
    url = dojo_url(container.settings)
    if not url:
        await message.answer('Mini App ещё не опубликовано. Попроси администратора проверить DOJO_APP_URL.', parse_mode=None)
        return
    token = message.text.split(maxsplit=1)[1][5:]
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query) if k != 'room']
    query.append(('room', token))
    target = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ''))
    await message.answer('⚔ Тебя вызвали на бой! Открой комнату. В PvP оба игрока начинают с равными ресурсами. Без ставок и наград бота.',
                         parse_mode=None, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                             InlineKeyboardButton(text='⚔ Войти в бой', web_app=WebAppInfo(url=target))]]))
