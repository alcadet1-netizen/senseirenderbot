"""
🎰 Рулетка Актива (Chat Roulette) v2.0 - УЛУЧШЕННАЯ!

Команда: /senseiroulette
- Анимация вращения рулетки
- Случайная награда (от 500 до 5000 монет!)
- Джекпот x5 (редкий шанс)
- Таймер с обратным отсчетом
- История последних победителей

Эффект: люди следят за чатом, чтобы не пропустить свой шанс!
"""

import asyncio
import html
import logging
import random
import time
from typing import Optional, Set, List, Dict

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest

from src.core.config import settings
from src.core.container import Container
from src.core.visuals import Visuals

router = Router(name="roulette")
logger = logging.getLogger(__name__)

# === Константы ===
ROULETTE_MIN_REWARD = 200      # Минимальная награда
ROULETTE_MAX_REWARD = 2000     # Максимальная награда
ROULETTE_JACKPOT_MULT = 5      # Множитель джекпота
ROULETTE_JACKPOT_CHANCE = 0.05 # Шанс джекпота (5%)
ROULETTE_TIMEOUT = 65          # Секунд на ответ (уменьшено для азарта!)
ROULETTE_COOLDOWN = 180        # Кулдаун между рулетками (3 минуты)
ROULETTE_ACTIVE_HOURS = 48     # За какой период искать активных
ROULETTE_SPIN_DURATION = 3     # Секунды анимации вращения

# Эмодзи для анимации
PREMIUM_EMOJIS = {
    "lightning": [
        '<tg-emoji emoji-id="5318921223449623508">⚡️</tg-emoji>',
        '<tg-emoji emoji-id="5215356457997837659">⚡️</tg-emoji>',
        '<tg-emoji emoji-id="5449665242030165868">⚡️</tg-emoji>',
        '<tg-emoji emoji-id="5431449001532594346">⚡️</tg-emoji>',
        '<tg-emoji emoji-id="5364098734600762220">⚡️</tg-emoji>',
        '<tg-emoji emoji-id="5199785165735367039">⚡️</tg-emoji>',
        '<tg-emoji emoji-id="5373066076558996568">⚡</tg-emoji>',
        '<tg-emoji emoji-id="5219943216781995020">⚡</tg-emoji>'
    ],
    "warning": [
        '<tg-emoji emoji-id="5264841061137683683">⚠️</tg-emoji>',
        '<tg-emoji emoji-id="5213205860498549992">⚠️</tg-emoji>',
        '<tg-emoji emoji-id="5212988801441344587">⚠️</tg-emoji>',
        '<tg-emoji emoji-id="5213336479043955543">⚠️</tg-emoji>',
        '<tg-emoji emoji-id="5215305227627931680">⚠️</tg-emoji>'
    ],
    "fire": [Visuals.fire_raw() for _ in range(4)],
    "circles": [
        '<tg-emoji emoji-id="5363897579807455575">🟡</tg-emoji>',
        '<tg-emoji emoji-id="5802982471708445914">🟢</tg-emoji>'
    ],
    "money": [
        '<tg-emoji emoji-id="5832384984593206481">💰</tg-emoji>',
        '<tg-emoji emoji-id="5318912792428814144">💰</tg-emoji>'
    ],
    "refresh": [
        '<tg-emoji emoji-id="5292226786229236118">🔄</tg-emoji>',
        '<tg-emoji emoji-id="5452002073606384268">🔄</tg-emoji>',
        '<tg-emoji emoji-id="5226702984204797593">🔄</tg-emoji>'
    ],
    "target": [
        '<tg-emoji emoji-id="5310278924616356636">🎯</tg-emoji>',
        '<tg-emoji emoji-id="5256131095094652290">🎯</tg-emoji>'
    ],
    "memo": [
        '<tg-emoji emoji-id="5215672443036772796">📝</tg-emoji>'
    ],
    "slots": [
        '<tg-emoji emoji-id="5954154471440257880">🎰</tg-emoji>',
        '<tg-emoji emoji-id="5976285042052175114">🎰</tg-emoji>'
    ],
    "party": [
        '<tg-emoji emoji-id="5316778159322963296">🎉</tg-emoji>',
        '<tg-emoji emoji-id="5461151367559141950">🎉</tg-emoji>',
        '<tg-emoji emoji-id="5215628200578655810">🎉</tg-emoji>',
        '<tg-emoji emoji-id="5215338925941340477">🎉</tg-emoji>'
    ],
    "check": [
        '<tg-emoji emoji-id="5213406375341731253">✅</tg-emoji>',
        '<tg-emoji emoji-id="5454096630372379732">☑️</tg-emoji>',
        '<tg-emoji emoji-id="5213292515758713570">✅</tg-emoji>',
        '<tg-emoji emoji-id="5215326869968136718">✅</tg-emoji>',
        '<tg-emoji emoji-id="5213302802205387293">✅</tg-emoji>',
        '<tg-emoji emoji-id="5316906020499365122">✔️</tg-emoji>',
        '<tg-emoji emoji-id="5429381339851796035">✅</tg-emoji>',
        '<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji>',
        '<tg-emoji emoji-id="5206607081334906820">☑️</tg-emoji>',
        '<tg-emoji emoji-id="5212932275376759608">✅</tg-emoji>',
        '<tg-emoji emoji-id="4985566589446259538">✅</tg-emoji>',
        '<tg-emoji emoji-id="4983339627428446834">✅</tg-emoji>'
    ],
    "clock": [
        '<tg-emoji emoji-id="5267421370114914946">⏱️</tg-emoji>',
        '<tg-emoji emoji-id="5260469398610657764">⏰</tg-emoji>',
        '<tg-emoji emoji-id="5373236586760651455">⏱</tg-emoji>'
    ],
    "trophy": [
        '<tg-emoji emoji-id="5462927083132970373">🏆</tg-emoji>',
        '<tg-emoji emoji-id="5332547853304734597">🎖</tg-emoji>'
    ],
    "1st": ['<tg-emoji emoji-id="5440539497383087970">🥇</tg-emoji>'],
    "2nd": ['<tg-emoji emoji-id="5447203607294265305">🥈</tg-emoji>'],
    "3rd": ['<tg-emoji emoji-id="5453902265922376865">🥉</tg-emoji>'],
    "jackpot": ['💎', '<tg-emoji emoji-id="5215568478957738228">💎</tg-emoji>'], # Standard + placeholder, user didn't give distinct premium jewel, using standard for now or mixing
    "sad": [
        '<tg-emoji emoji-id="5265244397221482932">😢</tg-emoji>',
        '<tg-emoji emoji-id="5323791480140079318">😢</tg-emoji>',
        '<tg-emoji emoji-id="5886662779825294115">😔</tg-emoji>',
        '<tg-emoji emoji-id="5197226061011623665">😕</tg-emoji>',
        '<tg-emoji emoji-id="5983380877780980112">😢</tg-emoji>',
        '<tg-emoji emoji-id="5891061328847572896">😔</tg-emoji>',
        '<tg-emoji emoji-id="5168323551039587146">😥</tg-emoji>',
        '<tg-emoji emoji-id="5325829592445887585">😢</tg-emoji>',
        '<tg-emoji emoji-id="5197385314103992580">😓</tg-emoji>',
        '<tg-emoji emoji-id="5456377060438056899">😔</tg-emoji>'
    ]
}

def _get_random_emoji(category: str) -> str:
    """Возвращает случайный премиум эмодзи из категории."""
    if category in PREMIUM_EMOJIS:
        return random.choice(PREMIUM_EMOJIS[category])
    return ""

SPIN_FRAMES = PREMIUM_EMOJIS["slots"]
SLOT_SYMBOLS = [
    '<tg-emoji emoji-id="5321272430281374718">🍒</tg-emoji>',
    '<tg-emoji emoji-id="5318758551563288909">🍋</tg-emoji>',
    '<tg-emoji emoji-id="5321073053604527685">🍇</tg-emoji>',
    '<tg-emoji emoji-id="5318902012060909021">🍉</tg-emoji>',
    '<tg-emoji emoji-id="5319104738812247312">⭐</tg-emoji>',
    '<tg-emoji emoji-id="5321135974875413234">🔔</tg-emoji>'
]

# Хранилище активных рулеток
_active_roulettes: Dict[int, dict] = {}

# Хранилище кулдаунов
_roulette_cooldowns: Dict[int, float] = {}

# История победителей (последние 5 на чат)
_roulette_history: Dict[int, List[dict]] = {}


class HasActiveRoulette:
    """Filter: only matches if there's an active roulette in this chat."""
    def __call__(self, message) -> bool:
        return message.chat.id in _active_roulettes


def _get_random_reward() -> tuple[int, bool]:
    """Генерирует случайную награду. Возвращает (сумма, is_jackpot)."""
    is_jackpot = random.random() < ROULETTE_JACKPOT_CHANCE
    base_reward = random.randint(ROULETTE_MIN_REWARD, ROULETTE_MAX_REWARD)
    
    if is_jackpot:
        return base_reward * ROULETTE_JACKPOT_MULT, True
    return base_reward, False


def _get_user_mention(user_id: int, username: Optional[str], first_name: str = "") -> str:
    """Создает упоминание пользователя."""
    if username:
        return f"@{username}"
    if first_name:
        return f'<a href="tg://user?id={user_id}">{html.escape(first_name)}</a>'
    return f'<a href="tg://user?id={user_id}">Участник #{str(user_id)[-4:]}</a>'


def _generate_slot_line() -> str:
    """Генерирует линию слотов (фиксированные 6 символов)."""
    return "".join(SLOT_SYMBOLS)


def _build_spinning_message(frame: int) -> str:
    """Создает сообщение анимации вращения."""
    emoji = _get_random_emoji("slots")
    refresh = _get_random_emoji("refresh")
    slots = _generate_slot_line()
    dots = "●" * ((frame % 3) + 1) + "○" * (3 - (frame % 3))
    
    return (
        f"{emoji} <b>КРУТИМ КОЛЕСО</b> {emoji}\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"   {slots}\n\n"
        f"  {refresh} <i>выбираем жертву...</i>\n\n"
        f"       {dots}"
    )


def _build_selected_message(mention: str, timeout: int, reward: int, is_jackpot: bool) -> str:
    """Создает сообщение о выбранном участнике."""
    reward_emoji = _get_random_emoji("jackpot") if is_jackpot else _get_random_emoji("money")
    target_emoji = _get_random_emoji("target")
    clock_emoji = _get_random_emoji("clock")
    memo_emoji = _get_random_emoji("memo")
    
    jackpot_block = ""
    if is_jackpot:
        jackpot_block = (
            "\n"
            f"{_get_random_emoji('fire') * 10}\n"
            f"   {_get_random_emoji('slots')} <b>ДЖЕКПОТ x5!</b> {_get_random_emoji('slots')}\n"
            f"{_get_random_emoji('fire') * 10}\n"
        )
    
    return (
        f"{target_emoji} <b>КОЛЕСО ОСТАНОВИЛОСЬ!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"{jackpot_block}\n"
        f"👤 <b>Выбран:</b> {mention}\n\n"
        f"{clock_emoji} Время: <b>{timeout}</b> секунд\n"
        f"{reward_emoji} Приз: <b>{reward:,}</b> монет\n\n"
        f"{memo_emoji} <b>НАПИШИ ЧТО УГОДНО</b>\n"
        f"     <i>чтобы забрать!</i>"
    )


def _build_countdown_message(mention: str, remaining: int, reward: int, is_jackpot: bool) -> str:
    """Создает сообщение с обратным отсчетом."""
    emoji = _get_random_emoji("slots")
    target_emoji = _get_random_emoji("target")
    memo_emoji = _get_random_emoji("memo")
    urgency = _get_random_emoji("circles")
    
    bar_filled = int((ROULETTE_TIMEOUT - remaining) / ROULETTE_TIMEOUT * 10)
    bar = "▓" * bar_filled + "░" * (10 - bar_filled)
    
    jackpot_emoji = _get_random_emoji("jackpot")
    jackpot_line = f"\n{jackpot_emoji} <b>ДЖЕКПОТ x5!</b>" if is_jackpot else ""
    
    return (
        f"{emoji} <b>КОЛЕСО АКТИВА</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"{target_emoji} {mention}{jackpot_line}\n\n"
        f"{urgency} <b>ОСТАЛОСЬ:</b> {remaining} сек\n"
        f"[{bar}]\n\n"
        f"{_get_random_emoji('money')} Приз: <b>{reward:,}</b>\n\n"
        f"{memo_emoji} <i>Пиши скорее!</i>"
    )


def _build_win_message(mention: str, reward: int, is_jackpot: bool, response_time: float) -> str:
    """Создает сообщение о победе."""
    slots_emoji = _get_random_emoji("slots")
    party_emoji = _get_random_emoji("party")
    trophy_emoji = _get_random_emoji("trophy")
    money_emoji = _get_random_emoji("money")
    clock_emoji = _get_random_emoji("clock")
    
    speed_text = f"{_get_random_emoji('lightning')} МОЛНИЕНОСНО!" if response_time < 5 else f"{_get_random_emoji('check')} Успел!"
    
    jackpot_block = ""
    if is_jackpot:
        jackpot_block = f"\n{_get_random_emoji('jackpot')} <b>ДЖЕКПОТ!</b> {_get_random_emoji('jackpot')}\n"
    
    return (
        f"{slots_emoji} <b>КОЛЕСО АКТИВА</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"{party_emoji} <b>ПОБЕДА!</b> {party_emoji}\n"
        f"{jackpot_block}\n"
        f"{trophy_emoji} {mention}\n"
        f"{money_emoji} <b>+{reward:,}</b> монет!\n\n"
        f"{speed_text}\n"
        f"{clock_emoji} Время: <b>{response_time:.1f}</b> сек"
    )


def _build_timeout_message(mention: str, reward: int, is_jackpot: bool) -> str:
    """Создает сообщение о таймауте."""
    slots_emoji = _get_random_emoji("slots")
    clock_emoji = _get_random_emoji("clock")
    
    jackpot_line = f"\n{_get_random_emoji('sad')} <b>Упущен ДЖЕКПОТ!</b>" if is_jackpot else ""
    
    return (
        f"{slots_emoji} <b>КОЛЕСО АКТИВА</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"{clock_emoji} <b>ВРЕМЯ ВЫШЛО!</b> {clock_emoji}\n\n"
        f"{_get_random_emoji('sad')} {mention}\n"
        f"<i>не успел ответить...</i>{jackpot_line}\n\n"
        f"💸 <b>{reward:,}</b> монет сгорели...\n\n"
        f"<i>В следующий раз!</i>"
    )


def _build_no_users_message() -> str:
    """Создает сообщение когда нет активных пользователей."""
    emoji = _get_random_emoji("slots")
    return (
        f"{emoji} <b>РУЛЕТКА АКТИВА</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"{_get_random_emoji('sad')} <b>Чат спит...</b>\n\n"
        f"Нет активных участников!\n\n"
        f"💬 Напишите в чат,\n"
        f"чтобы попасть\n"
        f"в следующую рулетку!"
    )


def _build_cooldown_message(remaining: int, history: List[dict]) -> str:
    """Создает сообщение о кулдауне с историей."""
    mins = remaining // 60
    secs = remaining % 60
    time_str = f"{mins}:{secs:02d}" if mins else f"{secs} сек"
    
    history_text = ""
    if history:
        history_text = f"\n\n{_get_random_emoji('trophy')} <b>Последние победители:</b>\n"
        for h in history[-3:]:
            name = h.get("name", "???")[:12]
            reward = h.get("reward", 0)
            jackpot = f"{_get_random_emoji('jackpot')} " if h.get("jackpot") else ""
            history_text += f"   {jackpot}{name}: <b>+{reward:,}</b>\n"
    
    return (
        f"{_get_random_emoji('slots')} <b>КОЛЕСО АКТИВА</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"⏳ <i>Колесо отдыхает</i>\n\n"
        f"{_get_random_emoji('clock')} До следующей: <b>{time_str}</b>"
        f"{history_text}"
    )


def _add_to_history(chat_id: int, name: str, reward: int, is_jackpot: bool):
    """Добавляет победителя в историю."""
    if chat_id not in _roulette_history:
        _roulette_history[chat_id] = []
    
    _roulette_history[chat_id].append({
        "name": name,
        "reward": reward,
        "jackpot": is_jackpot,
        "time": time.time()
    })
    
    # Храним только последние 10
    if len(_roulette_history[chat_id]) > 10:
        _roulette_history[chat_id] = _roulette_history[chat_id][-10:]


@router.message(Command("senseiroulette"))
async def cmd_senseiroulette(message: Message, container: Container):
    """🎰 Запустить рулетку актива (все пользователи с кулдауном)."""
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    # Проверяем, что это групповой чат
    if message.chat.type not in ("group", "supergroup"):
        await message.answer("🎰 Рулетка работает только в групповых чатах!")
        return
    
    # Определяем админ ли пользователь
    is_bot_admin = user_id in settings.admin_ids
    is_chat_admin = False
    
    if not is_bot_admin:
        try:
            member = await message.chat.get_member(user_id)
            is_chat_admin = member.status in ["creator", "administrator"]
        except Exception:
            is_chat_admin = False
    
    is_admin = is_bot_admin or is_chat_admin
    
    # Проверяем, нет ли уже активной рулетки
    if chat_id in _active_roulettes:
        roulette = _active_roulettes[chat_id]
        remaining = int(roulette["expires"] - time.time())
        if remaining > 0:
            winner_mention = _get_user_mention(
                roulette["user_id"],
                roulette.get("username"),
                roulette.get("first_name", "")
            )
            msg = _build_countdown_message(
                winner_mention, 
                remaining, 
                roulette["reward"],
                roulette.get("is_jackpot", False)
            )
            await message.answer(msg, parse_mode="HTML")
            return
    
    # === КУЛДАУН ===
    current_time = time.time()
    
    if is_admin:
        # Админы: кулдаун 5 минут на чат
        if chat_id in _roulette_cooldowns:
            cooldown_expires = _roulette_cooldowns[chat_id]
            if current_time < cooldown_expires:
                remaining = int(cooldown_expires - current_time)
                history = _roulette_history.get(chat_id, [])
                msg = _build_cooldown_message(remaining, history)
                await message.answer(msg, parse_mode="HTML")
                return
    else:
        # Обычные пользователи: персональный кулдаун 24 часа
        user_cooldown_key = f"roulette:user_cooldown:{chat_id}:{user_id}"
        ttl = await container.redis.ttl(user_cooldown_key)
        if ttl > 0:
            hours = ttl // 3600
            minutes = (ttl % 3600) // 60
            await message.answer(
                f'<tg-emoji emoji-id="5370680050427375727">⏲️</tg-emoji><tg-emoji emoji-id="5368441358853879381">⏲️</tg-emoji> <b>Подожди немного!</b>\n\n'
                f"Ты уже запускал колесо сегодня.\n"
                f"Следующий запуск через: <b>{hours}ч {minutes}мин</b>\n\n",
                parse_mode="HTML"
            )
            return
        
        # Устанавливаем персональный кулдаун 24 часа
        await container.redis.setex(user_cooldown_key, 86400, "1")
    
    # Получаем активных пользователей
    try:
        active_ids: Set[int] = await container.chat_activity_service.get_active_user_ids(
            chat_id, 
            since_hours=ROULETTE_ACTIVE_HOURS, 
            limit=500
        )
    except Exception as e:
        logger.exception(f"Ошибка получения активных пользователей: {e}")
        await message.answer(f"{Visuals.cross()} Ошибка при получении списка участников!")
        return
    
    # Исключаем ботов и админов
    exclude = set(settings.admin_ids) | {message.from_user.id}
    candidate_ids = list(active_ids - exclude)
    
    if not candidate_ids:
        msg = _build_no_users_message()
        await message.answer(msg, parse_mode="HTML")
        return
    
    # === АНИМАЦИЯ ВРАЩЕНИЯ ===
    spin_msg = await message.answer(
        _build_spinning_message(0),
        parse_mode="HTML"
    )
    
    # === ВЫБОР ПОБЕДИТЕЛЯ ===
    random.shuffle(candidate_ids)
    valid_candidates = []
    
    for uid in candidate_ids[:30]:
        try:
            member = await message.chat.get_member(uid)
            if member.status not in [ChatMemberStatus.LEFT, ChatMemberStatus.KICKED]:
                if not member.user.is_bot:
                    valid_candidates.append({
                        "user_id": uid,
                        "username": member.user.username,
                        "first_name": member.user.first_name or ""
                    })
        except Exception:
            continue
        
        if len(valid_candidates) >= 10:
            break
    
    if not valid_candidates:
        await spin_msg.edit_text(
            _build_no_users_message(),
            parse_mode="HTML"
        )
        return
    
    # Выбираем победителя
    winner = random.choice(valid_candidates)
    winner_id = winner["user_id"]
    winner_mention = _get_user_mention(
        winner_id, 
        winner.get("username"), 
        winner.get("first_name", "")
    )
    
    # Определяем награду
    reward, is_jackpot = _get_random_reward()
    
    # Показываем результат выбора
    selected_msg = _build_selected_message(winner_mention, ROULETTE_TIMEOUT, reward, is_jackpot)
    try:
        await spin_msg.edit_text(selected_msg, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Failed to edit roulette message: {e}")
        # Ensure we can still proceed even if visual update fails, or retry without HTML manually if custom_bot fails
        try:
            await spin_msg.edit_text(selected_msg, parse_mode=None)
        except Exception:
            pass
    
    # Сохраняем рулетку
    start_time = time.time()
    _active_roulettes[chat_id] = {
        "user_id": winner_id,
        "expires": start_time + ROULETTE_TIMEOUT,
        "start_time": start_time,
        "message_id": spin_msg.message_id,
        "username": winner.get("username"),
        "first_name": winner.get("first_name", ""),
        "reward": reward,
        "is_jackpot": is_jackpot,
        "container": container,
    }
    
    # Запускаем таймеры
    asyncio.create_task(_countdown_updater(message.bot, chat_id))
    asyncio.create_task(_roulette_timeout_handler(
        message.bot,
        chat_id,
        winner_id,
        winner_mention,
        spin_msg.message_id,
        reward,
        is_jackpot,
        container
    ))
    
    logger.info(f"🎰 Roulette started in {chat_id}: user {winner_id}, reward {reward}, jackpot={is_jackpot}")


async def _countdown_updater(bot: Bot, chat_id: int):
    """Обновляет обратный отсчет каждые 10 секунд."""
    update_intervals = [35, 25, 15, 10, 5]  # Моменты обновления
    
    for interval in update_intervals:
        await asyncio.sleep(10)
        
        if chat_id not in _active_roulettes:
            return
        
        roulette = _active_roulettes[chat_id]
        remaining = int(roulette["expires"] - time.time())
        
        if remaining <= 0:
            return
        
        winner_mention = _get_user_mention(
            roulette["user_id"],
            roulette.get("username"),
            roulette.get("first_name", "")
        )
        
        msg = _build_countdown_message(
            winner_mention,
            remaining,
            roulette["reward"],
            roulette.get("is_jackpot", False)
        )
        
        try:
            await bot.edit_message_text(
                msg,
                chat_id=chat_id,
                message_id=roulette["message_id"],
                parse_mode="HTML"
            )
        except TelegramBadRequest:
            pass
        except Exception as e:
            logger.warning(f"Countdown update error: {e}")


async def _roulette_timeout_handler(
    bot: Bot,
    chat_id: int,
    winner_id: int,
    winner_mention: str,
    message_id: int,
    reward: int,
    is_jackpot: bool,
    container: Container
):
    """Обработчик таймаута рулетки."""
    await asyncio.sleep(ROULETTE_TIMEOUT)
    
    if chat_id not in _active_roulettes:
        return
    
    roulette = _active_roulettes.get(chat_id)
    if not roulette or roulette["user_id"] != winner_id:
        return
    
    # Удаляем рулетку
    del _active_roulettes[chat_id]
    
    # Устанавливаем кулдаун
    _roulette_cooldowns[chat_id] = time.time() + ROULETTE_COOLDOWN
    
    logger.info(f"🎰 Roulette timeout in {chat_id}, user {winner_id} missed {reward} coins (jackpot={is_jackpot})")
    
    # Обновляем сообщение
    timeout_msg = _build_timeout_message(winner_mention, reward, is_jackpot)
    try:
        await bot.edit_message_text(
            timeout_msg,
            chat_id=chat_id,
            message_id=message_id,
            parse_mode="HTML"
        )
    except Exception as e:
        logger.warning(f"Failed to edit timeout message: {e}")


@router.message(F.text & ~F.text.startswith("/"), HasActiveRoulette())
async def check_roulette_response(message: Message, container: Container):
    """Проверяет ответ на рулетку."""
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if chat_id not in _active_roulettes:
        return
    
    roulette = _active_roulettes[chat_id]
    
    if roulette["user_id"] != user_id:
        return
    
    if time.time() > roulette["expires"]:
        return
    
    # Победа!
    del _active_roulettes[chat_id]
    
    # Устанавливаем кулдаун
    _roulette_cooldowns[chat_id] = time.time() + ROULETTE_COOLDOWN
    
    # Данные
    reward = roulette["reward"]
    is_jackpot = roulette.get("is_jackpot", False)
    response_time = time.time() - roulette["start_time"]
    
    winner_mention = _get_user_mention(
        user_id,
        roulette.get("username"),
        roulette.get("first_name", "")
    )
    
    # Добавляем в историю
    name = roulette.get("username") or roulette.get("first_name", "???")
    _add_to_history(chat_id, name, reward, is_jackpot)
    
    # Начисляем награду через сервис экономики
    try:
        economy_service = container.economy_service
        result = await economy_service.process_game_win(
            user_id=user_id,
            coins=reward,
            xp=0,  # Рулетка не дает XP
            description=f"Рулетка: {'ДЖЕКПОТ!' if is_jackpot else 'победа'}"
        )
        if not result["success"]:
            # Обработка ошибок от сервиса
            if "bank" in str(result.get("error", "")).lower() or "insufficient" in str(result.get("error", "")).lower():
                await message.answer(f"⚠️ <b>Казна пуста!</b> Награда не выдана.", parse_mode="HTML")
            else:
                await message.answer(f"{Visuals.cross()} Ошибка при начислении награды!", parse_mode="HTML")
            return

        logger.info(f"🎰 Roulette WIN: user {user_id} got {reward} coins")
    except Exception as e:
        logger.exception(f"Error awarding roulette prize: {e}")
        await message.answer(f"{Visuals.cross()} Ошибка при начислении награды!")
        return
    
    # Сообщение о победе
    win_msg = _build_win_message(winner_mention, reward, is_jackpot, response_time)
    
    try:
        await message.bot.edit_message_text(
            win_msg,
            chat_id=chat_id,
            message_id=roulette["message_id"],
            parse_mode="HTML"
        )
    except Exception as e:
        logger.warning(f"Failed to edit win message: {e}")
    
    # Ответ победителю
    jackpot_text = f"{_get_random_emoji('slots')} ДЖЕКПОТ! " if is_jackpot else ""
    speed_bonus = f"{_get_random_emoji('lightning')} Молниеносная реакция!" if response_time < 5 else ""
    
    await message.reply(
        f"{_get_random_emoji('party')} <b>{jackpot_text}ПОБЕДА!</b>\n\n"
        f"{_get_random_emoji('money')} Ты получил <b>{reward:,}</b> монет!\n"
        f"{_get_random_emoji('clock')} Время реакции: <b>{response_time:.1f}</b> сек\n"
        f"{speed_bonus}",
        parse_mode="HTML"
    )
