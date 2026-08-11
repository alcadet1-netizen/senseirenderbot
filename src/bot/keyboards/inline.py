"""
⌨️ Inline клавиатуры.
"""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData
import urllib.parse


class MenuCb(CallbackData, prefix="menu"):
    action: str
    user_id: int


class VisualsCb(CallbackData, prefix="visuals"):
    action: str
    user_id: int


class KatanaTopCb(CallbackData, prefix="katanatop"):
    page: int
    user_id: int


class RefCb(CallbackData, prefix="ref"):
    action: str
    user_id: int


class DigestCb(CallbackData, prefix="digest"):
    mode: str  # 'baldoi' or 'vestnik'
    user_id: int


class BossAttackCb(CallbackData, prefix="boss"):
    action: str  # 'hit' or 'ult'
    user_id: int


def get_katana_top_keyboard(user_id: int, page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Клавиатура пагинации топа катан."""
    buttons = []
    
    # Navigation buttons
    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton(text="◀️", callback_data=KatanaTopCb(page=page-1, user_id=user_id).pack()))
    
    nav_row.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop"))
    
    if page < total_pages:
        nav_row.append(InlineKeyboardButton(text="▶️", callback_data=KatanaTopCb(page=page+1, user_id=user_id).pack()))
        
    buttons.append(nav_row)
    
    # Back button
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data=MenuCb(action="back_to_profile", user_id=user_id).pack())])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_profile_keyboard(user_id: int, has_katana: bool = True) -> InlineKeyboardMarkup:
    """Клавиатура профиля."""
    keyboard = [
        [
            InlineKeyboardButton(text="💱 Обмен", callback_data=MenuCb(action="exchange_menu", user_id=user_id).pack()),
            InlineKeyboardButton(text="🏆 Достижения", callback_data=MenuCb(action="achievements", user_id=user_id).pack()),
        ],
        [
            InlineKeyboardButton(text="📊 Топ", callback_data=MenuCb(action="top_menu", user_id=user_id).pack()),
            InlineKeyboardButton(text="🎁 Бонус", callback_data=MenuCb(action="daily", user_id=user_id).pack()),
        ],
    ]
    
    if not has_katana:
        keyboard.insert(0, [
            InlineKeyboardButton(text="⚔️ Купить катану (1000 💰)", callback_data=MenuCb(action="buy_katana", user_id=user_id).pack())
        ])
    else:
        keyboard.insert(0, [
            InlineKeyboardButton(text="⚔️ Улучшить катану", callback_data=MenuCb(action="upgrade_katana_confirm", user_id=user_id).pack())
        ])
        
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_exchange_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Клавиатура обмена."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💰→🎫 Монеты в билет", callback_data=MenuCb(action="exchange_coins_to_ticket", user_id=user_id).pack())],
            [InlineKeyboardButton(text="🎫→💰 Билет в монеты", callback_data=MenuCb(action="exchange_ticket_to_coins", user_id=user_id).pack())],
            [InlineKeyboardButton(text="◀️ Назад", callback_data=MenuCb(action="back_to_profile", user_id=user_id).pack())],
        ]
    )


def get_top_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Клавиатура топов."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⚡ XP", callback_data=MenuCb(action="top_xp", user_id=user_id).pack()),
                InlineKeyboardButton(text="💰 Монеты", callback_data=MenuCb(action="top_coins", user_id=user_id).pack()),
            ],
            [
                InlineKeyboardButton(text="💬 Сообщения", callback_data=MenuCb(action="top_messages", user_id=user_id).pack()),
                InlineKeyboardButton(text="🔥 Страйк", callback_data=MenuCb(action="top_streak", user_id=user_id).pack()),
            ],
            [
                InlineKeyboardButton(text="🎫 Билеты", callback_data=MenuCb(action="top_tickets", user_id=user_id).pack()),
            ],
            [InlineKeyboardButton(text="◀️ Назад", callback_data=MenuCb(action="back_to_profile", user_id=user_id).pack())],
        ]
    )


def get_confirm_keyboard(user_id: int, action: str) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да", callback_data=MenuCb(action=f"confirm_{action}", user_id=user_id).pack()),
                InlineKeyboardButton(text="❌ Нет", callback_data=MenuCb(action="cancel", user_id=user_id).pack()),
            ],
        ]
    )


def get_start_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Клавиатура старта."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👤 Профиль", callback_data=MenuCb(action="profile", user_id=user_id).pack()),
                InlineKeyboardButton(text="🏆 Топ", callback_data=MenuCb(action="top_menu", user_id=user_id).pack()),
            ],
            [
                InlineKeyboardButton(text="🎁 Ежедневный бонус", callback_data=MenuCb(action="daily", user_id=user_id).pack()),
            ],
            [
                InlineKeyboardButton(text="❓ Помощь", callback_data=MenuCb(action="help", user_id=user_id).pack()),
            ]
        ]
    )

def get_referral_keyboard(link: str, user_id: int) -> InlineKeyboardMarkup:
    """Клавиатура реферальной системы."""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="📊 Статистика", callback_data=RefCb(action="stats", user_id=user_id).pack()),
        InlineKeyboardButton(text="🏆 Топ", callback_data=RefCb(action="top", user_id=user_id).pack())
    )
    builder.row(
        InlineKeyboardButton(text="💎 Награды", callback_data=RefCb(action="rewards", user_id=user_id).pack()),
        InlineKeyboardButton(text="🏅 Ранги", callback_data=RefCb(action="ranks", user_id=user_id).pack())
    )
    builder.row(
        InlineKeyboardButton(text="📋 Рефералы", callback_data=RefCb(action="list", user_id=user_id).pack()),
        InlineKeyboardButton(text="🏰 Империя", callback_data=RefCb(action="empire", user_id=user_id).pack())
    )
    builder.row(
        InlineKeyboardButton(text="🔗 Поделиться", callback_data=RefCb(action="share", user_id=user_id).pack()),
        InlineKeyboardButton(text="❓ Помощь", callback_data=RefCb(action="help", user_id=user_id).pack())
    )
    
    encoded_url = urllib.parse.quote(link)
    share_url = f"https://t.me/share/url?url={encoded_url}&text=В Sensei Bot'e тебя ждёт сюрприз. Залетай и забери свои 200 монет — пока все не разобрали!"
    
    builder.row(
        InlineKeyboardButton(text="📨 Отправить другу", url=share_url)
    )
    
    return builder.as_markup()

def get_referral_back_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Клавиатура назад в реферальное меню."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data=RefCb(action="menu", user_id=user_id).pack())]
        ]
    )
