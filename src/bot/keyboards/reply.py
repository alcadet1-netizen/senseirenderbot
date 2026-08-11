"""
⌨️ Reply клавиатуры.
"""

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Главная клавиатура."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="сенсей дай курс"), KeyboardButton(text="ℹ️ Помощь")],
            [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="🎁 Бонус")],
        ],
        resize_keyboard=True,
    )

def get_crypto_start_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура из команды start (по запросу)."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 CoinGecko"), KeyboardButton(text="💹 CoinCap")],
            [KeyboardButton(text="🔶 Binance"), KeyboardButton(text="📈 Сравнить")],
            [KeyboardButton(text="ℹ️ Помощь")],
        ],
        resize_keyboard=True,
    )


def get_admin_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура админа."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="🎰 Розыгрыш")],
            [KeyboardButton(text="📢 Рассылка"), KeyboardButton(text="🛡️ Модерация")],
            [KeyboardButton(text="⚙️ Система"), KeyboardButton(text="◀️ Назад")],
        ],
        resize_keyboard=True,
    )