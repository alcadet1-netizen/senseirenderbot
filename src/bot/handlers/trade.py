"""
💹 Trade command handler.
"""

import asyncio
import logging
import random
import html
from typing import Optional, List, Tuple

from aiogram import Router, F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, CallbackQuery
from aiogram.enums import ChatType

from src.core.config import settings
from src.core.container import Container
from src.core.visuals import Visuals

router = Router(name="trade")
logger = logging.getLogger(__name__)


async def safe_edit_msg(message: Message, text: str, reply_markup=None):
    try:
        if message.text != text:
            await message.edit_text(text, parse_mode="HTML", reply_markup=reply_markup)
    except Exception:
        pass


@router.message(Command("senseitrade", "trade"))
async def cmd_trade(message: Message, command: CommandObject, container: Container):
    """
    💹 Крипто-трейдинг симулятор.

    Usage:
        /trade [ставка]
    """
    if not message.from_user:
        return

    user_id = message.from_user.id
    username = message.from_user.username
    mention = f"@{username}" if username else f"<b>{html.escape(message.from_user.full_name)}</b>"

    if message.chat.type != ChatType.PRIVATE:
        await message.answer(f"{mention}\n\n⚠️ Трейдинг доступен только в личных сообщениях боту.", parse_mode="HTML")
        try:
            await message.delete()
        except Exception:
            pass
        return

    # 1. Parse bet
    bet = settings.trade_cost
    if command.args:
        try:
            bet_arg = int(command.args.strip())
            # Basic validation
            if bet_arg < 1:
                await message.answer(f"{mention}\n\n{Visuals.cross()} Ставка должна быть больше 0!", parse_mode="HTML")
                return
            bet = bet_arg
        except ValueError:
            await message.answer(f"{mention}\n\n{Visuals.cross()} Неверный формат ставки! Используй: /trade 100", parse_mode="HTML")
            return

    # Delete user command message
    try:
        await message.delete()
    except Exception:
        pass

    # 2. Play Game (Atomic via Service)
    result = await container.trade_service.play_game(user_id, bet)
    
    if not result["success"]:
        if result.get("error") == "rate_limit":
            await message.answer(f"{mention}\n\n⏳ Подожди {result.get('ttl')} сек...", parse_mode="HTML")
        else:
            await message.answer(f"{mention}\n\n{result.get('error', 'Произошла ошибка')}", parse_mode="HTML")
        return

    # 3. Animation
    await container.message_cleanup_service.cleanup_previous(message.chat.id, user_id, "trade", message.bot)
    
    direction = "long" if random.random() < 0.5 else "short"
    
    sent_message = None
    try:
        frames = Visuals.get_trade_animation(username="")
        sent_message = await message.answer(f"{frames[0]}\n{mention}", parse_mode="HTML")
        await container.message_cleanup_service.set_last(message.chat.id, user_id, "trade", sent_message.message_id)
        
        for frame in frames[1:]:
            await asyncio.sleep(1)
            await safe_edit_msg(sent_message, f"{frame}\n{mention}")
    except Exception as e:
        logger.error(f"Animation error: {e}")

    # 4. Show Result (using data from service)
    result_text = Visuals.get_trade_result(
        direction=direction,
        is_win=result["is_win"],
        profit=result["profit"],
        remaining_coins=result["balance"],
        bet=result["bet"],
        fee=result["fee"],
        username=""
    )
    result_text += f"\n\n🧾 Комиссия: {result['fee']} (5%) | Рабочая ставка: {result['bet'] - result['fee']}"
    
    final_text = f"{result_text}\n{mention}"

    if sent_message:
        await safe_edit_msg(sent_message, final_text)
    else:
        msg = await message.answer(final_text, parse_mode="HTML")
        await container.message_cleanup_service.set_last(message.chat.id, user_id, "trade", msg.message_id)
