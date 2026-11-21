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
                await message.answer(f"{mention}\n\n❌ Ставка должна быть числом.\nПример: /duel 300", parse_mode="HTML")
                return
        else:
            bet = 0 # Default bet

    if bet < 300:
        await message.answer(f"{mention}\n\n❌ Минимальная ставка — 300 Coin.", parse_mode="HTML")
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
            bot=bot,
            request_id=f'{message.chat.id}:{message.message_id}'
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


@router.callback_query(F.data.startswith('vs:'))
async def accept_dojo_challenge(query: CallbackQuery, container: Container, bot: Bot):
    import time
    match = re.fullmatch(r'vs:(\d{1,19}):([a-f0-9]{24})', query.data or '')
    if not match or not query.message or query.from_user.is_bot:
        return await query.answer('Недоступный вызов.')
    uid, token = int(match[1]), match[2]
    opponent = query.from_user.id
    if uid == opponent:
        return await query.answer('Ожидаем другого игрока.')
    db = container.mongo_client.database
    offers = db.dojo_duel_offers
    key = {'_id': uid, 'token': token, 'chat': query.message.chat.id,
           'status': 'open', 'expires': {'$gt': time.time()}}
    offer = await offers.find_one(key)
    if not offer:
        return await query.answer('Вызов занят или истёк.')
    if offer.get('rival') not in (None, opponent):
        return await query.answer('Это персональный вызов другому игроку.')
    player = await db.users.find_one({'id': opponent, 'is_banned': {'$ne': True}})
    if not player or player.get('coins', 0) < offer['bet']:
        return await query.answer('Открой /start и проверь баланс для ставки.', show_alert=True)
    if offer['chat'] > 0 and (not player.get('has_katana') or player.get('coins', 0) <= 0):
        return await query.answer('Для личной дуэли нужны катана и положительный баланс Coin.', show_alert=True)
    if container.duel_service._is_in_active_duel(opponent):
        return await query.answer('Сначала заверши свою дуэль.')
    key['expires'] = {'$gt': time.time()}
    locked = await offers.update_one(key, {'$set': {'status': 'joining'}})
    if not locked.matched_count:
        return await query.answer('Вызов занят или истёк.')
    await query.answer('Открой /dojo → VS. На подключение — 2 минуты.', show_alert=True)
    result = await container.duel_service.create_duel(uid, opponent, offer['bet'], offer['chat'], bot,
                                                       request_id=f'dojo:{token}')
    if isinstance(result, str):
        await offers.update_one({'_id': uid, 'token': token}, {'$set': {'status': 'closed'}})
        return await query.message.edit_text(result, parse_mode=None)
    result.dojo_only = True
    result.challenge_message_id = query.message.message_id
    await container.duel_service.process_decision(result.id, opponent, 'a')
    await offers.update_one({'_id': uid, 'token': token}, {'$set': {'status': 'closed'}})


@router.inline_query(F.query.startswith('dojo_vs '))
async def inline_duel(query, container: Container, bot: Bot):
    """The Telegram chooser supplies chat type, never a recipient's user ID."""
    import secrets
    import time
    from aiogram.types import InlineQueryResultArticle, InputTextMessageContent
    from pymongo.errors import DuplicateKeyError
    match = re.fullmatch(r'dojo_vs ([0-9]{1,16})', query.query)
    uid = query.from_user.id
    bet = int(match[1]) if match else 0
    db = container.mongo_client.database
    results = []
    if (300 <= bet <= 2**53-1 and query.chat_type in ('private', 'group', 'supergroup') and
            not container.duel_service._is_in_active_duel(uid) and await db.users.find_one(
                {'id': uid, 'is_banned': {'$ne': True}, 'coins': {'$gte': bet}})):
        token = secrets.token_hex(12)
        now = time.time()
        try:
            await db.dojo_duel_offers.update_one({'_id': uid, '$or': [{'expires': {'$lte': now}},
                {'status': {'$in': ['draft', 'closed']}}]}, {'$set': dict(status='draft', token=token,
                bet=bet, expires=now+120, title='Вызов в Telegram', chat=0, inline_private=query.chat_type=='private',
                rival=None, rematch=None, inline_arena=None, message_id=None)}, upsert=True)
        except DuplicateKeyError:
            pass  # An already published challenge cannot be replaced by a preview.
        else:
            url = f'https://t.me/{(await bot.me()).username}?startapp=vs_{uid}_{token}'
            title = f'⚔️ Отправить дуэль · {bet} Coin'
            results.append(InlineQueryResultArticle(id=f'vs_{token}', title=title,
                input_message_content=InputTextMessageContent(message_text=f'{query.from_user.full_name} вызывает на дуэль! Ставка каждого: {bet} Coin. Принять за 2 минуты.', parse_mode=None),
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Открыть дуэль', url=url)]])))
    await query.answer(results, cache_time=0, is_personal=True)


@router.chosen_inline_result(F.result_id.startswith('vs_'))
async def sent_inline_duel(chosen, container: Container):
    import time
    if not chosen.inline_message_id:
        return
    now = time.time()
    await container.mongo_client.database.dojo_duel_offers.update_one(
        {'_id': chosen.from_user.id, 'token': chosen.result_id[3:], 'status': 'draft', 'expires': {'$gt': now}},
        {'$set': {'status': 'open', 'expires': now+120, 'inline_arena': chosen.inline_message_id}})
