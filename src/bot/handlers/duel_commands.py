import html
import re
import logging

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest

from src.core.container import Container
from src.services.duel_resources import DuelDecisionCb, DuelMoveCb, DuelSurrenderCb, DuelUtilityCb

logger = logging.getLogger(__name__)
router = Router()

from src.bot.utils import check_owner

def make_decision_kb(duel_id: int, challenger_id: int, opponent_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Принять ⚔️", callback_data=DuelDecisionCb(id=duel_id, d="a", c=challenger_id, o=opponent_id).pack()),
        InlineKeyboardButton(text="Отклонить ❌", callback_data=DuelDecisionCb(id=duel_id, d="x", c=challenger_id, o=opponent_id).pack()),
    ]])

@router.message(F.reply_to_message & F.text.regexp(r"сенсей\s+дуэль(?:\s+(?:№\s*)?(\d+))?", flags=re.IGNORECASE))
async def text_duel(message: Message, container: Container, bot: Bot):
    """
    Обработчик текстовой команды вызова на дуэль (regex).
    Пример: "сенсей дуэль 100" или "сенсей дуэль" (ставка 0).
    """
    m = re.search(r"сенсей\s+дуэль(?:\s+(?:№\s*)?(\d+))?", message.text or "", re.IGNORECASE)
    
    bet = 0
    if m and m.group(1):
        try:
            bet = int(m.group(1))
        except ValueError:
            await message.answer("❌ Некорректная ставка.")
            return

    await cmd_duel(message, container, bot, bet=bet)

@router.message(Command("duel", "senseiduel"))
async def cmd_duel(message: Message, container: Container, bot: Bot, bet: int = None):
    user_id = message.from_user.id
    username = message.from_user.username
    mention = f"@{username}" if username else f"<b>{html.escape(message.from_user.full_name)}</b>"
    
    # Parse bet if not provided
    if bet is None:
        args = message.text.split()
        if len(args) > 1:
            try:
                bet = int(args[1])
            except ValueError:
                await message.answer(f"{mention}\n\n❌ Ставка должна быть числом.\nПример: /duel 100", parse_mode="HTML")
                return
        else:
            bet = 0 # Default bet

    if bet < 0:
        await message.answer(f"{mention}\n\n❌ Ставка не может быть отрицательной.", parse_mode="HTML")
        return

    # Check reply
    if not message.reply_to_message or not message.reply_to_message.from_user:
        await message.answer(f"{mention}\n\n❌ Ответь на сообщение того, кого хочешь вызвать на дуэль!", parse_mode="HTML")
        return

    opponent = message.reply_to_message.from_user
    if opponent.id == user_id:
        await message.answer(f"{mention}\n\n❌ Бить себя — это странно. Сходи к психологу.", parse_mode="HTML")
        return
    if opponent.is_bot:
        await message.answer(f"{mention}\n\n❌ Я не дерусь с коллегами. (И с другими ботами тоже).", parse_mode="HTML")
        return

    # Check database info
    user = await container.user_service.get_profile(user_id)
    opp_user = await container.user_service.get_profile(opponent.id)

    if not user:
        await message.answer(f"{mention}\n\n❌ Ты не зарегистрирован. Напиши что-нибудь в чат.", parse_mode="HTML")
        return
    if not opp_user:
        await message.answer(f"{mention}\n\n❌ Оппонент не зарегистрирован.", parse_mode="HTML")
        return
        
    # Check eligibility (using internal method or service helper)
    # The service now does checks inside create_duel mostly, but we can do a quick check if exposed.
    # Service create_duel returns string on error.
    
    # Create duel
    try:
        result = await container.duel_service.create_duel(
            challenger_id=user_id,
            opponent_id=opponent.id,
            bet=bet,
            chat_id=message.chat.id,
            bot=bot
        )
        
        if isinstance(result, str):
            # Error message
            await message.answer(f"{mention}\n\n{result}", parse_mode="HTML")
            return
            
        duel = result
        
    except Exception as e:
        logger.error(f"Error creating duel: {e}", exc_info=True)
        await message.answer(f"{mention}\n\n❌ Ошибка при создании дуэли: {html.escape(str(e))}", parse_mode="HTML")
        return
    
    opp_username = opponent.username
    opp_mention = f"@{opp_username}" if opp_username else f"<b>{html.escape(opponent.full_name)}</b>"

    # Send challenge
    try:
        msg = await message.answer(
            f"{mention}\n\n"
            f"⚔️ <b>ВЫЗОВ НА ДУЭЛЬ!</b>\n"
            f"{mention} вызывает {opp_mention}!\n"
            f"💰 Ставка: <b>{bet}</b> монет\n"
            f"⏳ Есть 120 секунд на принятие решения.",
            reply_markup=make_decision_kb(duel.id, user_id, opponent.id),
            parse_mode="HTML"
        )
        duel.challenge_message_id = msg.message_id
    except Exception as e:
        logger.error(f"Failed to send challenge: {e}")
        await message.answer("❌ Не удалось отправить вызов.")


@router.callback_query(DuelDecisionCb.filter())
async def on_duel_decision(query: CallbackQuery, callback_data: DuelDecisionCb, container: Container):
    # Determine who is clicking
    user_id = query.from_user.id
    
    is_opponent = (user_id == callback_data.o)
    is_challenger = (user_id == callback_data.c)

    # 1. 'a' (Accept) -> Only Opponent
    if callback_data.d == 'a':
        if not is_opponent:
            await query.answer("⛔ Принять вызов может только тот, кого вызвали!", show_alert=True)
            return

    # 2. 'x' (Decline/Cancel) -> Opponent OR Challenger
    elif callback_data.d == 'x':
        if not (is_opponent or is_challenger):
             await query.answer("⛔ Это не твой вызов!", show_alert=True)
             return
    
    # 3. Process
    try:
        res = await container.duel_service.process_decision(
            duel_id=callback_data.id,
            user_id=query.from_user.id,
            decision=callback_data.d
        )
        await query.answer(res)
    except Exception as e:
        logger.error(f"Decision error: {e}")
        await query.answer("❌ Ошибка обработки.", show_alert=True)


@router.callback_query(DuelMoveCb.filter())
async def on_duel_move(query: CallbackQuery, callback_data: DuelMoveCb, container: Container):
    """
    Обработчик ходов в дуэли (атака/защита).
    """
    if query.from_user.id != callback_data.u:
        await query.answer("⛔ Это не твой ход!", show_alert=True)
        return

    try:
        res = await container.duel_service.process_move(
            duel_id=callback_data.id,
            user_id=query.from_user.id,
            move=callback_data.m
        )
        await query.answer(res)
    except Exception as e:
        logger.error(f"Move error: {e}")
        await query.answer("❌ Ошибка хода.", show_alert=True)

@router.callback_query(DuelSurrenderCb.filter())
async def on_duel_surrender(query: CallbackQuery, callback_data: DuelSurrenderCb, container: Container):
    """
    Сдача в дуэли.
    """
    if query.from_user.id != callback_data.u:
        try:
            await query.answer("⛔ Эта кнопка не для тебя!", show_alert=True)
        except TelegramBadRequest:
            pass
        return

    try:
        res = await container.duel_service.surrender(
            duel_id=callback_data.id,
            user_id=query.from_user.id
        )
        try:
            await query.answer(res)
        except TelegramBadRequest:
            pass
    except Exception as e:
        logger.error(f"Surrender error: {e}")
        try:
            await query.answer("❌ Ошибка сдачи.", show_alert=True)
        except TelegramBadRequest:
            pass

@router.callback_query(DuelUtilityCb.filter())
async def on_duel_utility(query: CallbackQuery, callback_data: DuelUtilityCb, container: Container):
    """
    Утилитарные кнопки: автоход, сброс, управление.
    """
    # If u is specified and not 0, check it matches
    if callback_data.u != 0 and query.from_user.id != callback_data.u:
        await query.answer("⛔ Не для тебя.", show_alert=True)
        return

    try:
        res = await container.duel_service.process_utility(
            duel_id=callback_data.id,
            user_id=query.from_user.id,
            action=callback_data.a
        )
        await query.answer(res)
    except Exception as e:
        logger.error(f"Utility error: {e}")
        await query.answer("❌ Ошибка.", show_alert=True)
