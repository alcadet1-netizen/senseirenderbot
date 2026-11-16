"""Запуск восьмичасового майнера SenseiCoin."""
import os
from urllib.parse import urlsplit

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from src.services.dojo_miner_service import CYCLE_SECONDS, MINING_REWARD

router = Router(name='dojo')


def dojo_url(settings):
    explicit = settings.dojo_app_url.strip()
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
        await message.answer('🥋 Открой личку бота и отправь /dojo — майнер скучает!', parse_mode=None)
        return
    url = dojo_url(container.settings)
    if not url:
        await message.answer('Майнер ещё не опубликован. Администратору нужно настроить DOJO_APP_URL или RENDER_EXTERNAL_URL.', parse_mode=None)
        return
    hours = CYCLE_SECONDS // 3600
    await message.answer(
        '🥋 Додзё: Майнер SenseiCoin\n\n'
        f'Раз в {hours} часов пни Пашу Дурова — и запустится майнинг из SenseiBank. '
        f'Через {hours} часов вернись и забери {MINING_REWARD} SenseiCoin.\n\n'
        'Пока майнинг идёт, пнуть снова нельзя. Следующий цикл открывается сразу после сбора. '
        'Монеты начисляются только внутри Telegram и только с сервера.',
        parse_mode=None, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text='👟 Пнуть Пашу', web_app=WebAppInfo(url=url))]]))
