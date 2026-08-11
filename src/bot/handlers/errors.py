"""
⚠️ Обработчик ошибок.
"""

import logging
import asyncio
import html
from aiogram import Router
from aiogram.types import ErrorEvent, Message, CallbackQuery
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramRetryAfter,
    TelegramNetworkError,
    TelegramForbiddenError,
)

from src.core.exceptions import (
    SenseiBotError,
    InsufficientFundsError,
    InsufficientTicketsError,
    UserNotFoundError,
    DailyAlreadyClaimedError,
    MaintenanceModeError,
    BankInsufficientFundsError,
    UserBannedError,
    CooldownError,
    NoKatanaError,
)

logger = logging.getLogger(__name__)

router = Router(name="errors")


@router.error()
async def error_handler(event: ErrorEvent):
    """Глобальный обработчик ошибок."""
    exception = event.exception
    update = event.update
    
    # 1. Игнорируем ошибки блокировки бота пользователем
    if isinstance(exception, TelegramForbiddenError):
        logger.info(f"Bot blocked by user: {exception}")
        return

    # 2. Логируем остальные ошибки
    # Если это наша кастомная ошибка - логируем как info, иначе exception
    if isinstance(exception, SenseiBotError):
        logger.info(f"Business logic error: {exception}")
    else:
        logger.exception(
            f"Error handling update {update.update_id}: {exception}",
            exc_info=exception
        )
    
    # 3. Пытаемся уведомить пользователя, если это возможно
    try:
        # Определяем чат и сообщение для ответа
        message = update.message or (update.callback_query.message if update.callback_query else None)
        
        if not message:
            return

        # Обработка разных типов ошибок
        if isinstance(exception, TelegramRetryAfter):
            # Если это флуд-контроль, можно попробовать подождать и повторить (но в глобальном хендлере лучше просто уведомить)
            # await asyncio.sleep(exception.retry_after)
            # return # или ретрай
            pass
            
        elif isinstance(exception, TelegramBadRequest):
            # Ошибки вроде "message not modified" или "chat not found"
            if "message is not modified" in str(exception):
                return
            await _notify_user(update, "⚠️ Ошибка запроса. Возможно, сообщение устарело.")
            
        elif isinstance(exception, TelegramNetworkError):
            logger.warning(f"Network error: {exception}")
            # Обычно нет смысла отвечать, так как сеть лежит

        # --- Обработка бизнес-логики ---
        elif isinstance(exception, InsufficientFundsError):
            await _notify_user(update, f"💰 <b>Недостаточно средств!</b>\nНужно: {exception.required}\nУ вас: {exception.available}")

        elif isinstance(exception, InsufficientTicketsError):
            await _notify_user(update, f"🎟 <b>Недостаточно билетов!</b>\nНужно: {exception.required}\nУ вас: {exception.available}")

        elif isinstance(exception, DailyAlreadyClaimedError):
            await _notify_user(update, f"⏳ <b>Бонус уже получен!</b>\nПриходите через: {exception.next_claim_time}")

        elif isinstance(exception, MaintenanceModeError):
            await _notify_user(update, "🛠 <b>Технические работы!</b>\nБот временно недоступен. Попробуйте позже.")

        elif isinstance(exception, BankInsufficientFundsError):
            await _notify_user(update, f"🏦 <b>В банке недостаточно средств!</b>\nПопробуйте сумму поменьше.")

        elif isinstance(exception, UserBannedError):
            await _notify_user(update, "🚫 <b>Вы забанены!</b>\nОбратитесь к администратору.")

        elif isinstance(exception, CooldownError):
            await _notify_user(update, f"⏳ <b>Подождите!</b>\nОсталось: {exception.formatted_time}")

        elif isinstance(exception, NoKatanaError):
            await _notify_user(update, "⚔️ <b>У вас нет катаны!</b>\nКупите её в профиле.")

        elif isinstance(exception, UserNotFoundError):
            await _notify_user(update, "❓ <b>Пользователь не найден.</b>\nПопробуйте /start")
        
        # --- Неизвестные ошибки ---
        else:
            # Неизвестная ошибка
            await _notify_user(update, "❌ Произошла внутренняя ошибка. Мы уже работаем над этим.")
            
    except Exception as e:
        logger.error(f"Failed to notify user about error: {e}")


async def _notify_user(update, text: str):
    """Безопасная отправка уведомления об ошибке."""
    try:
        if update.callback_query:
            await update.callback_query.answer(text, show_alert=True)
        elif update.message:
            # Add mention for message replies
            user = update.message.from_user
            if user:
                username = user.username
                mention = f"@{username}" if username else f"<b>{html.escape(user.full_name)}</b>"
                text = f"{mention}\n\n{text}"
                
            await update.message.answer(text, parse_mode="HTML")
    except Exception:
        pass
