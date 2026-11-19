"""Daily hedgehog reward delivered as a photo in chat."""
import time

from aiogram.types import InputMediaPhoto, BufferedInputFile

from src.core.exceptions import DailyAlreadyClaimedError
from src.services.hedgehog_service import GameError


async def _get_random_image_from_gridfs(container) -> bytes:
    """Get a random hedgehog image from GridFS."""
    gridfs = container.hedgehog_gridfs
    file_info = await gridfs.get_random_image()
    if not file_info:
        raise GameError('Картинки ежа временно недоступны. Попробуйте позже.')
    content = await gridfs.get_image_by_id(file_info['id'])
    if not content:
        raise GameError('Картинки ежа временно недоступны. Попробуйте позже.')
    return content


async def _get_image_by_name_from_gridfs(container, image_name: str) -> bytes:
    """Get a specific hedgehog image by name from GridFS."""
    gridfs = container.hedgehog_gridfs
    content = await gridfs.get_image(image_name)
    if not content:
        raise GameError('Сохранённая картинка ежа недоступна. Обратитесь в /paysupport; не платите повторно.')
    return content


async def picture(container, token, image_name=None):
    """Return a BufferedInputFile with hedgehog image from GridFS."""
    if image_name is not None:
        content = await _get_image_by_name_from_gridfs(container, image_name)
    else:
        content = await _get_random_image_from_gridfs(container)
    return BufferedInputFile(content, filename="hedgehog.jpg")


async def send_daily_hedgehog(message, user, container):
    try:
        await container.user_service.get_or_create(
            user_id=user.id, username=user.username, first_name=user.first_name or '',
            last_name=user.last_name, is_bot=user.is_bot)
        # Resolve everything fallible we can before awarding the daily reward.
        await picture(container, str(user.id))
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
                             reply_markup=repeat_keyboard(user.id), parse_mode=None)
    except GameError as exc:
        await message.answer(str(exc), parse_mode=None)


async def open_pet(message, user, container, token):
    # Existing deep links can still be opened after deployment. They must not
    # create another payout or open the retired interactive widget.
    await message.answer('Поглаживания больше недоступны. Ежедневная награда показывается с картинкой в чате.', parse_mode=None)


async def send_reward_notice(message, user, container, result, session, *, notice=None):
    caption = (f'🦔 {user.first_name or "Друг"}, награда ваша!\n'
               f"+{result['total_xp']} XP · +{result['total_coins']} монет\n"
               f"🔥 Серия: {result['streak']} дн.")
    if session.get('paid_order'):
        from src.texts.payment_thanks import payment_thanks
        caption += '\n' + payment_thanks(session['token'])
    # Retain the existing session lifecycle for payment/recovery, but expire
    # the now-retired touch window immediately for newly delivered notices.
    await container.daily_pet_service.activate(
        session['token'], user.id, time.time() - session.get('duration', 10))
    photo = await picture(container, str(user.id), session.get("image_name"))
    # Both free and Stars delivery pass here. Claim in Mongo, not a process lock:
    # another update/process may already be sending this session's notice.
    if not await container.daily_pet_service.reserve_notice(session['token'], user.id):
        return
    if notice:
        await message.bot.edit_message_media(
            chat_id=notice['chat_id'], message_id=notice['message_id'],
            media=InputMediaPhoto(media=photo, caption=caption, parse_mode=None), reply_markup=None)
    else:
        await message.answer_photo(photo, caption=caption, reply_markup=None, parse_mode=None)
    await container.daily_pet_service.mark_delivered(session['token'], user.id)
