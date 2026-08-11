"""
🥋 Сенсей управляет своим додзё.
"""

import random
from datetime import datetime

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandObject
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.core.config import settings
from src.services.maintenance_service import MaintenanceService, SENSEI_BACK_PHRASES
from src.bot.filters.admin import AdminFilter

router = Router(name="sensei_commands")
router.message.filter(AdminFilter())


# 🥋 Мотивационные фразы для сенсея
SENSEI_ENABLE_PHRASES = [
    "🥋 Сенсей закрыл додзё! Ученики рыдают у входа.",
    "⚔️ Сенсей ушёл в бой! Пожелаем ему удачи.",
    "🧘 Сенсей медитирует. Тишина в зале!",
    "🐉 Сенсей укрощает драконов. Не беспокоить!",
]


@router.message(Command("sensei"))
async def cmd_sensei(message: Message, command: CommandObject):
    """
    🥋 Управление режимом сенсея.
    
    /sensei - статус
    /sensei work [причина] - ушёл работать
    /sensei update - обновление
    /sensei fix - чиню баги 
    /sensei deploy - деплой (страшно)
    /sensei db - работа с БД
    /sensei done - вернулся
    /sensei 30 [причина] - ушёл на 30 минут
    """
    args = command.args.split() if command.args else []
    
    if not args:
        await _show_dojo_status(message)
        return
    
    action = args[0].lower()
    
    # 🔑 Быстрые пресеты
    presets = {
        "update": ("update", "Обновляю бота до новой версии"),
        "fix": ("fix", "Чиню то, что сломалось"),
        "deploy": ("deploy", "Деплою в продакшен 🙏"),
        "db": ("db", "Шаманю с базой данных"),
    }
    
    if action in presets:
        key, reason = presets[action]
        minutes = int(args[1]) if len(args) > 1 and args[1].isdigit() else None
        
        MaintenanceService.enable(
            reason=reason,
            reason_key=key,
            admin_id=message.from_user.id,
            estimated_minutes=minutes
        )
        
        await message.answer(
            f"{random.choice(SENSEI_ENABLE_PHRASES)}\n\n"
            f"📋 {reason}\n"
            f"{'⏱ Планирую вернуться через ' + str(minutes) + ' мин.' if minutes else '⏱ Время неизвестно'}",
            parse_mode="HTML"
        )
        return
    
    if action == "work":
        # Парсим аргументы
        remaining = args[1:]
        minutes = None
        
        if remaining and remaining[0].isdigit():
            minutes = int(remaining[0])
            remaining = remaining[1:]
        
        reason = " ".join(remaining) if remaining else "Работаю над секретными техниками"
        
        MaintenanceService.enable(
            reason=reason,
            admin_id=message.from_user.id,
            estimated_minutes=minutes
        )
        
        time_str = f"⏱ Планирую: ~{minutes} мин." if minutes else "⏱ Сколько надо, столько и буду!"
        
        await message.answer(
            f"🥋 <b>Додзё закрыто!</b>\n\n"
            f"📋 {reason}\n"
            f"{time_str}\n\n"
            f"<i>Ученики ждут снаружи и плачут...</i>",
            parse_mode="HTML"
        )
        
    elif action == "done" or action == "back":
        phrase = MaintenanceService.disable(admin_id=message.from_user.id)
        
        await message.answer(
            f"✨ <b>Додзё открыто!</b>\n\n"
            f"{phrase}\n\n"
            f"<i>Ученики могут вернуться к страданиям.</i>",
            parse_mode="HTML"
        )
        
    elif action.isdigit():
        # /sensei 30 причина
        minutes = int(action)
        reason = " ".join(args[1:]) if len(args) > 1 else "Делаю дела"
        
        MaintenanceService.enable(
            reason=reason,
            admin_id=message.from_user.id,
            estimated_minutes=minutes
        )
        
        await message.answer(
            f"🥋 <b>Сенсей ушёл на {minutes} минут</b>\n\n"
            f"📋 {reason}\n\n"
            f"<i>Таймер страданий запущен!</i>",
            parse_mode="HTML"
        )
        
    else:
        await message.answer(
            "🥋 <b>Команды сенсея:</b>\n\n"
            "• /sensei — статус додзё\n"
            "• /sensei work [мин] причина — ушёл работать\n"
            "• /sensei update — обновление\n"
            "• /sensei fix — фикшу баги\n"
            "• /sensei deploy — деплою (помолись)\n"
            "• /sensei db — работа с БД\n"
            "• /sensei 30 причина — ушёл на 30 мин\n"
            "• /sensei done — вернулся!",
            parse_mode="HTML"
        )


async def _show_dojo_status(message: Message):
    """Показать статус додзё."""
    state = MaintenanceService.get_state()
    
    if state.enabled:
        suffering = MaintenanceService.get_suffering_time()
        
        text = (
            "🥋 <b>ДОДЗЁ ЗАКРЫТО</b>\n\n"
            f"📋 {state.reason or 'Сенсей занят'}\n"
            f"{suffering}\n"
        )
        
        if state.estimated_end:
            remaining = (state.estimated_end - datetime.now()).total_seconds()
            if remaining > 0:
                text += f"🔮 Осталось: ~{int(remaining // 60)} мин.\n"
            else:
                text += "⚠️ Сенсей задерживается...\n"
        
        text += "\n<i>Ученики страдают у входа</i> 😢"
        
    else:
        text = (
            "⛩️ <b>ДОДЗЁ ОТКРЫТО</b>\n\n"
            "✅ Сенсей на месте\n"
            "✅ Ученики страдают штатно\n"
            "✅ Всё по плану\n\n"
            "<i>Но это ненадолго... 😈</i>"
        )
    
    # Кнопки
    builder = InlineKeyboardBuilder()
    
    if state.enabled:
        builder.button(text="✨ Вернуться!", callback_data="sensei:done")
    else:
        builder.button(text="🔧 Чинить", callback_data="sensei:fix")
        builder.button(text="🚀 Деплоить", callback_data="sensei:deploy")
        builder.button(text="📦 Обновлять", callback_data="sensei:update")
        builder.button(text="🗄️ БД", callback_data="sensei:db")
    
    builder.adjust(2)
    
    await message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("sensei:"))
async def callback_sensei(callback: CallbackQuery):
    """Кнопки управления."""
    if callback.from_user.id not in settings.admin_ids:
        try:
            await callback.answer("🥋 Ты не сенсей! Уходи!", show_alert=True)
        except Exception:
            pass
        return
    
    action = callback.data.split(":")[1]
    
    presets = {
        "update": ("update", "Обновляю бота"),
        "fix": ("fix", "Чиню баги"),
        "deploy": ("deploy", "Деплою в прод 🙏"),
        "db": ("db", "Работаю с БД"),
    }
    
    if action in presets:
        key, reason = presets[action]
        MaintenanceService.enable(
            reason=reason,
            reason_key=key,
            admin_id=callback.from_user.id
        )
        try:
            await callback.answer(f"🥋 Режим '{action}' активирован!")
        except Exception:
            pass
        
    elif action == "done":
        MaintenanceService.disable(admin_id=callback.from_user.id)
        try:
            await callback.answer("✨ Сенсей вернулся!")
        except Exception:
            pass
    
    # Обновляем сообщение
    try:
        await callback.message.delete()
    except:
        pass
    await _show_dojo_status(callback.message)
