"""Запуск трёхчасового майнера SenseiCoin."""
import os
from urllib.parse import urlsplit

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from src.services.dojo_miner_service import BASE_RATE, CYCLE_SECONDS

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
    hour_word = 'час' if hours == 1 else 'часа' if 2 <= hours <= 4 else 'часов'
    await message.answer(
        '⛏ Додзё: Майнер SenseiCoin\n\n'
        f'Запусти майнинг на {hours} {hour_word}: кирка добывает от {int(BASE_RATE)} Coin/ч. '
        '100 энергии — час полной мощности, потом 10% скорости.\n\n'
        f'Telegram можно закрыть — добыча продолжится. Вернись через {hours} {hour_word}, забери награду '
        'и запускай следующий. Монеты начисляются только внутри Telegram и только с сервера.\n\n'
        'Внутри — «Задания», «Улучшения» за Stars и общая эмиссия SenseiBank.',
        parse_mode=None, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text='⛏ Начать майнинг', web_app=WebAppInfo(url=url))]]))
