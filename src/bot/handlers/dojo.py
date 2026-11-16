"""Запуск одиночной выживалки с ограниченной наградой SenseiCoin."""
import os
from urllib.parse import urlsplit
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

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
        await message.answer('🥋 Открой личку бота и отправь /dojo — твой отряд ждёт!', parse_mode=None)
        return
    url = dojo_url(container.settings)
    if not url:
        await message.answer('Игра ещё не опубликована. Администратору нужно настроить DOJO_APP_URL или RENDER_EXTERNAL_URL.', parse_mode=None)
        return
    await message.answer(
        '🥋 Додзё: Последний рубеж\n\n'
        'Отряд стражей против пяти волн чудовищ: пауки, скелеты, големы и маги. '
        'Победи разрушителя-они и архилича, уходи от их атак, собирай бонусы и усиливай отряд в кузнице.\n\n'
        'За забег можно добыть до 14 SenseiCoin в баланс бота: только за волны, минимум 45 секунд боя и не больше 30 Coin в сутки. Фарм намеренно жестокий.',
        parse_mode=None, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text='⚔ Защитить додзё', web_app=WebAppInfo(url=url))]]))
