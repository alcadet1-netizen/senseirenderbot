"""Launch the daily Mini App; groups use a private-chat deep link."""
from urllib.parse import urlsplit

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from src.core.exceptions import DailyAlreadyClaimedError
from src.services.hedgehog_service import GameError


def app_base(settings) -> str:
    import os
    base = (settings.mini_app_url or os.environ.get('RENDER_EXTERNAL_URL', '')).rstrip('/')
    parsed = urlsplit(base)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or parsed.path not in ('', '/')):
        raise GameError('Мини-игра ещё не настроена: нужен публичный HTTPS-адрес MINI_APP_URL на сервере.')
    return base


async def launch_hedgehog(message, user, container, token=None):
    try:
        base = app_base(container.settings)
        await container.user_service.get_or_create(
            user_id=user.id, username=user.username, first_name=user.first_name or '',
            last_name=user.last_name, is_bot=user.is_bot,
        )
        if token:
            game = await container.hedgehog_service.owned(token, user.id)
        else:
            game = await container.hedgehog_service.issue(user.id)
        if message.chat.type == 'private':
            button = InlineKeyboardButton(text='🦔 Погладить ежа · 12 секунд', web_app=WebAppInfo(
                url=f'{base}/miniapp/hedgehog?session={game["token"]}',
            ))
        else:
            bot_user = await message.bot.get_me()
            button = InlineKeyboardButton(text='🦔 Открыть игру', url=(
                f'https://t.me/{bot_user.username}?start=hedgehog_{game["token"]}'
            ))
        await message.answer(
            '🦔 Ёж ждёт ласки!\n\n12 секунд на поглаживания. Шанс успеха — 95%.\n'
            'В 5% случаев ёж вредничает: серия сбрасывается, но монеты и XP не теряются. '
            'Одна попытка в день, новый день — в 00:00 UTC.',
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[button]]), parse_mode=None,
        )
    except DailyAlreadyClaimedError as exc:
        await message.answer(f'🦔 Сегодня вы уже встречались с ежом. Следующая попытка: {exc.next_claim_time}', parse_mode=None)
    except GameError as exc:
        await message.answer(str(exc), parse_mode=None)
