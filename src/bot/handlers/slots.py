"""
🎰 Обработчик для команды /senseislots.
"""

import asyncio
import html
from aiogram import Router, F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from src.core.container import Container
from src.core.visuals import Visuals

router = Router(name="slots_commands")


@router.message(Command("senseislots", "senseislot"))
async def cmd_slots(message: Message, command: CommandObject, container: Container):
    """
    🎰 Игра в слоты.
    """
    if not message.from_user:
        return

    user_id = message.from_user.id
    username_tg = message.from_user.username
    mention = f"@{username_tg}" if username_tg else f"<b>{html.escape(message.from_user.full_name)}</b>"
    
    # Для визуализации используем просто имя
    username = message.from_user.first_name

    # Парсинг ставки
    bet = 10
    if command.args:
        try:
            arg = command.args.strip().lower()
            multiplier = 1
            if arg.endswith('k') or arg.endswith('к'):
                multiplier = 1_000
                arg = arg[:-1]
            elif arg.endswith('m') or arg.endswith('м'):
                multiplier = 1_000_000
                arg = arg[:-1]
            
            # Разрешаем float ввод, например 1.5k
            bet = int(float(arg) * multiplier)
        except ValueError:
            await message.answer(f"{mention}\n\n❌ Неверная ставка. Используйте число (например, /senseislots 100 или 1k).", parse_mode="HTML")
            return

    if bet < 1:
        await message.answer(f"{mention}\n\n❌ Ставка должна быть больше 0.", parse_mode="HTML")
        return
    if bet > 1_000_000:
        await message.answer(f"{mention}\n\n❌ Максимальная ставка 1,000,000.", parse_mode="HTML")
        return

    # Delete user command message
    try:
        await message.delete()
    except Exception:
        pass

    # 0. Удаляем предыдущее сообщение
    await container.message_cleanup_service.cleanup_previous(message.chat.id, user_id, "slots", message.bot)

    # 1. Запускаем игру (атомарно списываем, считаем результат)
    result = await container.slots_service.play_slots(user_id, bet)

    if not result["success"]:
        reason = result["reason"]
        if reason == "user_not_found":
            await message.answer(f"{mention}\n\n❌ Профиль не найден. Напишите сообщение в чат.", parse_mode="HTML")
        elif reason == "insufficient_funds":
            await message.answer(f"{mention}\n\n❌ Недостаточно средств! Баланс: {result['balance']:,.0f}", parse_mode="HTML")
        else:
            await message.answer(f"{mention}\n\n❌ Ошибка игры.", parse_mode="HTML")
        return

    # 2. Анимация
    # Получаем результат из сервиса
    final_symbols = result["symbols"]
    is_win = result["is_win"]
    prize = result["prize"]
    fee = result["fee"]
    balance_end = result["balance"]
    
    # Баланс для анимации (до начисления выигрыша, но после списания ставки)
    # result['balance'] это уже конечный баланс.
    # Если выиграл: balance_end = start - bet + prize.
    # Если проиграл: balance_end = start - bet.
    # Нам нужен баланс "в процессе", то есть (start - bet).
    if is_win:
        balance_anim = balance_end - prize
    else:
        balance_anim = balance_end

    frames = Visuals.get_slots_animation(
        username=username,
        balance=balance_anim,
        bet=bet,
        fee=fee,
        final_symbols=final_symbols,
        spins=6
    )

    sent_msg = await message.answer(f"{mention}\n\n{frames[0]}", parse_mode="HTML")
    
    # Сохраняем ID сообщения для последующего удаления
    await container.message_cleanup_service.set_last(message.chat.id, user_id, "slots", sent_msg.message_id)

    for frame in frames[1:]:
        await asyncio.sleep(0.5)
        # Игнорируем ошибки редактирования (если удалили сообщение)
        try:
            # Need to keep mention in frames
            text_frame = f"{mention}\n\n{frame}"
            if sent_msg.text != text_frame: # aiogram сам проверяет, но на всякий
                await sent_msg.edit_text(text_frame, parse_mode="HTML")
        except Exception:
            pass

    # 3. Финальный результат
    # Генерируем финальную картинку
    final_text = Visuals.get_slots_result(
        result_symbols=final_symbols,
        is_win=is_win,
        prize=prize,
        username=username,
        remaining_coins=balance_end,
        bet=bet,
        fee=fee
    )
    
    full_final_text = f"{mention}\n\n{final_text}"

    try:
        await sent_msg.edit_text(full_final_text, parse_mode="HTML")
    except Exception:
        await message.answer(full_final_text, parse_mode="HTML")
