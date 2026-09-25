"""
💣 БОНУС-БОМБА v2.0 - ЭПИЧЕСКАЯ ВЕРСИЯ!

Команда: /senseibomb [сумма] [кол-во победителей]
- Анимация активации бомбы
- Драматический обратный отсчёт
- Бонусы для первых (x2 для первого!)
- Комбо-система
- Эпичные визуальные эффекты

Эффект: чат ВЗРЫВАЕТСЯ активностью!
"""

import asyncio
import html
import logging
import random
import time
from typing import Dict, List, Optional, Set

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.exceptions import TelegramBadRequest

from src.core.config import settings
from src.core.container import Container
from src.core.visuals import Visuals
from src.infra.database.uow import UnitOfWork
from src.domain.repositories import UserRepository, BankRepository, TransactionRepository
from src.infra.database.models import TransactionType

router = Router(name="bomb")
logger = logging.getLogger(__name__)

# === Константы ===
BOMB_DEFAULT_TOTAL = 5000
BOMB_DEFAULT_WINNERS = 10
BOMB_MIN_TOTAL = 100
BOMB_MAX_TOTAL = 100000
BOMB_MIN_WINNERS = 1
BOMB_MAX_WINNERS = 50
BOMB_TIMEOUT = 60
BOMB_COOLDOWN = 120
BOMB_ANIMATION_FRAMES = 5

# Бонусы для первых мест
FIRST_PLACE_BONUS = 2.0   # x2 для первого
SECOND_PLACE_BONUS = 1.5  # x1.5 для второго
THIRD_PLACE_BONUS = 1.25  # x1.25 для третьего

# Эмодзи для анимации
BOMB_EMOJIS = [
    '<tg-emoji emoji-id="6064114009404083025">💣</tg-emoji>',
    '<tg-emoji emoji-id="5469654973308476699">💣</tg-emoji>',
    '<tg-emoji emoji-id="5798897068751719945">💥</tg-emoji>',
    '<tg-emoji emoji-id="5276032951342088188">💥</tg-emoji>',
    Visuals.fire(),
    '<tg-emoji emoji-id="5318921223449623508">⚡</tg-emoji>'
]
EXPLOSION_FRAMES = [
    '<tg-emoji emoji-id="6064114009404083025">💣</tg-emoji>',
    '<tg-emoji emoji-id="5469654973308476699">💣</tg-emoji>💨',
    '<tg-emoji emoji-id="5341570033405412393">💣</tg-emoji>💨💨',
    f"{Visuals.fire_raw()}<tg-emoji emoji-id=\"5798897068751719945\">💥</tg-emoji>{Visuals.fire_raw()}",
    '<tg-emoji emoji-id="5276032951342088188">💥</tg-emoji><tg-emoji emoji-id="5260516956783534160">💥</tg-emoji><tg-emoji emoji-id="6325767939676964769">💥</tg-emoji>',
    f"⚡{Visuals.fire_raw()}⚡",
]

WINNER_REACTIONS = [
    '<tg-emoji emoji-id="5318921223449623508">⚡</tg-emoji> МОЛНИЯ!',
    f"{Visuals.fire()} ОГОНЬ!",
    '<tg-emoji emoji-id="5258461290946379238">⚡️</tg-emoji> СКОРОСТЬ!',
    '<tg-emoji emoji-id="5256131095094652290">🎯</tg-emoji> ТОЧНО!',
    '<tg-emoji emoji-id="6033132735260792506">🚀</tg-emoji> РАКЕТА!',
    '<tg-emoji emoji-id="5886285376754031265">⭐</tg-emoji> ЗВЕЗДА!',
]

# Хранилища
_active_bombs: Dict[int, dict] = {}
_bomb_cooldowns: Dict[int, float] = {}
_bomb_stats: Dict[int, dict] = {}  # Статистика по чатам


class HasActiveBomb:
    """Filter: only matches if there's an active bomb in this chat."""
    def __call__(self, message) -> bool:
        return message.chat.id in _active_bombs


def _get_user_mention(user_id: int, username: Optional[str], first_name: str = "") -> str:
    """Создает упоминание."""
    if username:
        return f"@{username}"
    if first_name:
        return f'<a href="tg://user?id={user_id}">{html.escape(first_name)}</a>'
    return f'<a href="tg://user?id={user_id}">#{str(user_id)[-4:]}</a>'


def _get_position_emoji(position: int) -> str:
    """Эмодзи для позиции."""
    emojis = {
        1: '<tg-emoji emoji-id="5440539497383087970">🥇</tg-emoji>',
        2: '<tg-emoji emoji-id="5447203607294265305">🥈</tg-emoji>',
        3: '<tg-emoji emoji-id="5453902265922376865">🥉</tg-emoji>'
    }
    return emojis.get(position, f"#{position}")


def _get_position_bonus(position: int) -> float:
    """Множитель бонуса для позиции."""
    if position == 1:
        return FIRST_PLACE_BONUS
    elif position == 2:
        return SECOND_PLACE_BONUS
    elif position == 3:
        return THIRD_PLACE_BONUS
    return 1.0


def _build_activation_frame(frame: int) -> str:
    """Кадр анимации активации."""
    emoji = EXPLOSION_FRAMES[frame % len(EXPLOSION_FRAMES)]
    dots = "●" * ((frame % 3) + 1) + "○" * (3 - (frame % 3))
    
    if frame < 2:
        return (
            f"{emoji} <b>БОНУС-БОМБА</b> {emoji}\n"
            f"━━━━━━━━━━━━━━━━━━━\n\n"
            f"  {Visuals.bomb()} <i>Активация...</i>\n\n"
            f"       {dots}"
        )
    elif frame < 4:
        return (
            f"{emoji}{emoji}{emoji} <b>БОНУС-БОМБА</b> {emoji}{emoji}{emoji}\n"
            f"━━━━━━━━━━━━━━━━━━━\n\n"
            f'  <tg-emoji emoji-id="5264841061137683683">⚠️</tg-emoji> <b>ВНИМАНИЕ!</b> <tg-emoji emoji-id="5264841061137683683">⚠️</tg-emoji>\n\n'
            f"       {dots}"
        )
    else:
        return (
            f'<tg-emoji emoji-id="5798897068751719945">💥</tg-emoji><tg-emoji emoji-id="5798897068751719945">💥</tg-emoji><tg-emoji emoji-id="5798897068751719945">💥</tg-emoji> <b>БОМБА АКТИВНА!</b> <tg-emoji emoji-id="5798897068751719945">💥</tg-emoji><tg-emoji emoji-id="5798897068751719945">💥</tg-emoji><tg-emoji emoji-id="5798897068751719945">💥</tg-emoji>\n'
            f"━━━━━━━━━━━━━━━━━━━\n\n"
            f"  ⚡ <b>ПИШИ БЫСТРЕЕ!</b> ⚡"
        )


def _build_bomb_start_message(total: int, per_user: int, max_winners: int, timeout: int) -> str:
    """Эпичное стартовое сообщение."""
    return (
        f'<tg-emoji emoji-id="5798897068751719945">💥</tg-emoji><tg-emoji emoji-id="5798897068751719945">💥</tg-emoji><tg-emoji emoji-id="5798897068751719945">💥</tg-emoji> <b>БОНУС-БОМБА</b> <tg-emoji emoji-id="5798897068751719945">💥</tg-emoji><tg-emoji emoji-id="5798897068751719945">💥</tg-emoji><tg-emoji emoji-id="5798897068751719945">💥</tg-emoji>\n'
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f'{Visuals.fire()} <b>АКТИВИРОВАНА!</b> {Visuals.fire()}\n\n'
        f"💰 Банк: <b>{total:,}</b> монет\n"
        f"👥 Мест: <b>{max_winners}</b>\n"
        f"🎁 Награда: <b>~{per_user:,}</b>\n\n"
        f'<tg-emoji emoji-id="5462927083132970373">🏆</tg-emoji> <b>Бонусы:</b>\n'
        f'   <tg-emoji emoji-id="5440539497383087970">🥇</tg-emoji> 1-е место: x2\n'
        f'   <tg-emoji emoji-id="5447203607294265305">🥈</tg-emoji> 2-е место: x1.5\n'
        f'   <tg-emoji emoji-id="5453902265922376865">🥉</tg-emoji> 3-е место: x1.25\n\n'
        f'<tg-emoji emoji-id="5260469398610657764">⏰</tg-emoji> <b>ОСТАЛОСЬ: {timeout} СЕК</b>\n\n'
        f"📝 <b>ПИШИ ЧТО УГОДНО</b>\n"
        f"<i>чтобы успеть!</i> 🏃"
    )


def _build_progress_message(
    total: int,
    per_user: int,
    max_winners: int,
    current_winners: int,
    remaining: int,
    winners_list: List[dict]
) -> str:
    """Сообщение с прогрессом."""
    progress = current_winners / max_winners if max_winners > 0 else 0
    bar_len = 15
    filled = int(progress * bar_len)
    bar = "▓" * filled + "░" * (bar_len - filled)
    
    # Цвет срочности
    if remaining <= 10:
        urgency = "🔴 <b>ФИНАЛ!</b>"
    elif remaining <= 20:
        urgency = "🟠 <b>СПЕШИ!</b>"
    elif remaining <= 30:
        urgency = "🟡"
    else:
        urgency = "🟢"
    
    remaining_spots = max_winners - current_winners
    
    spots_text = ""
    if remaining_spots > 0:
        spots_text = (
            f"{urgency} ОСТАЛОСЬ: <b>{remaining}</b> сек\n"
            f"🎯 Ещё <b>{remaining_spots}</b> мест!"
        )
    else:
        spots_text = (
            f"{Visuals.check()} <b>ВСЕ МЕСТА ЗАНЯТЫ!</b>\n"
            f"<i>Подводим итоги...</i>"
        )
    
    # Топ-5 победителей
    leaders_text = ""
    leaders_text = ""
    if winners_list:
        leaders_text = '\n\n<tg-emoji emoji-id="5462927083132970373">🏆</tg-emoji> <b>Лидеры:</b>\n'
        for i, w in enumerate(winners_list[:5], 1):
            name = w.get("name", "???")[:10]
            bonus = w.get("bonus", 0)
            pos_emoji = _get_position_emoji(i)
            if i <= 3:
                leaders_text += f"   {pos_emoji} {name} <b>+{bonus:,}</b>\n"
            else:
                leaders_text += f"   #{i} {name} <b>+{bonus:,}</b>\n"
    
    return (
        f"💣 <b>БОНУС-БОМБА</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"[{bar}]\n"
        f"<b>{current_winners}/{max_winners}</b> успели\n\n"
        f"{spots_text}"
        f"{leaders_text}"
    )


def _build_countdown_message(remaining: int, current: int, max_win: int) -> str:
    """Драматический обратный отсчёт."""
    if remaining <= 5:
        explosion = '<tg-emoji emoji-id="5798897068751719945">💥</tg-emoji>'
        countdown_visual = explosion * remaining
    elif remaining <= 10:
        countdown_visual = Visuals.fire_raw() * (remaining // 2)
    else:
        countdown_visual = f'<tg-emoji emoji-id="5260469398610657764">⏰</tg-emoji> <b>{remaining}</b>'
    
    return (
        f"{Visuals.bomb()} <b>БОМБА ТИКАЕТ!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"  {countdown_visual}\n\n"
        f"👥 <b>{current}/{max_win}</b>"
    )


def _build_finished_message(
    total: int,
    per_user: int,
    winners_list: List[dict],
    max_winners: int,
    total_distributed: int,
    is_timeout: bool = False
) -> str:
    """Эпичное финальное сообщение."""
    actual_winners = len(winners_list)
    
    if actual_winners == 0:
        return (
            f"💥💥💥 <b>БОНУС-БОМБА</b> 💥💥💥\n"
            f"━━━━━━━━━━━━━━━━━━━\n\n"
            f'<tg-emoji emoji-id="5453957997418004470">😱</tg-emoji><tg-emoji emoji-id="5453957997418004470">😱</tg-emoji><tg-emoji emoji-id="5453957997418004470">😱</tg-emoji> <b>ПРОВАЛ!</b> <tg-emoji emoji-id="5453957997418004470">😱</tg-emoji><tg-emoji emoji-id="5453957997418004470">😱</tg-emoji><tg-emoji emoji-id="5453957997418004470">😱</tg-emoji>\n\n'
            f"{Visuals.cross()} Никто не успел!\n\n"
            f"💸 <b>{total:,}</b> монет\n"
            f"<i>сгорели в огне...</i>\n\n"
            f"{Visuals.fire_raw() * 7}\n\n"
            f"<i>В следующий раз будьте быстрее!</i> 🏃"
        )
    else:
        status = '<tg-emoji emoji-id="5260469398610657764">⏰</tg-emoji> <b>ВРЕМЯ ВЫШЛО!</b>' if is_timeout else f'{Visuals.check()} <b>ВСЕ МЕСТА!</b>'
        
        # Топ-3 с бонусами
        top3_text = ""
        for i, w in enumerate(winners_list[:3], 1):
            name = w.get("name", "???")[:12]
            bonus = w.get("bonus", 0)
            pos_emoji = _get_position_emoji(i)
            mult = _get_position_bonus(i)
            if mult > 1:
                top3_text += f"   {pos_emoji} {name}: <b>+{bonus:,}</b> (x{mult})\n"
            else:
                top3_text += f"   {pos_emoji} {name}: <b>+{bonus:,}</b>\n"
        
        # Остальные
        others_text = ""
        if actual_winners > 3:
            others_text = "\n"
            for i, w in enumerate(winners_list[3:7], 4):
                name = w.get("name", "???")[:12]
                bonus = w.get("bonus", 0)
                others_text += f"   #{i} {name}: <b>+{bonus:,}</b>\n"
            
            if actual_winners > 7:
                others_text += f"   <i>...и ещё {actual_winners - 7} чел.</i>\n"
        
        return (
            f'<tg-emoji emoji-id="5798897068751719945">💥</tg-emoji><tg-emoji emoji-id="5798897068751719945">💥</tg-emoji><tg-emoji emoji-id="5798897068751719945">💥</tg-emoji> <b>БОНУС-БОМБА</b> <tg-emoji emoji-id="5798897068751719945">💥</tg-emoji><tg-emoji emoji-id="5798897068751719945">💥</tg-emoji><tg-emoji emoji-id="5798897068751719945">💥</tg-emoji>\n'
            f"━━━━━━━━━━━━━━━━━━━\n\n"
            f"{status}\n\n"
            f"👥 Победителей: <b>{actual_winners}/{max_winners}</b>\n"
            f"💰 Роздано: <b>{total_distributed:,}</b>\n\n"
            f'<tg-emoji emoji-id="5462927083132970373">🏆</tg-emoji> <b>ПОБЕДИТЕЛИ:</b>\n'
            f"{top3_text}"
            f"{others_text}"
        )


def _build_cooldown_message(remaining: int) -> str:
    """Сообщение о кулдауне."""
    mins = remaining // 60
    secs = remaining % 60
    time_str = f"{mins}:{secs:02d}" if mins else f"{secs} сек"
    
    return (
        f"💣 <b>БОНУС-БОМБА</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"{Visuals.wait()} <i>Перезарядка...</i>\n\n"
        f'<tg-emoji emoji-id="5260469398610657764">⏰</tg-emoji> Ещё <b>{time_str}</b>\n\n'
        f"🔋 <i>Копим энергию!</i>"
    )


@router.message(Command("senseibomb"))
async def cmd_senseibomb(message: Message, container: Container):
    """💣 Запустить ЭПИЧЕСКУЮ бонус-бомбу!"""
    logger.info(f"👉 [BOMB] Step 1: Command triggered by {message.from_user.id} in chat {message.chat.id}")
    
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    # Проверяем групповой чат
    logger.info(f"👉 [BOMB] Step 2: Checking chat type: {message.chat.type}")
    if message.chat.type not in ("group", "supergroup"):
        logger.info(f"💣 Bomb rejected: not a group chat (type={message.chat.type})")
        await message.answer(f"{Visuals.bomb()} Бомба работает только в групповых чатах!")
        return
    
    # Проверяем права
    logger.info(f"👉 [BOMB] Step 3: Checking permissions for user {user_id}")
    is_bot_admin = user_id in settings.admin_ids
    logger.info(f"👉 [BOMB] Step 3a: is_bot_admin = {is_bot_admin}, admin_ids = {settings.admin_ids}")
    
    if not is_bot_admin:
        try:
            member = await message.chat.get_member(user_id)
            is_chat_admin = member.status in ["creator", "administrator"]
            logger.info(f"👉 [BOMB] Step 3b: member.status = {member.status}, is_chat_admin = {is_chat_admin}")
        except Exception as e:
            logger.error(f"👉 [BOMB] Step 3c: Error getting member: {e}")
            is_chat_admin = False
        
        if not is_chat_admin:
            logger.info(f"👉 [BOMB] Step 3d: User is not admin, rejecting")
            await message.answer(f"{Visuals.bomb()} Только администраторы могут запускать бомбу!")
            return
    
    # Проверяем активную бомбу
    logger.info(f"👉 [BOMB] Step 4: Checking active bombs")
    if chat_id in _active_bombs:
        bomb = _active_bombs[chat_id]
        remaining = int(bomb["expires"] - time.time())
        if remaining > 0:
            logger.info(f"👉 [BOMB] Step 4a: Bomb already active, {remaining}s remaining")
            await message.answer(
                f"{Visuals.bomb()} Бомба уже тикает!\n"
                f"👥 Успели: {len(bomb['winners'])}/{bomb['max_winners']}\n"
                f"⏰ Осталось: {remaining} сек"
            )
            return
    
    # Проверяем кулдаун
    logger.info(f"👉 [BOMB] Step 5: Checking cooldown")
    current_time = time.time()
    if chat_id in _bomb_cooldowns:
        cooldown_expires = _bomb_cooldowns[chat_id]
        if current_time < cooldown_expires:
            remaining = int(cooldown_expires - current_time)
            logger.info(f"👉 [BOMB] Step 5a: On cooldown, {remaining}s remaining")
            msg = _build_cooldown_message(remaining)
            await message.answer(msg, parse_mode="HTML")
            return
    
    # Парсим аргументы
    logger.info(f"👉 [BOMB] Step 6: Parsing arguments from: {message.text}")
    args = message.text.split()[1:]
    
    total = BOMB_DEFAULT_TOTAL
    max_winners = BOMB_DEFAULT_WINNERS
    
    if len(args) >= 1:
        try:
            total = int(args[0])
            total = max(BOMB_MIN_TOTAL, min(BOMB_MAX_TOTAL, total))
        except ValueError:
            pass
    
    if len(args) >= 2:
        try:
            max_winners = int(args[1])
            max_winners = max(BOMB_MIN_WINNERS, min(BOMB_MAX_WINNERS, max_winners))
        except ValueError:
            pass
    
    per_user = total // max_winners
    logger.info(f"👉 [BOMB] Step 6a: total={total}, max_winners={max_winners}, per_user={per_user}")
    
    # Проверяем и резервируем средства в банке
    logger.info(f"👉 [BOMB] Step 7: Checking bank balance")
    try:
        uow = UnitOfWork(container.session_factory)
        async with uow:
            bank_repo = BankRepository(uow.session)
            balance = await bank_repo.get_balance()
            logger.info(f"👉 [BOMB] Step 7a: Bank balance = {balance}, needed = {total}")
            if balance < total:
                logger.info(f"👉 [BOMB] Step 7b: Insufficient funds!")
                await message.answer(
                    f"⚠️ <b>КАЗНА ПУСТА!</b>\n"
                    f"💰 Нужно: {total:,}\n"
                    f"📉 В банке: {balance:,.0f}\n"
                    f"Пополните банк через БД или /addmoney",
                    parse_mode="HTML"
                )
                return
            
            logger.info(f"👉 [BOMB] Step 7c: Withdrawing {total} from bank")
            await bank_repo.withdraw(total)
            await uow.commit()
            logger.info(f"👉 [BOMB] Step 7d: Bank transaction committed!")
    except Exception as e:
        logger.error(f"👉 [BOMB] Step 7e: Bank error: {e}", exc_info=True)
        await message.answer(f"{Visuals.cross()} Ошибка банка: {e}")
        return

    # === АНИМАЦИЯ АКТИВАЦИИ ===
    activation_msg = await message.answer(
        _build_activation_frame(0),
        parse_mode="HTML"
    )
    
    for frame in range(1, BOMB_ANIMATION_FRAMES + 1):
        await asyncio.sleep(0.5)
        try:
            await activation_msg.edit_text(
                _build_activation_frame(frame),
                parse_mode="HTML"
            )
        except TelegramBadRequest:
            pass
    
    await asyncio.sleep(0.5)
    
    # Показываем стартовое сообщение
    start_msg = _build_bomb_start_message(total, per_user, max_winners, BOMB_TIMEOUT)
    await activation_msg.edit_text(start_msg, parse_mode="HTML")
    
    # Сохраняем состояние
    _active_bombs[chat_id] = {
        "total": total,
        "per_user": per_user,
        "max_winners": max_winners,
        "winners": [],
        "winner_ids": set(),
        "expires": current_time + BOMB_TIMEOUT + 3,  # +3 за анимацию
        "message_id": activation_msg.message_id,
        "container": container,
        "total_distributed": 0,
    }
    
    # Запускаем таймеры
    asyncio.create_task(_bomb_progress_updater(message.bot, chat_id))
    asyncio.create_task(_bomb_timeout_handler(message.bot, chat_id, container))
    
    logger.info(f"💣 EPIC Bomb started in {chat_id}: {total} coins for {max_winners} winners")


async def _bomb_progress_updater(bot: Bot, chat_id: int):
    """Обновляет прогресс с драматическим эффектом."""
    last_update = 0
    
    while True:
        await asyncio.sleep(3)
        
        if chat_id not in _active_bombs:
            return
        
        bomb = _active_bombs[chat_id]
        remaining = int(bomb["expires"] - time.time())
        
        if remaining <= 0:
            return
        
        current_winners = len(bomb["winners"])
        
        # Обновляем чаще к концу
        should_update = (
            current_winners != last_update or
            remaining <= 15 or
            remaining in [45, 30, 20]
        )
        
        if should_update:
            last_update = current_winners
            
            msg = _build_progress_message(
                bomb["total"],
                bomb["per_user"],
                bomb["max_winners"],
                current_winners,
                remaining,
                bomb["winners"]
            )
            
            try:
                await bot.edit_message_text(
                    msg,
                    chat_id=chat_id,
                    message_id=bomb["message_id"],
                    parse_mode="HTML"
                )
            except TelegramBadRequest:
                pass
            except Exception as e:
                logger.warning(f"Bomb update error: {e}")


async def _bomb_timeout_handler(bot: Bot, chat_id: int, container: Container):
    """Таймаут бомбы."""
    await asyncio.sleep(BOMB_TIMEOUT)
    
    if chat_id not in _active_bombs:
        return
    
    await _finish_bomb(bot, chat_id, container, is_timeout=True)


async def _finish_bomb(bot: Bot, chat_id: int, container: Container, is_timeout: bool = False):
    """Эпичное завершение бомбы."""
    if chat_id not in _active_bombs:
        return
    
    bomb = _active_bombs.pop(chat_id)
    winners = bomb["winners"]
    total_distributed = bomb["total_distributed"]
    
    # Кулдаун
    _bomb_cooldowns[chat_id] = time.time() + BOMB_COOLDOWN
    
    # Начисляем награды и возвращаем остаток
    try:
        uow = UnitOfWork(container.session_factory)
        async with uow:
            user_repo = UserRepository(uow.session)
            tx_repo = TransactionRepository(uow.session)
            bank_repo = BankRepository(uow.session)
            
            # 1. Раздача
            for winner in winners:
                user = await user_repo.get_for_update(winner["user_id"])
                if user:
                    bonus = winner["bonus"]
                    user.coins += bonus
                    
                    position = winner.get("position", 0)
                    desc = f"Бонус-бомба #{position}"
                    
                    await tx_repo.create(
                        user_id=winner["user_id"],
                        tx_type=TransactionType.BOMB_WIN,
                        coins_change=bonus,
                        description=desc
                    )
            
            # 2. Возврат остатка
            refund = bomb["total"] - total_distributed
            if refund > 0:
                await bank_repo.deposit(refund)
                logger.info(f"Refunding {refund} to bank")
                
            await uow.commit()
            
            if refund > 0:
                await bot.send_message(chat_id, f"🏦 Неразыгранные {refund:,} монет вернулись в банк!", parse_mode="HTML")
             
    except Exception as e:
        logger.error(f"Error processing bomb rewards: {e}")
    
    # Финальное сообщение
    final_msg = _build_finished_message(
        bomb["total"],
        bomb["per_user"],
        winners,
        bomb["max_winners"],
        total_distributed,
        is_timeout
    )
    
    try:
        await bot.edit_message_text(
            final_msg,
            chat_id=chat_id,
            message_id=bomb["message_id"],
            parse_mode="HTML"
        )
    except Exception as e:
        logger.warning(f"Failed to edit final bomb message: {e}")
    
    logger.info(f"💣 Bomb finished in {chat_id}: {len(winners)}/{bomb['max_winners']} winners, {total_distributed} distributed")


@router.message(F.text & ~F.text.startswith("/"), HasActiveBomb())
async def check_bomb_participant(message: Message, container: Container):
    """Проверяет участника бомбы с ЭПИЧНЫМИ эффектами! Исключает команды."""
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if chat_id not in _active_bombs:
        return
    
    bomb = _active_bombs[chat_id]
    
    # Проверки
    if time.time() > bomb["expires"]:
        return
    
    if user_id in bomb["winner_ids"]:
        return
    
    if len(bomb["winners"]) >= bomb["max_winners"]:
        return
    
    # УСПЕЛ!
    username = message.from_user.username
    first_name = message.from_user.first_name or ""
    name = username or first_name or f"#{str(user_id)[-4:]}"
    
    position = len(bomb["winners"]) + 1
    multiplier = _get_position_bonus(position)
    bonus = int(bomb["per_user"] * multiplier)
    
    bomb["winner_ids"].add(user_id)
    bomb["winners"].append({
        "user_id": user_id,
        "username": username,
        "first_name": first_name,
        "name": name,
        "position": position,
        "bonus": bonus,
        "multiplier": multiplier,
    })
    bomb["total_distributed"] += bonus
    
    # Эпичное уведомление
    pos_emoji = _get_position_emoji(position)
    reaction = random.choice(WINNER_REACTIONS)
    
    if position == 1:
        explosion = '<tg-emoji emoji-id="5798897068751719945">💥</tg-emoji>'
        reply_text = (
            f'<tg-emoji emoji-id="5440539497383087970">🥇</tg-emoji>{explosion} <b>ПЕРВЫЙ!</b> {explosion}<tg-emoji emoji-id="5440539497383087970">🥇</tg-emoji>\n\n'
            f"💰 +{bonus:,} монет (x2!)\n"
            f"{reaction}"
        )
    elif position == 2:
        reply_text = (
            f'<tg-emoji emoji-id="5447203607294265305">🥈</tg-emoji> <b>ВТОРОЙ!</b>\n\n'
            f"💰 +{bonus:,} монет (x1.5!)\n"
            f"{reaction}"
        )
    elif position == 3:
        reply_text = (
            f'<tg-emoji emoji-id="5453902265922376865">🥉</tg-emoji> <b>ТРЕТИЙ!</b>\n\n'
            f"💰 +{bonus:,} монет (x1.25!)\n"
            f"{reaction}"
        )
    else:
        reply_text = (
            f"{pos_emoji} <b>УСПЕЛ!</b>\n\n"
            f"💰 +{bonus:,} монет"
        )
    
    await message.reply(reply_text, parse_mode="HTML")
    
    logger.info(f"💣 Bomb winner #{position} in {chat_id}: user {user_id}, bonus {bonus}")
    
    # Если все места заняты
    if len(bomb["winners"]) >= bomb["max_winners"]:
        asyncio.create_task(_finish_bomb(
            message.bot,
            chat_id,
            container,
            is_timeout=False
        ))
