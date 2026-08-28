"""
🛠️ Админ-команды для настройки боссов.
"""

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from src.bot.filters import AdminFilter
from src.core.container import Container
from src.core.visuals import Visuals

router = Router(name="boss_admin")

@router.message(Command("boss_settings"), AdminFilter())
async def cmd_boss_settings(message: Message, container: Container):
    """Показать текущие настройки наград босса."""
    settings = await container.boss_service.get_reward_settings()
    
    lines = [
        "⚙️ <b>Настройки наград Босса (xRocket):</b>",
        f"🎲 Шанс выпадения: {settings['drop_chance'] * 100:.1f}%",
        f"💰 Награда: {settings['reward_min']} - {settings['reward_max']} GRAM",
        f"🏦 Лимит пула: {settings['pool_limit']} GRAM",
        f"📊 Использовано: {settings['pool_used']:.4f} GRAM",
        "",
        "<b>Команды для изменения:</b>",
        "/boss_chance <0.0-1.0> - шанс выпадения",
        "/boss_reward <min> <max> - диапазон награды",
        "/boss_pool <limit> - лимит пула",
        "/boss_reset_pool - сбросить использованный пул"
    ]
    
    await message.answer("\n".join(lines), parse_mode="HTML")

@router.message(Command("boss_chance"), AdminFilter())
async def cmd_boss_chance(message: Message, command: CommandObject, container: Container):
    """Установить шанс выпадения награды."""
    try:
        if not command.args:
            raise ValueError("Укажите шанс (например, 0.05)")
            
        chance = float(command.args)
        if not 0 <= chance <= 1:
            raise ValueError("Шанс должен быть от 0.0 до 1.0")
            
        await container.boss_service.update_setting("drop_chance", chance)
        await message.answer(f"✅ Шанс выпадения установлен: {chance * 100:.1f}%")
        
    except ValueError as e:
        await message.answer(f"⚠️ Ошибка: {str(e)}")

@router.message(Command("boss_reward"), AdminFilter())
async def cmd_boss_reward(message: Message, command: CommandObject, container: Container):
    """Установить диапазон награды."""
    try:
        args = command.args.split() if command.args else []
        if len(args) != 2:
            raise ValueError("Укажите min и max (например, 0.006 0.02)")
            
        min_val = float(args[0])
        max_val = float(args[1])
        
        if min_val > max_val:
            min_val, max_val = max_val, min_val
            
        await container.boss_service.update_setting("reward_min", min_val)
        await container.boss_service.update_setting("reward_max", max_val)
        
        await message.answer(f"✅ Диапазон награды установлен: {min_val} - {max_val} GRAM")
        
    except ValueError as e:
        await message.answer(f"⚠️ Ошибка: {str(e)}")

@router.message(Command("boss_pool"), AdminFilter())
async def cmd_boss_pool(message: Message, command: CommandObject, container: Container):
    """Установить лимит пула."""
    try:
        if not command.args:
            raise ValueError("Укажите лимит (например, 10.0)")
            
        limit = float(command.args)
        if limit < 0:
            raise ValueError("Лимит не может быть отрицательным")
            
        await container.boss_service.update_setting("pool_limit", limit)
        await message.answer(f"✅ Лимит пула установлен: {limit} TON")
        
    except ValueError as e:
        await message.answer(f"⚠️ Ошибка: {str(e)}")

@router.message(Command("boss_reset_pool"), AdminFilter())
async def cmd_boss_reset_pool(message: Message, container: Container):
    """Сбросить счетчик использованного пула."""
    await container.boss_service.reset_pool()
    await message.answer("✅ Счетчик использованного пула сброшен.")
