"""
💬 Обработчики триггеров в сообщениях.
"""

import re
import random
import html
import logging
import time
from aiogram import Router, F
from aiogram.types import Message, ReactionTypeEmoji
from aiogram.exceptions import TelegramBadRequest
from src.bot.filters import PrivateChatFilter

from src.core.container import Container
from src.core.constants import RANDOM_MESSAGE_CHANCE
from src.core.exceptions import DailyAlreadyClaimedError
from src.core.visuals import Visuals
from src.texts.phrases import get_random_phrase, check_easter_egg, get_random_pour_phrase, ERROR_COOLDOWN

router = Router(name="triggers")

# Cooldown storage
pour_cooldowns = {}


# Паттерны для триггеров
SENSEI_PATTERN = re.compile(r'\b(сенсей|сэнсей|сэнсэй|sensei)\b', re.IGNORECASE)
POUR_PATTERN = re.compile(r'(сенсей\s+(наливай|налей|давай\s+наливай))', re.IGNORECASE)
DAILY_PATTERN = re.compile(r'\b(ежа|фарма)\b', re.IGNORECASE)
HELP_PATTERN = re.compile(r'(сенсей\s*(помо[гщ]и|помощь)|ℹ️ Помощь)', re.IGNORECASE)

CRYPTO_TOP_PATTERN = re.compile(r'(сенсей\s+дай\s+курс|📊 CoinGecko|💹 CoinCap|🔶 Binance|📈 Сравнить)', re.IGNORECASE)
CRYPTO_CALC_PATTERN = re.compile(r'курс\s+№\s*([a-zA-Z0-9]+)\s*№\s*([\d\.,]+)', re.IGNORECASE)
CRYPTO_AMOUNT_PATTERN = re.compile(r'курс\s+(\d+(?:[.,]\d+)?)\s+([a-zA-Z0-9]+)', re.IGNORECASE)
CRYPTO_PRICE_PATTERN = re.compile(r'курс\s+([a-zA-Z0-9]+)', re.IGNORECASE)
SAGE_QUESTION_PATTERN = re.compile(r'мудрец\s+сенсей\s+(.+)', re.IGNORECASE)
VANGA_PATTERN = re.compile(r'(сенсей\s+вангуй)', re.IGNORECASE)


@router.message(F.text.regexp(HELP_PATTERN))
async def trigger_help(message: Message):
    """Триггер на 'сенсей помоги/помощь'."""
    if message.text == "ℹ️ Помощь" and message.chat.type != "private":
        return
    
    text = Visuals.help_card()
    await message.answer(text, parse_mode="HTML")


@router.message(F.text.regexp(POUR_PATTERN))
async def trigger_pour(message: Message, container: Container):
    """Триггер на 'сенсей наливай'."""
    # Cooldown check
    chat_id = message.chat.id
    current_time = time.time()
    last_time = pour_cooldowns.get(chat_id, 0)
    
    if current_time - last_time < 4:
        remaining = int(4 - (current_time - last_time))
        if remaining < 1: remaining = 1
        await message.answer(ERROR_COOLDOWN.format(seconds=remaining))
        return

    pour_cooldowns[chat_id] = current_time

    user_data = await container.user_service.get_random_user()
    
    if not user_data:
        await message.answer("В додзё пусто... Некому налить. 😔")
        return
        
    phrase = get_random_pour_phrase()
    
    # Формируем упоминание
    if user_data["username"]:
        mention = f"@{user_data['username']}"
    else:
        name = user_data["first_name"]
        mention = f'<a href="tg://user?id={user_data["id"]}">{name}</a>'
        
    await message.answer(f"{mention}, {phrase}", parse_mode="HTML")


@router.message(F.text.regexp(DAILY_PATTERN))
async def trigger_daily(message: Message, container: Container):
    """Триггер на 'ежа/фарма'."""
    if not message.from_user:
        return

    # Delete trigger message
    try:
        await message.delete()
    except TelegramBadRequest:
        pass
    except Exception as e:
        logging.warning(f"⚠️ Failed to delete trigger message in trigger_daily: {e}")
    
    try:
        result = await container.daily_service.claim_daily(
            user_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name or "",
            is_bot=message.from_user.is_bot or False
        )
        
        if result["success"]:
            username = message.from_user.username
            mention = f"@{username}" if username else f"<b>{message.from_user.full_name}</b>"
            
            card = Visuals.daily_reward(
                xp=result["xp"],
                coins=result["coins"],
                streak=result["streak"],
                bonus_xp=result["bonus_xp"],
                bonus_coins=result["bonus_coins"],
            )
            await message.answer(f"{mention}\n\n{card}", parse_mode="HTML")
    
    except DailyAlreadyClaimedError as e:
        username = message.from_user.username
        mention = f"@{username}" if username else f"<b>{html.escape(message.from_user.full_name)}</b>"
        await message.answer(
            f"{mention}\n\n"
            f"⏰ Бонус уже получен!\nСледующий: {e.next_claim_time}",
            parse_mode="HTML"
        )


@router.message(F.text.regexp(CRYPTO_TOP_PATTERN))
async def trigger_crypto_top(message: Message, container: Container):
    """Триггер на 'сенсей дай курс'."""
    text = await container.crypto_service.get_top_10_message()
    await message.answer(text, parse_mode="HTML")


@router.message(F.text.regexp(CRYPTO_CALC_PATTERN))
async def trigger_crypto_calc(message: Message, container: Container):
    """Триггер на 'курс № TON № 100'."""
    if not message.text:
        return
        
    match = CRYPTO_CALC_PATTERN.search(message.text)
    if not match:
        return

    symbol = match.group(1)
    amount_str = match.group(2).replace(',', '.')
    
    try:
        amount = float(amount_str)
        text = await container.crypto_service.get_calculator_message(symbol, amount)
        await message.answer(text, parse_mode="HTML")
    except ValueError:
        await message.answer("❌ Некорректное число.")


@router.message(F.text.regexp(CRYPTO_AMOUNT_PATTERN))
async def trigger_crypto_amount(message: Message, container: Container):
    """Триггер на 'курс 123 TON'."""
    if not message.text:
        return
        
    match = CRYPTO_AMOUNT_PATTERN.search(message.text)
    if not match:
        return

    amount_str = match.group(1).replace(',', '.')
    symbol = match.group(2)
    
    try:
        amount = float(amount_str)
        text = await container.crypto_service.get_calculator_message(symbol, amount)
        await message.answer(text, parse_mode="HTML")
    except ValueError:
        await message.answer("❌ Некорректное число.")


@router.message(F.text.regexp(CRYPTO_PRICE_PATTERN))
async def trigger_crypto_price(message: Message, container: Container):
    """Триггер на 'курс TON/BTC'."""
    if not message.text:
        return
    
    match = CRYPTO_PRICE_PATTERN.search(message.text)
    if not match:
        return
        
    symbol = match.group(1)
    
    # Игнорируем если это часть калькулятора (хотя порядок роутеров должен решать, но на всякий случай)
    if "№" in message.text:
        return

    text = await container.crypto_service.get_price_message(symbol)
    await message.answer(text, parse_mode="HTML")


@router.message(F.text.regexp(SAGE_QUESTION_PATTERN))
async def trigger_sage_question(message: Message, container: Container):
    """Триггер на 'мудрец сенсей [вопрос]'."""
    if not message.text:
        return
        
    match = SAGE_QUESTION_PATTERN.search(message.text)
    if not match:
        return

    question = match.group(1)
    
    # Отправляем "печатает..."
    await message.bot.send_chat_action(message.chat.id, "typing")
    
    try:
        answer = await container.digest_service.ask_sage(question)
        # Gemini возвращает Markdown, но без экранирования для V2 это опасно.
        # Используем обычный текст или пробуем Markdown, если уверены.
        # Для безопасности пока оставим без parse_mode или Markdown
        await message.reply(answer) 
    except Exception as e:
        logging.error(f"Sage error: {e}")
        await message.reply("🧘‍♂️ Сенсей ушел в астрал. Попробуй позже.")


@router.message(F.text.regexp(VANGA_PATTERN))
async def trigger_vanga(message: Message, container: Container):
    """Триггер на 'сенсей вангуй'."""
    # Проверяем, просит ли пользователь предсказание для себя
    is_me = re.search(r'\bмне\b', message.text, re.IGNORECASE)
    
    if is_me:
        # Используем данные отправителя
        user = message.from_user
        user_data = {
            "username": user.username,
            "first_name": user.first_name,
            "id": user.id
        }
    else:
        # Получаем случайного пользователя
        user_data = await container.user_service.get_random_user()
    
    if not user_data:
        await message.answer("В додзё пусто... Некому гадать. 😔")
        return
        
    # Формируем имя для промпта
    if user_data["username"]:
        username = f"@{user_data['username']}"
    else:
        username = user_data["first_name"]
        
    # Отправляем "печатает..."
    await message.bot.send_chat_action(message.chat.id, "typing")
    
    try:
        prediction = await container.digest_service.get_vanga_prediction(username)
        
        # Формируем упоминание для ответа
        if user_data["username"]:
            mention = f"@{user_data['username']}"
        else:
            name = html.escape(user_data["first_name"])
            mention = f'<a href="tg://user?id={user_data["id"]}">{name}</a>'
            
        await message.reply(f"{mention}, {prediction}", parse_mode="HTML")
    except Exception as e:
        logging.error(f"Vanga error: {e}")
        await message.reply("🔮 Шар судьбы треснул. Попробуй позже.")


@router.message(F.text.regexp(SENSEI_PATTERN))
async def trigger_sensei(message: Message):
    """Триггер на 'сенсей'."""
    if not message.text:
        return
    
    text = message.text.lower()
    
    # Пропускаем если это помощь или курс
    if "помо" in text or "курс" in text:
        return
    
    phrase = get_random_phrase()
    await message.answer(phrase, parse_mode="HTML")


@router.message(F.text.func(lambda text: text and check_easter_egg(text) is not None))
async def check_easter_eggs_handler(message: Message):
    """Проверка на пасхалки."""
    response = check_easter_egg(message.text)
    if response:
        await message.answer(response, parse_mode="HTML")



@router.message()
async def catch_all_message(message: Message):
    """
    Catch-all handler для отслеживания активности.
    Позволяет UserActivityMiddleware начислить награду за любое сообщение.
    Также с шансом 0.02% отправляет случайную фразу,
    и с шансом 1% ставит реакцию (👍 или ❤).
    """
    # Debug logging to identify unhandled commands
    text_repr = repr(message.text) if message.text else "None"
    logging.info(f"⚠️ [CATCH_ALL] Unhandled message: {text_repr} from {message.from_user.id}")

    # 1. Реакция с шансом 1%
    if random.random() < 0.08:
        try:
            reaction = random.choice(["👍", "❤", "😂", "😆", "😮", "😲", "🤔", "🤨"])
            await message.react([ReactionTypeEmoji(emoji=reaction)])
        except Exception as e:
            logging.debug(f"⚠️ Failed to set reaction: {e}")

    # 2. Случайная фраза (очень редкая)
    if random.random() < RANDOM_MESSAGE_CHANCE:
        phrase = get_random_phrase()
        await message.answer(phrase, parse_mode="HTML")
