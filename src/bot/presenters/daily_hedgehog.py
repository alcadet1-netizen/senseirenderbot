"""Ordinary photo reward in chat; optional private Telegram Mini App."""
import hashlib
import os
import time
from urllib.parse import urlsplit

from aiogram.types import FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from src.core.exceptions import DailyAlreadyClaimedError
from src.services.hedgehog_service import GameError
from src.bot.widget_diagnostics import WIDGET_TRANSPORT_ERRORS, describe_failure


def picture(container, token):
    files = sorted(p for p in (container.settings.BASE_DIR / 'src/infra/storage/ega').glob('*')
                   if p.is_file() and p.suffix.lower() in {'.jpg', '.jpeg', '.png'})
    if not files:
        raise GameError('Картинки ежа временно недоступны. Попробуйте позже.')
    return FSInputFile(files[int(hashlib.sha256(token.encode()).hexdigest()[:8], 16) % len(files)])


async def send_daily_hedgehog(message, user, container):
    try:
        await container.user_service.get_or_create(
            user_id=user.id, username=user.username, first_name=user.first_name or '',
            last_name=user.last_name, is_bot=user.is_bot)
        # Resolve everything fallible we can before awarding the daily reward.
        photo = picture(container, str(user.id))
        me = await message.bot.me()
        result, session = await container.daily_pet_service.claim(user.id)
        link = f'https://t.me/{me.username}?start=pet_{session["token"]}'
        caption = (f'🦔 {user.first_name or "Друг"}, вы погладили ежа!\n'
                   f"Ежедневная награда: +{result['total_xp']} XP · +{result['total_coins']} монет.\n"
                   f"Серия: {result['streak']} дн. · Бонус серии: +{result['bonus_xp']} XP / +{result['bonus_coins']} монет.\n\n"
                   'Дополнительно: успейте перейти в личку и гладить ежа за 10 секунд! '
                   'Каждый принятый тап — ещё +10% от этой суммы монет. '
                   'Не успели — основная награда уже ваша.')
        markup = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text='🦔 В личку: погладить за 10 секунд', url=link)]])
        # Start before the send attempt, not on /start or on the first pet.
        # Retrying delivery can never renew this deadline.
        active = await container.daily_pet_service.activate(session['token'], user.id, time.time())
        if time.time() >= active['deadline']:
            caption = caption.split('\n\nДополнительно:', 1)[0] + '\n\n10 секунд дополнительных поглаживаний уже истекли.'
            markup = None
        await message.answer_photo(photo, caption=caption, reply_markup=markup, parse_mode=None)
        await container.daily_pet_service.mark_delivered(session['token'], user.id)
    except DailyAlreadyClaimedError as exc:
        await message.answer(f'🦔 Сегодня награда уже получена. Следующая: {exc.next_claim_time}', parse_mode=None)
    except GameError as exc:
        await message.answer(str(exc), parse_mode=None)


async def open_pet(message, user, container, token):
    if message.chat.type != 'private' or message.chat.id != user.id:
        await message.answer('Поглаживания доступны только в личном чате с ботом.', parse_mode=None)
        return
    try:
        session = await container.daily_pet_service.owned(token, user.id)
        if session['state'] == 'pending':
            raise GameError('Сначала получите обычное уведомление ежа в чате.')
        base = (getattr(container.settings, 'mini_app_url', '') or os.environ.get('RENDER_EXTERNAL_URL', '')).strip()
        parsed = urlsplit(base)
        if parsed.scheme != 'https' or not parsed.netloc or parsed.username or parsed.password:
            raise GameError('Для личной игры нужен HTTPS адрес MINI_APP_URL или RENDER_EXTERNAL_URL. Основная награда уже ваша.')
        url = f'https://{parsed.netloc}/miniapp/daily-pet#session={token}'
        markup = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text='🦔 Открыть игру с ёжиком', web_app=WebAppInfo(url=url))]])
        await message.answer('🦔 Коснись ёжика в игре! На переход и поглаживания — общие 10 секунд. '
                             'Таймер уже идёт, открытие не продлевает его. '
                             'Основная награда сохранена; каждый принятый тап добавляет 10% монет.',
                             reply_markup=markup, parse_mode=None)
    except GameError as exc:
        await message.answer(str(exc), parse_mode=None)
    except WIDGET_TRANSPORT_ERRORS as exc:
        failure = describe_failure(exc, message.bot)
        await message.answer('Не удалось открыть личного ежа. Основная награда уже ваша. '
                             f'Диагностика: {failure.category} / {failure.reference}', parse_mode=None)
    except (OSError, ValueError):
        await message.answer('Не удалось подготовить личного ежа. Основная награда уже начислена.', parse_mode=None)
