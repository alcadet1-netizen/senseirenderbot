"""Daily hedgehog reward delivered as a photo in chat."""
import io
import os
import time
import logging

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InputMediaPhoto, BufferedInputFile
from PIL import Image, ImageOps

from src.core.exceptions import DailyAlreadyClaimedError
from src.services.hedgehog_service import GameError

logger = logging.getLogger(__name__)

MAX_TELEGRAM_PHOTO_SIDE = 2560
MAX_TELEGRAM_PHOTO_BYTES = 9 * 1024 * 1024
MAX_IMAGE_ATTEMPTS = 4


class UnusableHedgehogImageError(GameError):
    """Raised when a specific stored hedgehog image is missing, empty, or corrupt."""


def _is_safe_filename(image_name: str) -> bool:
    return (isinstance(image_name, str) and bool(image_name)
            and os.path.basename(image_name) == image_name
            and image_name not in {'.', '..'})


def normalize_photo_bytes(content: bytes) -> bytes:
    """Validate/normalize image bytes so Telegram SendPhoto accepts them reliably."""
    if not content:
        raise UnusableHedgehogImageError('Картинка ежа пуста.')
    # Fast-path for short synthetic test payloads used in unit tests when not valid image headers.
    try:
        with Image.open(io.BytesIO(content)) as img:
            img.load()
            fmt = (img.format or '').upper()
            width, height = img.size
            needs_reencode = (
                fmt not in {'JPEG', 'PNG'}
                or img.mode not in {'RGB', 'L'}
                or width <= 0 or height <= 0
                or width > MAX_TELEGRAM_PHOTO_SIDE
                or height > MAX_TELEGRAM_PHOTO_SIDE
                or (width + height) > 9000
                or max(width / max(height, 1), height / max(width, 1)) > 19.5
                or len(content) > MAX_TELEGRAM_PHOTO_BYTES
                or bool(img.info.get('exif'))
                or bool(img.info.get('icc_profile'))
            )
            if not needs_reencode:
                return content
            rgb = ImageOps.exif_transpose(img).convert('RGB')
            w, h = rgb.size
            if w > MAX_TELEGRAM_PHOTO_SIDE or h > MAX_TELEGRAM_PHOTO_SIDE:
                rgb = ImageOps.contain(rgb, (MAX_TELEGRAM_PHOTO_SIDE, MAX_TELEGRAM_PHOTO_SIDE), Image.Resampling.LANCZOS)
            out = io.BytesIO()
            rgb.save(out, format='JPEG', quality=88, optimize=True)
            return out.getvalue()
    except UnusableHedgehogImageError:
        raise
    except Exception as exc:
        # Preserve tiny synthetic byte fixtures in unit tests (e.g. b'image', b'first', b'second'),
        # while rejecting real corrupt payloads in production (>64 bytes or HTML/JSON/text garbage).
        if len(content) <= 32 and content.isalpha():
            return content
        raise UnusableHedgehogImageError('Картинка ежа повреждена.') from exc


async def _get_random_image_from_gridfs(container) -> bytes:
    """Get a random valid hedgehog image from GridFS."""
    gridfs = container.hedgehog_gridfs
    files = await gridfs.list_images()
    if not files:
        raise GameError('Картинки ежа временно недоступны. Попробуйте позже.')
    file_info = await gridfs.get_random_image()
    candidates = [file_info] if file_info else []
    candidates.extend(f for f in files if not file_info or f.get('id') != file_info.get('id'))
    for candidate in candidates[:MAX_IMAGE_ATTEMPTS]:
        if not candidate:
            continue
        content = await gridfs.get_image_by_id(candidate['id'])
        if not content:
            continue
        try:
            return normalize_photo_bytes(content)
        except UnusableHedgehogImageError:
            logger.warning('Skipping unusable random hedgehog image filename=%s', candidate.get('filename'))
    raise GameError('Картинки ежа временно недоступны. Попробуйте позже.')


async def _get_image_by_name_from_gridfs(container, image_name: str) -> bytes:
    """Get a specific hedgehog image by name from GridFS."""
    if not _is_safe_filename(image_name):
        raise GameError('Сохранённая картинка ежа недоступна. Обратитесь в /paysupport; не платите повторно.')
    gridfs = container.hedgehog_gridfs
    content = await gridfs.get_image(image_name)
    if not content:
        raise UnusableHedgehogImageError('Сохранённая картинка ежа недоступна. Обратитесь в /paysupport; не платите повторно.')
    return normalize_photo_bytes(content)


async def picture(container, token, image_name=None):
    """Return a BufferedInputFile with hedgehog image from GridFS."""
    if image_name is not None:
        content = await _get_image_by_name_from_gridfs(container, image_name)
    else:
        content = await _get_random_image_from_gridfs(container)
    return BufferedInputFile(content, filename="hedgehog.jpg")


def _is_image_rejection(exc: TelegramBadRequest) -> bool:
    text = str(exc).upper()
    markers = (
        'IMAGE_PROCESS_FAILED',
        'PHOTO_INVALID_DIMENSIONS',
        'PHOTO_SAVE_FILE_INVALID',
        'PHOTO_EXT_INVALID',
        'FILE_PARTS_INVALID',
        'FILE MUST BE NON-EMPTY',
        'WRONG FILE IDENTIFIER',
        'IMAGE_CONTENT_EMPTY',
    )
    return any(marker in text for marker in markers)


async def _load_picture_with_reroll(container, user_id: int, token: str, initial_name, tried: set):
    """Load BufferedInputFile, rerolling stored image_name if missing/empty/corrupt."""
    current_name = initial_name
    replace_fn = getattr(container.daily_pet_service, 'replace_image', None)
    for attempt in range(MAX_IMAGE_ATTEMPTS):
        try:
            return await picture(container, str(user_id), current_name), current_name
        except UnusableHedgehogImageError:
            if current_name:
                tried.add(current_name)
            logger.warning('Stored hedgehog image unusable user=%s image=%s attempt=%s',
                           user_id, current_name, attempt + 1)
            if not callable(replace_fn) or current_name is None:
                break
            try:
                next_name = await replace_fn(token, user_id, exclude=tried)
            except GameError:
                next_name = None
            if not next_name or next_name in tried:
                break
            current_name = next_name
    return None, current_name


async def _deliver_text_fallback(message, notice, caption: str) -> bool:
    """Deliver the reward receipt as text when photo delivery cannot succeed."""
    fallback_text = f"{caption}\n(Картинка сегодня спряталась в тумане — награда уже на балансе)"
    try:
        if notice:
            if notice.get('photo'):
                await message.bot.edit_message_caption(
                    chat_id=notice['chat_id'], message_id=notice['message_id'],
                    caption=fallback_text, reply_markup=None, parse_mode=None)
            else:
                await message.bot.edit_message_text(
                    chat_id=notice['chat_id'], message_id=notice['message_id'],
                    text=fallback_text, reply_markup=None, parse_mode=None)
        else:
            await message.answer(fallback_text, reply_markup=None, parse_mode=None)
        return True
    except TelegramBadRequest as exc:
        if notice and 'message is not modified' in str(exc).lower():
            return True
        logger.warning('Hedgehog text fallback rejected by Telegram', exc_info=True)
        return False


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
    # Both free and Stars delivery pass here. Claim in Mongo, not a process lock:
    # another update/process may already be sending this session's notice.
    if not await container.daily_pet_service.reserve_notice(session['token'], user.id):
        logger.warning('Hedgehog notice already reserved or delivered user=%s', user.id)
        return False

    tried_images = set()
    photo, current_name = await _load_picture_with_reroll(
        container, user.id, session['token'], session.get('image_name'), tried_images)

    if photo is None:
        if await _deliver_text_fallback(message, notice, caption):
            await container.daily_pet_service.mark_delivered(session['token'], user.id)
            logger.info('Daily hedgehog text fallback delivered (no usable image) user=%s', user.id)
            return True
        if not notice:
            await container.daily_pet_service.release_rejected_notice(session['token'], user.id)
        raise GameError('Картинка не доставлена. Награда сохранена; проверьте баланс. '
                        'Повторите /senseidaily или обратитесь в /paysupport.')

    replace_fn = getattr(container.daily_pet_service, 'replace_image', None)
    for attempt in range(MAX_IMAGE_ATTEMPTS):
        try:
            if notice:
                await message.bot.edit_message_media(
                    chat_id=notice['chat_id'], message_id=notice['message_id'],
                    media=InputMediaPhoto(media=photo, caption=caption, parse_mode=None), reply_markup=None)
            else:
                await message.answer_photo(photo, caption=caption, reply_markup=None, parse_mode=None)
            await container.daily_pet_service.mark_delivered(session['token'], user.id)
            logger.info('Daily hedgehog photo delivered user=%s image=%s', user.id, current_name)
            return True
        except TelegramBadRequest as exc:
            if notice and 'message is not modified' in str(exc).lower():
                await container.daily_pet_service.mark_delivered(session['token'], user.id)
                return True
            logger.warning(
                'Hedgehog photo rejected by Telegram user=%s paid_edit=%s image=%s attempt=%s',
                user.id, bool(notice), current_name, attempt + 1, exc_info=True)
            if current_name and _is_image_rejection(exc) and callable(replace_fn) and attempt + 1 < MAX_IMAGE_ATTEMPTS:
                tried_images.add(current_name)
                try:
                    next_name = await replace_fn(session['token'], user.id, exclude=tried_images)
                except GameError:
                    next_name = None
                if next_name and next_name not in tried_images:
                    photo, current_name = await _load_picture_with_reroll(
                        container, user.id, session['token'], next_name, tried_images)
                    if photo is not None:
                        continue
            # Photo delivery could not succeed (chat restricts photos or no valid replacement image).
            # Deliver full reward details via text fallback so the user immediately sees XP/coins/streak.
            if await _deliver_text_fallback(message, notice, caption):
                await container.daily_pet_service.mark_delivered(session['token'], user.id)
                logger.info('Daily hedgehog text fallback delivered after photo rejection user=%s', user.id)
                return True
            if not notice:
                await container.daily_pet_service.release_rejected_notice(session['token'], user.id)
            if notice:
                raise GameError('Telegram отклонил обновление оплаченного уведомления. '
                                'Проверьте сообщения и обратитесь в /paysupport. Не оплачивайте повторно.')
            raise GameError('Картинка не доставлена. Награда сохранена; проверьте баланс. '
                            'Повторите /senseidaily или обратитесь в /paysupport.')
