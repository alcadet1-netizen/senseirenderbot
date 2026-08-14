"""
⚙️ Обработчики настроек чата.
"""

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ChatMemberStatus

from src.core.container import Container
from src.core.config import settings

router = Router(name="chat_settings")

async def is_admin(message: Message, bot: Bot) -> bool:
    """Проверяет, является ли пользователь админом чата или бота."""
    if message.from_user.id in settings.admin_ids:
        return True
        
    if message.chat.type not in ("group", "supergroup"):
        return False
        
    member = await bot.get_chat_member(message.chat.id, message.from_user.id)
    return member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR)

@router.message(Command("offexit"))
async def cmd_offexit(message: Message, bot: Bot, container: Container):
    """Отключает уведомления о выходе из чата."""
    if not await is_admin(message, bot):
        # Можно молча игнорировать или отвечать
        return

    key = f"chat:{message.chat.id}:exit_notifications"
    await container.chat_settings_service.set_setting(message.chat.id, key, "0")
    
    await message.answer("🔕 Уведомления о выходе из чата <b>отключены</b>.", parse_mode="HTML")

@router.message(Command("onexit"))
async def cmd_onexit(message: Message, bot: Bot, container: Container):
    """Включает уведомления о выходе из чата."""
    if not await is_admin(message, bot):
        return

    key = f"chat:{message.chat.id}:exit_notifications"
    await container.chat_settings_service.set_setting(message.chat.id, key, "1")
    
    await message.answer("🔔 Уведомления о выходе из чата <b>включены</b>.", parse_mode="HTML")
