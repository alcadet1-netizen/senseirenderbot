from aiogram.types import InlineKeyboardMarkup as IKM, InlineKeyboardButton as IKB
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData

class BroadcastCb(CallbackData, prefix="bc"):
    action: str
    user_id: int

def broadcast_menu_kb(user_id: int) -> IKM:
    b = InlineKeyboardBuilder()
    b.row(IKB(text="📝 Текст", callback_data=BroadcastCb(action="text", user_id=user_id).pack()), IKB(text="🖼 Фото", callback_data=BroadcastCb(action="photo", user_id=user_id).pack()))
    b.row(IKB(text="🎬 GIF", callback_data=BroadcastCb(action="gif", user_id=user_id).pack()), IKB(text="🎥 Видео", callback_data=BroadcastCb(action="video", user_id=user_id).pack()))
    b.row(IKB(text="📎 Файл", callback_data=BroadcastCb(action="doc", user_id=user_id).pack()), IKB(text="👥 Статистика", callback_data=BroadcastCb(action="stats", user_id=user_id).pack()))
    b.row(IKB(text="❌ Закрыть", callback_data=BroadcastCb(action="close", user_id=user_id).pack()))
    return b.as_markup()

def skip_text_kb(user_id: int) -> IKM:
    return IKM(inline_keyboard=[
        [IKB(text="⏭ Без текста", callback_data=BroadcastCb(action="skip_text", user_id=user_id).pack())],
        [IKB(text="❌ Отмена", callback_data=BroadcastCb(action="cancel", user_id=user_id).pack())]
    ])

def cancel_kb(user_id: int) -> IKM:
    return IKM(inline_keyboard=[[IKB(text="❌ Отмена", callback_data=BroadcastCb(action="cancel", user_id=user_id).pack())]])

def confirm_kb(user_id: int) -> IKM:
    b = InlineKeyboardBuilder()
    b.row(IKB(text="🚀 Старт", callback_data=BroadcastCb(action="send", user_id=user_id).pack()), IKB(text="❌ Отмена", callback_data=BroadcastCb(action="cancel", user_id=user_id).pack()))
    b.row(IKB(text="✏️ Изменить", callback_data=BroadcastCb(action="edit_text", user_id=user_id).pack()))
    return b.as_markup()
