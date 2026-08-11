"""Keyboards package."""

from src.bot.keyboards.inline import (
    get_profile_keyboard,
    get_exchange_keyboard,
    get_top_keyboard,
    get_confirm_keyboard,
)
from src.bot.keyboards.reply import (
    get_main_keyboard,
    get_admin_keyboard,
    get_crypto_start_keyboard,
)

__all__ = [
    "get_profile_keyboard",
    "get_exchange_keyboard",
    "get_top_keyboard",
    "get_confirm_keyboard",
    "get_main_keyboard",
    "get_admin_keyboard",
    "get_crypto_start_keyboard",
]