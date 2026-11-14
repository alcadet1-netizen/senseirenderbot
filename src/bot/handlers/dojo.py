"""Launch the local-only dojo prototype; no economy or reward operations."""
import os
from urllib.parse import urlsplit

from aiogram import Router
from aiogram.filters import Command
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
        '🥷 Ёж-Сенсей: Стенка на Стенку\n'
        'Тестовая игра. Прогресс сохраняется на этом устройстве. '
        'Игровые монеты не связаны с балансом бота.',
        parse_mode=None,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text='🎮 Играть', web_app=WebAppInfo(url=url)),
        ]]),
    )
