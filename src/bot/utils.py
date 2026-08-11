from aiogram.types import CallbackQuery
from aiogram.exceptions import TelegramBadRequest

async def check_owner(callback: CallbackQuery, owner_id: int) -> bool:
    """
    Проверяет, является ли пользователь владельцем кнопки (меню).
    Если нет, отправляет уведомление и возвращает False.
    """
    if callback.from_user.id != owner_id:
        try:
            await callback.answer("⛔ Эта кнопка не для тебя!", show_alert=True)
        except TelegramBadRequest:
            pass
        return False
    return True
