"""
⚙️ Обработчики настроек чата.
"""

from aiogram import Router, F, Bot
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from aiogram.enums import ChatMemberStatus

from src.core.container import Container
from src.core.config import settings
from src.core.visuals import Visuals

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


@router.message(Command("welcomeon"))
async def cmd_welcomeon(message: Message, bot: Bot, container: Container):
    """Включает приветствие новых участников."""
    if not await is_admin(message, bot):
        return

    key = f"chat:{message.chat.id}:welcome_enabled"
    await container.chat_settings_service.set_setting(message.chat.id, key, "1")

    await message.answer("👋 Приветствие новых участников <b>включено</b>.", parse_mode="HTML")


@router.message(Command("welcomeoff"))
async def cmd_welcomeoff(message: Message, bot: Bot, container: Container):
    """Отключает приветствие новых участников."""
    if not await is_admin(message, bot):
        return

    key = f"chat:{message.chat.id}:welcome_enabled"
    await container.chat_settings_service.set_setting(message.chat.id, key, "0")

    await message.answer("🔇 Приветствие новых участников <b>отключено</b>.", parse_mode="HTML")


@router.message(Command("autobanon"))
async def cmd_autobanon(message: Message, bot: Bot, container: Container):
    """Включает автобан при выходе из чата."""
    if not await is_admin(message, bot):
        return

    key = f"chat:{message.chat.id}:autoban_enabled"
    await container.chat_settings_service.set_setting(message.chat.id, key, "1")

    await message.answer("🔨 Автобан при выходе из чата <b>включен</b>.", parse_mode="HTML")


@router.message(Command("autobanoff"))
async def cmd_autobanoff(message: Message, bot: Bot, container: Container):
    """Отключает автобан при выходе из чата."""
    if not await is_admin(message, bot):
        return

    key = f"chat:{message.chat.id}:autoban_enabled"
    await container.chat_settings_service.set_setting(message.chat.id, key, "0")

    await message.answer("🕊️ Автобан при выходе из чата <b>отключен</b>.", parse_mode="HTML")


@router.message(Command("uvedomleniaon"))
async def cmd_uvedomleniaon(message: Message, bot: Bot, container: Container):
    """Включает уведомления об активности (уровень, билеты, достижения)."""
    if not await is_admin(message, bot):
        return

    key = f"chat:{message.chat.id}:activity_notifications_enabled"
    await container.chat_settings_service.set_setting(message.chat.id, key, "1")

    await message.answer("🔔 Уведомления об активности (уровень, билеты, достижения) <b>включены</b>.", parse_mode="HTML")


@router.message(Command("uvedomleniaoff"))
async def cmd_uvedomleniaoff(message: Message, bot: Bot, container: Container):
    """Отключает уведомления об активности (уровень, билеты, достижения)."""
    if not await is_admin(message, bot):
        return

    key = f"chat:{message.chat.id}:activity_notifications_enabled"
    await container.chat_settings_service.set_setting(message.chat.id, key, "0")

    await message.answer("🔕 Уведомления об активности (уровень, билеты, достижения) <b>отключены</b>.", parse_mode="HTML")


@router.message(Command("popugai"))
async def cmd_popugai(message: Message, command: CommandObject, bot: Bot, container: Container):
    if message.chat.type not in ("group", "supergroup"):
        return

    if not await is_admin(message, bot):
        return

    chat_id = message.chat.id
    service = container.popugai_service
    arg = (command.args or "").strip().lower() if command and command.args else ""

    if not arg:
        chance = await service.get_reply_chance(chat_id)
        if chance <= 0:
            await message.answer(
                "🦜 Попугай в этом чате: <b>выключен</b>.\n\n"
                "Примеры:\n"
                "/popugai 5  — 5% шанс ответа\n"
                "/popugai off — выключить",
                parse_mode="HTML"
            )
            return

        percent = int(chance * 100)
        await message.answer(
            f"🦜 Попугай включен. Текущий шанс ответа: <b>{percent}%</b>.\n\n"
            "Измени его командой /popugai X (в процентах) или выключи /popugai off.",
            parse_mode="HTML"
        )
        return

    lowered = arg
    if lowered in {"off", "выкл", "0"}:
        await service.set_reply_chance(chat_id, 0.0)
        await message.answer("🦜 Попугай в этом чате <b>выключен</b>.", parse_mode="HTML")
        return

    try:
        value_str = lowered.replace("%", "").replace(",", ".")
        value = float(value_str)
    except ValueError:
        await message.answer(
            f"{Visuals.cross()} Неверный формат.\n\n"
            "Используй:\n"
            "/popugai 5  — 5% шанс ответа\n"
            "/popugai 0  — выключить\n"
            "/popugai off — выключить",
            parse_mode="HTML"
        )
        return

    if value <= 0:
        await service.set_reply_chance(chat_id, 0.0)
        await message.answer("🦜 Попугай в этом чате <b>выключен</b>.", parse_mode="HTML")
        return

    if value > 100:
        value = 100.0

    if value > 1:
        # Treat as percentage (e.g., 15 -> 0.15)
        chance = value / 100.0
        percent = int(value)
    else:
        # Treat as decimal probability (e.g., 0.15 -> 0.15)
        chance = value
        percent = int(chance * 100)

    await service.set_reply_chance(chat_id, chance)
    await message.answer(
        f"🦜 Попугай в этом чате включен.\n"
        f"Текущий шанс ответа: <b>{percent}%</b>.",
        parse_mode="HTML"
    )