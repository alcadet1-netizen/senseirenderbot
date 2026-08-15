"""
👤 Обработчики пользовательских команд.
"""

import os
import random
import re
import logging
import html
from aiogram import Router, F
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.types import Message, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest

from src.bot.filters import AdminFilter, PrivateChatFilter
from src.core.config import settings
from src.core.container import Container
from src.core.visuals import Visuals
from src.core.exceptions import (
    DailyAlreadyClaimedError,
    InsufficientFundsError,
    InsufficientTicketsError,
    UserNotFoundError,
    CooldownError,
    NoKatanaError,
)
from src.bot.keyboards import (
    get_profile_keyboard,
    get_exchange_keyboard,
    get_top_keyboard,
    get_crypto_start_keyboard,
    get_main_keyboard,
)
from src.bot.keyboards.inline import MenuCb, get_start_keyboard, get_katana_top_keyboard
import math

logger = logging.getLogger(__name__)

router = Router(name="user_commands")


def get_mention(user) -> str:
    """Safe mention construction."""
    if user.username:
        return f"@{user.username}"
    return f"<b>{html.escape(user.full_name)}</b>"


async def show_profile(message: Message, container: Container, user, is_edit: bool = False):
    """Отобразить профиль."""
    mention = get_mention(user)

    profile = await container.user_service.get_profile(user.id)

    if not profile:
        # Пытаемся создать, если нет
        await container.user_service.get_or_create(
            user_id=user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name or "",
            last_name=message.from_user.last_name,
            is_bot=message.from_user.is_bot or False,
        )
        profile = await container.user_service.get_profile(user.id)

        if not profile:
            text = f"{mention}\n\n❌ Профиль не найден. Попробуйте /start"
            try:
                if is_edit:
                    await message.edit_text(text, parse_mode="HTML")
                else:
                    await message.answer(text, parse_mode="HTML")
            except Exception as e:
                logger.error(f"❌ Failed to send profile not found message: {e}")
            return

    card = Visuals.profile_card(
        username=profile["username"],
        level=profile["level"],
        level_name=profile["level_name"],
        xp=profile["xp"],
        xp_next=profile["xp_next"],
        coins=profile["coins"],
        tickets=profile["tickets"],
        messages=profile["messages_count"],
        streak=profile["daily_streak"],
        has_katana=profile["has_katana"],
        katana_length=profile.get("katana_length", 0.0),
        achievements_count=profile["achievements_count"],
        wins=profile.get("wins", 0),
        losses=profile.get("losses", 0),
        role=profile.get("role"),
    )

    markup = get_profile_keyboard(user_id=user.id, has_katana=profile["has_katana"])

    text = f"{mention}\n\n{card}"

    try:
        if is_edit:
            await message.edit_text(text, parse_mode="HTML", reply_markup=markup)
        else:
            await message.answer(text, parse_mode="HTML", reply_markup=markup)
        logger.info(f"✅ Profile shown for {user.id}")
    except Exception as e:
        logger.error(f"❌ Failed to send profile card: {e}")


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, container: Container) -> None:
    """Команда /start."""
    logger.info(f"👉 [CMD] cmd_start triggered by {message.from_user.id}")
    if not message.from_user:
        return

    await container.user_service.get_or_create(
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name or "",
        last_name=message.from_user.last_name,
    )

    # Обработка реферальной ссылки
    args = command.args
    if args and args.startswith("ref_"):
        # Используем ReferralService
        res, msg = await container.referral_service.process_referral(message.from_user.id, args)
        if res:
             try:
                await message.answer(msg, parse_mode="HTML")
             except Exception as e:
                logger.error(f"❌ Failed to send referral message: {e}")

    mention = get_mention(message.from_user)

    # 1. Основное меню (Reply)
    reply_markup = get_main_keyboard() if message.chat.type == "private" else None
    try:
        await message.answer(
            "👋",
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"❌ Failed to send handshake: {e}")

    # 2. Интерактивное меню (Inline)
    text = Visuals.start_menu(message.from_user.first_name)

    if message.chat.type == "private":
        text += "\n\nПроект существует в том числе на ваши пожертвования, если вам нравится бот можете поддержать автора <code>https://t.me/xrocket?start=inv_uBCMaE7YvzGJYwF</code>"

    try:
        await message.answer(
            f"{mention}\n\n{text}",
            parse_mode="HTML",
            reply_markup=get_start_keyboard(message.from_user.id)
        )
        logger.info(f"✅ Start menu sent to {message.from_user.id}")
    except Exception as e:
        logger.error(f"❌ Failed to send start menu: {e}")


@router.message(Command("upkatana"))
@router.message(F.text.regexp(r"(?i)(?:^|\s)/upkatana(@\w+)?\b"))
@router.message(F.text.lower().in_({"ап катана", "\\upkatana"}))
async def cmd_upkatana(message: Message, container: Container):
    """Команда /upkatana - улучшение катаны."""
    logger.info(f"👉 [CMD] cmd_upkatana triggered by {message.from_user.id}")
    if not message.from_user:
        return

    # Delete trigger message
    try:
        await message.delete()
    except TelegramBadRequest:
        pass
    except Exception as e:
        logger.warning(f"⚠️ Failed to delete trigger message in cmd_upkatana: {e}")

    mention = get_mention(message.from_user)

    try:
        result = await container.economy_service.upgrade_katana(message.from_user.id)

        # Успех или неудача (но транзакция прошла)
        is_upgraded = result["is_upgraded"]
        growth = result["growth"]
        new_length = result["new_length"]
        cost = result["cost"]

        text = Visuals.katana_upgrade_result(
            is_success=is_upgraded,
            growth=growth,
            length=new_length,
            cost=cost
        )

        await message.answer(f"{mention}\n\n{text}", parse_mode="HTML")
        logger.info(f"✅ Upkatana result sent to {message.from_user.id}")

    except UserNotFoundError:
        await message.answer(f"{mention}\n\n❌ Профиль не найдено!")

    except NoKatanaError:
        await message.answer(f"{mention}\n\n❌ У тебя нет катаны! Купи её в /mysensei.")

    except CooldownError as e:
        await message.answer(
            f"{mention}\n\n"
            f"⏳ <b>Мастер устал...</b>\n"
            f"{e}",
            parse_mode="HTML"
        )

    except InsufficientFundsError as e:
        await message.answer(
            f"{mention}\n\n"
            f"❌ <b>Не хватает монет!</b>\n"
            f"Нужно: {e.required:,.0f}  💰\n"
            f"У тебя: {e.available:,.0f}  💰",
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"❌ Error in cmd_upkatana: {e}", exc_info=True)


@router.message(Command("mykatana"))
@router.message(F.text.regexp(r"(?i)(?:^|\s)/mykatana(@\w+)?\b"))
@router.message(F.text.lower().in_({"моя катана"}))
async def cmd_mykatana(message: Message, container: Container) -> None:
    """Команда /mykatana - информация о катане."""
    logger.info(f"👉 [CMD] cmd_mykatana triggered by {message.from_user.id}")
    if not message.from_user:
        return

    mention = get_mention(message.from_user)

    try:
        profile = await container.user_service.get_profile(message.from_user.id)
        if not profile or not profile.get("has_katana"):
            await message.answer(f"{mention}\n\n❌ У тебя нет катаны! Купи её в магазине.")
            return

        length = profile.get("katana_length", 0.0)

        # Визуализация катаны
        text = Visuals.katana_info(length)
        await message.answer(f"{mention}\n\n{text}", parse_mode="HTML")
        logger.info(f"✅ Mykatana info sent to {message.from_user.id}")
    except Exception as e:
        logger.error(f"❌ Error in cmd_mykatana: {e}", exc_info=True)


@router.message(Command("senseihelp", "помощь", "help"))
@router.message(F.text.regexp(r"(?i)(?:^|\s)/senseihelp(@\w+)?\b"))
@router.message(F.text.lower().in_({"сенсей помоги", "сенсей что умеешь?"}))
async def cmd_help(message: Message):
    """Команда /senseihelp."""
    logger.info(f"👉 [CMD] cmd_help triggered by {message.from_user.id}")

    # Check permissions: User can only use in chat (groups), Admin can use everywhere
    is_admin = message.from_user.id in settings.admin_ids
    is_private = message.chat.type == "private"

    if is_private and not is_admin:
        await message.answer("⚠️ Эта команда доступна только в групповых чатах.", parse_mode="HTML")
        return

    mention = get_mention(message.from_user)

    try:
        text = Visuals.help_card()
        await message.answer(f"{mention}\n\n{text}", parse_mode="HTML")
        logger.info(f"✅ Help sent to {message.from_user.id}")
    except Exception as e:
        logger.error(f"❌ Failed to send help: {e}", exc_info=True)


@router.message(Command("mysensei", "профиль", "profile"))
@router.message(F.text.regexp(r"(?i)(?:^|\s)/mysensei(@\w+)?\b"))
@router.message(F.text.lower() == "мой сенсей")
@router.message(F.text == "👤 Профиль", PrivateChatFilter())
async def cmd_profile(message: Message, container: Container) -> None:
    """Команда /mysensei - профиль."""
    logger.info(f"👉 [CMD] cmd_profile triggered by {message.from_user.id}")
    if not message.from_user:
        return

    # Check cooldown - disabled for now
    # TODO: Implement cooldown using MongoDB
    pass

    await show_profile(message, container, message.from_user)


@router.message(Command("mycoin"))
@router.message(F.text.lower() == "мой балик")
async def cmd_mycoin(message: Message, container: Container) -> None:
    """Команда /mycoin и 'Мой балик'."""
    logger.info(f"👉 [CMD] cmd_mycoin triggered by {message.from_user.id}")
    if not message.from_user:
        return

    user_id = message.from_user.id
    profile = await container.user_service.get_profile(user_id)

    if not profile:
        await message.answer("❌ Профиль не найден. Напиши /start", parse_mode="HTML")
        return

    coins = profile["coins"]
    usdt_value = coins * 0.0002

    mention = get_mention(message.from_user)

    text = (
        f"{mention}\n\n"
        f"💰 <b>Твой баланс:</b> {int(coins):,} COIN\n"
        f"💱 <b>Оценка:</b> ≈ {usdt_value:,.2f} USDT"
    ).replace(",", " ")

    await message.answer(text, parse_mode="HTML")


@router.message(Command("senseitop", "топ", "top", "рейтинг"))
async def cmd_top(message: Message, container: Container):
    """Команда /senseitop - топы."""
    logger.info(f"👉 [CMD] cmd_top triggered by {message.from_user.id}")
    mention = get_mention(message.from_user)

    try:
        top_xp = await container.user_service.get_top_by_xp(10)

        text = Visuals.top_table(
            title="ТОП ПО XP",
            emoji="⚡",
            items=top_xp,
            value_key="xp"
        )

        await message.answer(f"{mention}\n\n{text}", parse_mode="HTML", reply_markup=get_top_keyboard(user_id=message.from_user.id))
        logger.info(f"✅ Top sent to {message.from_user.id}")
    except Exception as e:
        logger.error(f"❌ Error in cmd_top: {e}", exc_info=True)


@router.message(Command("topkatana"))
@router.message(F.text.regexp(r"(?i)(?:^|\s)/topkatana(@\w+)?\b"))
async def cmd_topkatana(message: Message, container: Container):
    """Команда /topkatana - топ катан с артами."""
    logger.info(f"👉 [CMD] cmd_topkatana triggered by {message.from_user.id}")
    mention = get_mention(message.from_user)

    try:
        # Получаем топ 10 для первой страницы
        limit = 10
        offset = 0

        result = await container.user_service.get_top_by_katana(limit, offset)
        items = result["items"]
        total = result["total"]

        total_pages = math.ceil(total / limit)

        text = Visuals.top_katana_table(
            title="ТОП КАТАН",
            emoji="🗡️",
            items=items,
            offset=offset
        )

        # Показываем клавиатуру пагинации только если есть что листать
        if total_pages > 1:
            reply_markup = get_katana_top_keyboard(user_id=message.from_user.id, page=1, total_pages=total_pages)
        else:
            reply_markup = None

        await message.answer(f"{mention}\n\n{text}", parse_mode="HTML", reply_markup=reply_markup)
        logger.info(f"✅ Top katana sent to {message.from_user.id}")
    except Exception as e:
        logger.error(f"❌ Error in cmd_topkatana: {e}", exc_info=True)


@router.message(Command("senseidaily", "бонус", "daily"))
@router.message(F.text.regexp(r"(?i)(?:^|\s)/senseidaily(@\w+)?\b"))
@router.message(F.text.lower().in_({"ежа", "фарм", "фармить", "фарма", "ферма"}))
@router.message(F.text == "🎁 Бонус", PrivateChatFilter())
async def cmd_daily(message: Message, container: Container):
    """Команда /senseidaily - ежедневный бонус."""
    logger.info(f"👉 [CMD] cmd_daily triggered by {message.from_user.id}")
    if not message.from_user:
        return

    # Delete trigger message (except private chat button which we can't detect easily here but safe to try)
    # Don't delete if it is "🎁 Бонус" (button text) in private chat usually, but here we can just try.
    if message.chat.type != "private" or message.text not in ["🎁 Бонус"]:
         try:
            await message.delete()
         except TelegramBadRequest:
            pass
         except Exception as e:
            logger.warning(f"⚠️ Failed to delete trigger message in cmd_daily: {e}")

    mention = get_mention(message.from_user)

    try:
        result = await container.daily_service.claim_daily(
            user_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name or ""
        )

        if result["success"]:
            card = Visuals.daily_reward(
                xp=result["xp"],
                coins=result["coins"],
                streak=result["streak"],
                bonus_xp=result["bonus_xp"],
                bonus_coins=result["bonus_coins"]
            )

            # Add hedgehog message
            hedgehog_msg = "🦔 <b>Вы погладили ежа!</b>\n\n"
            full_text = f"{mention}\n\n{hedgehog_msg}{card}"

            # Пытаемся отправить картинку из папки ega
            ega_path = settings.BASE_DIR / "src" / "infra" / "storage" / "ega"

            sent_photo = False
            if ega_path.exists():
                images = [f.name for f in ega_path.iterdir() if f.suffix.lower() in ('.jpg', '.jpeg', '.png', '.gif')]
                if images:
                    image_name = random.choice(images)
                    image_path = ega_path / image_name
                    try:
                        # Используем send_photo чтобы сообщение не удалялось
                        await message.bot.send_photo(
                            chat_id=message.chat.id,
                            photo=FSInputFile(str(image_path)),
                            caption=full_text,
                            parse_mode="HTML"
                        )
                        sent_photo = True
                        logger.info(f"✅ Daily photo sent to {message.from_user.id}")
                    except Exception as e:
                        logger.warning(f"⚠️ Failed to send daily photo: {e}")

            if not sent_photo:
                # Используем send_message если фото не удалось отправить
                await message.bot.send_message(
                    chat_id=message.chat.id,
                    text=full_text,
                    parse_mode="HTML"
                )
                logger.info(f"✅ Daily text sent to {message.from_user.id}")
        else:
            await message.bot.send_message(
                chat_id=message.chat.id,
                text=f"{mention}\n\n❌ {result.get('error', 'Ошибка')}",
                parse_mode="HTML"
            )

    except DailyAlreadyClaimedError as e:
        await message.answer(
            f"{mention}\n\n"
            f"⏰ <b>Бонус уже получен!</b>\n\n"
            f"Следующий доступен: {e.next_claim_time}",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"❌ Error in cmd_daily: {e}", exc_info=True)


@router.message(Command("senseiobmen", "обмен", "exchange"))
@router.message(F.text.regexp(r"(?i)(?:^|\s)/senseiobmen(@\w+)?\b"))
async def cmd_exchange(message: Message):
    """Команда /senseiobmen - обмен."""
    logger.info(f"👉 [CMD] cmd_exchange triggered by {message.from_user.id}")
    mention = get_mention(message.from_user)

    try:
        text = Visuals.exchange_info_card()

        await message.answer(f"{mention}\n\n{text}", parse_mode="HTML", reply_markup=get_exchange_keyboard(user_id=message.from_user.id))
        logger.info(f"✅ Exchange sent to {message.from_user.id}")
    except Exception as e:
        logger.error(f"❌ Error in cmd_exchange: {e}", exc_info=True)


@router.message(Command("senseibank"))
@router.message(F.text.regexp(r"(?i)(?:^|\s)/senseibank(@\w+)?\b"))
async def cmd_senseibank(message: Message, container: Container):
    """Команда /senseibank - статистика банка."""
    logger.info(f"👉 [CMD] cmd_senseibank triggered by {message.from_user.id}")
    if not message.from_user:
        return

    mention = get_mention(message.from_user)

    try:
        stats = await container.stats_service.get_admin_stats()

        text = Visuals.bank_card(stats)
        await message.answer(f"{mention}\n\n{text}", parse_mode="HTML")
        logger.info(f"✅ Bank stats sent to {message.from_user.id}")
    except Exception as e:
        logger.error(f"❌ Error in cmd_senseibank: {e}", exc_info=True)


@router.message(Command("senseiuser"))
@router.message(F.text.regexp(r"(?i)(?:^|\s)/senseiuser(@\w+)?\b"))
async def cmd_senseiuser(message: Message, container: Container):
    """Команда /senseiuser - количество пользователей."""
    logger.info(f"👉 [CMD] cmd_senseiuser triggered by {message.from_user.id}")
    if not message.from_user:
        return

    mention = get_mention(message.from_user)

    try:
        stats = await container.stats_service.get_admin_stats()
        total_users = stats.get("users", {}).get("total", 0)

        width = 24
        lines = [
            Visuals.frame_top_left(width),
            Visuals.frame_line_left("👥 ПОЛЬЗОВАТЕЛИ", width, "center"),
            Visuals.frame_separator_left(width),
            Visuals.frame_line_left(f"Всего: {total_users}", width),
            Visuals.frame_bottom_left(width)
        ]

        text = f"<pre>{chr(10).join(lines)}</pre>"

        await message.answer(f"{mention}\n\n{text}", parse_mode="HTML")
    except Exception as e:
        logger.error(f"❌ Error in cmd_senseiuser: {e}", exc_info=True)
        await message.answer(f"{mention}\n\n❌ Ошибка получения данных.", parse_mode="HTML")


# ========== CALLBACK HANDLERS ==========
# Callback handlers have been moved to src/bot/handlers/callbacks.py