"""Ordinary photo reward in chat; private native touch widget."""
import hashlib
import asyncio
import time


from aiogram.types import FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup

from src.bot.native_widgets import send_native_widget
from src.widgets.daily_pet import to_daily_pet_html
from src.widgets.limits import RENDER_SLOTS
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
        picture(container, str(user.id))
        await message.bot.me()
        paid = getattr(container, 'paid_hedgehog_service', None)
        if paid is not None:
            receipt = await paid.pending(user.id)
            if receipt:
                from src.bot.handlers.paid_hedgehog import deliver
                await deliver(message, container, receipt)
                return
        result, session = await container.daily_pet_service.claim(user.id)
        await send_reward_notice(message, user, container, result, session)
    except DailyAlreadyClaimedError:
        from src.bot.handlers.paid_hedgehog import repeat_keyboard
        await message.answer('🦔 Бесплатная Ежа сегодня уже получена.\n'
                             'Ещё попытки: 1 ⭐ → 5 ⭐ → 10 ⭐ → 20 ⭐…\n'
                             'Каждая даёт полную награду; серия растёт раз в сутки. Цены сбрасываются в 00:00 UTC.',
                             reply_markup=repeat_keyboard(), parse_mode=None)
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
        snapshot = await container.daily_pet_service.widget_action(token, user.id, 'v', '')
        async with RENDER_SLOTS:
            html = await asyncio.to_thread(to_daily_pet_html, token,
                container.settings.BASE_DIR / 'src/infra/storage/ega', snapshot)
        await send_native_widget(message.bot, container, user.id, html)
    except GameError as exc:
        await message.answer(str(exc), parse_mode=None)
    except WIDGET_TRANSPORT_ERRORS as exc:
        failure = describe_failure(exc, message.bot)
        await message.answer('Не удалось открыть личного ежа. Основная награда уже ваша. '
                             f'Диагностика: {failure.category} / {failure.reference}', parse_mode=None)
    except (OSError, ValueError):
        await message.answer('Не удалось подготовить личного ежа. Основная награда уже начислена.', parse_mode=None)


async def send_reward_notice(message, user, container, result, session):
    me = await message.bot.me()
    link = f'https://t.me/{me.username}?start=pet_{session["token"]}'
    reward_caption = (f'🦔 {user.first_name or "Друг"}, награда ваша!\n'
                      f"+{result['total_xp']} XP · +{result['total_coins']} монет\n"
                      f"🔥 Серия: {result['streak']} дн.")
    caption = (reward_caption + '\n\nВ личке: 15 сек. на переход и ласку.\n'
               'Принятый тап → +10% монет.')
    markup = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text='Погладить ёжика · 15 сек.', url=link)]])
    # Start before the send attempt, not on /start or on the first pet.
    # Retrying delivery can never renew this deadline.
    active = await container.daily_pet_service.activate(session['token'], user.id, time.time())
    if time.time() >= active['deadline']:
        caption = reward_caption + '\n\nВремя ласки вышло. До завтра ♡'
        markup = None
    photo = picture(container, str(user.id))
    # Both free and Stars delivery pass here. Claim in Mongo, not a process lock:
    # another update/process may already be sending this session's notice.
    if not await container.daily_pet_service.reserve_notice(session['token'], user.id):
        return
    await message.answer_photo(photo, caption=caption, reply_markup=markup, parse_mode=None)
    await container.daily_pet_service.mark_delivered(session['token'], user.id)
