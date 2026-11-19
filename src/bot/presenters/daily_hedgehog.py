"""Daily hedgehog reward delivered as a photo in chat."""
import time
import logging

from aiogram.exceptions import TelegramBadRequest

from aiogram.types import InputMediaPhoto, BufferedInputFile

from src.core.exceptions import DailyAlreadyClaimedError
from src.services.hedgehog_service import GameError

logger = logging.getLogger(__name__)


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
    logger.info('Daily hedgehog requested chat=%s user=%s', message.chat.id, user.id)
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
                delivered = await deliver(message, container, receipt)
                if delivered is False:
                    await message.answer(
                        '🦔 Оплаченная награда уже сохранена. Доставка картинки ещё не '
                        'подтверждена или уже выполнена. Проверьте баланс и сообщения; '
                        'не оплачивайте повторно. Если нужна помощь — /paysupport.', parse_mode=None)
                return
        result, session = await container.daily_pet_service.claim(user.id)
        logger.info('Daily hedgehog reward receipt ready chat=%s user=%s', message.chat.id, user.id)
        delivered = await send_reward_notice(message, user, container, result, session)
        if not delivered:
            await message.answer(
                '🦔 Награда уже сохранена. Доставка картинки ещё не подтверждена '
                'или уже выполнена. Проверьте баланс и сообщения; повторного начисления нет. '
                'Если картинка не появилась, обратитесь в /paysupport.', parse_mode=None)
    except DailyAlreadyClaimedError:
        logger.info('Daily hedgehog already claimed chat=%s user=%s', message.chat.id, user.id)
        from src.bot.handlers.paid_hedgehog import repeat_keyboard
        await message.answer('🦔 Бесплатная Ежа сегодня уже получена.\n'
                             'Ещё попытки: 1 ⭐ → 5 ⭐ → 10 ⭐ → 20 ⭐…\n'
                             'Каждая даёт полную награду; серия растёт раз в сутки. Цены сбрасываются в 00:00 UTC.',
                             reply_markup=repeat_keyboard(user.id), parse_mode=None)
    except GameError as exc:
        logger.warning('Daily hedgehog unavailable chat=%s user=%s reason=%s', message.chat.id, user.id, exc)
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
        logger.warning('Hedgehog notice already reserved or delivered user=%s', user.id)
        return False
    try:
        if notice:
            await message.bot.edit_message_media(
                chat_id=notice['chat_id'], message_id=notice['message_id'],
                media=InputMediaPhoto(media=photo, caption=caption, parse_mode=None), reply_markup=None)
        else:
            await message.answer_photo(photo, caption=caption, reply_markup=None, parse_mode=None)
    except TelegramBadRequest:
        # An explicit Telegram rejection is not an ambiguous network failure.
        # Retain the reward and allow a later command to retry this receipt.
        # Paid edits may report "message is not modified" on an already-edited
        # anchor, so do not treat those as proof that no delivery occurred.
        if not notice:
            await container.daily_pet_service.release_rejected_notice(session['token'], user.id)
        logger.warning('Hedgehog photo rejected by Telegram user=%s paid_edit=%s', user.id, bool(notice), exc_info=True)
        if notice:
            raise GameError('Telegram отклонил обновление оплаченного уведомления. '
                            'Проверьте сообщения и обратитесь в /paysupport. Не оплачивайте повторно.')
        raise GameError('Картинка не доставлена. Награда сохранена; проверьте баланс. '
                        'Повторите /senseidaily или обратитесь в /paysupport.')
    await container.daily_pet_service.mark_delivered(session['token'], user.id)
    logger.info('Daily hedgehog photo delivered user=%s', user.id)
    return True
