"""
🌊 ВОЛНА v2.0 - ЭПИЧЕСКАЯ ВЕРСИЯ!

Команда: /senseiwave
- Эпичная анимация волны
- Топ-контрибьюторов с бонусами
- MVP получает x3 награду!
- Визуальные эффекты прогресса
- Комбо-система

Эффект: КОЛЛЕКТИВНАЯ цель объединяет!
"""

import asyncio
import html
import logging
import random
import time
from typing import Dict, List, Optional, Set
from collections import Counter

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.exceptions import TelegramBadRequest

from src.core.config import settings
from src.core.container import Container
from src.core.visuals import Visuals

router = Router(name="wave")
logger = logging.getLogger(__name__)

# Логирование при загрузке модуля
logger.info("🌊 Wave router loaded successfully!")

# === Константы ===
WAVE_TARGET_MESSAGES = 100
WAVE_DURATION_MINUTES = 10
WAVE_BASE_REWARD = 300
WAVE_MVP_MULTIPLIER = 3.0      # MVP получает x3
WAVE_TOP2_MULTIPLIER = 2.0     # 2-е место x2
WAVE_TOP3_MULTIPLIER = 1.5     # 3-е место x1.5
WAVE_COOLDOWN = 300
WAVE_UPDATE_INTERVAL = 5
WAVE_ANIMATION_FRAMES = 8

# Множители за серию
WAVE_STREAK_MULTIPLIERS = {
    3: 1.5,
    5: 2.0,
    10: 3.0,
}

# Визуальные эффекты волны - более драматичные
WAVE_PHASES = [
    ('<tg-emoji emoji-id="5215280961062713538">🌊</tg-emoji>', "Океан спокоен..."),
    ('<tg-emoji emoji-id="5215280961062713538">🌊</tg-emoji><tg-emoji emoji-id="5215409208786171970">🌊</tg-emoji>', "Волна зарождается!"),
    ('<tg-emoji emoji-id="5215280961062713538">🌊</tg-emoji><tg-emoji emoji-id="5215409208786171970">🌊</tg-emoji><tg-emoji emoji-id="5215568509123181370">🌊</tg-emoji>', "Волна набирает силу!"),
    ('<tg-emoji emoji-id="5215280961062713538">🌊</tg-emoji><tg-emoji emoji-id="5215409208786171970">🌊</tg-emoji><tg-emoji emoji-id="5215568509123181370">🌊</tg-emoji><tg-emoji emoji-id="5215701803433211518">🌊</tg-emoji>', "ВОЛНА МЧИТСЯ!"),
    ('<tg-emoji emoji-id="5215280961062713538">🌊</tg-emoji><tg-emoji emoji-id="5215409208786171970">🌊</tg-emoji><tg-emoji emoji-id="5215568509123181370">🌊</tg-emoji><tg-emoji emoji-id="5215701803433211518">🌊</tg-emoji><tg-emoji emoji-id="5215528291049420035">🌊</tg-emoji>', "НЕУДЕРЖИМАЯ СИЛА!"),
    ('<tg-emoji emoji-id="5215280961062713538">🌊</tg-emoji><tg-emoji emoji-id="5215409208786171970">🌊</tg-emoji><tg-emoji emoji-id="5215568509123181370">🌊</tg-emoji><tg-emoji emoji-id="5215701803433211518">🌊</tg-emoji><tg-emoji emoji-id="5215528291049420035">🌊</tg-emoji><tg-emoji emoji-id="5217656954150729943">🌊</tg-emoji>', "🔱 ЦУНАМИ СЕНСЕЯ! 🔱"),
]

WAVE_START_FRAMES = [
    '<tg-emoji emoji-id="5215280961062713538">🌊</tg-emoji>',
    '<tg-emoji emoji-id="5215280961062713538">🌊</tg-emoji><tg-emoji emoji-id="5215409208786171970">🌊</tg-emoji>',
    '<tg-emoji emoji-id="5215280961062713538">🌊</tg-emoji><tg-emoji emoji-id="5215409208786171970">🌊</tg-emoji><tg-emoji emoji-id="5215568509123181370">🌊</tg-emoji>',
    '<tg-emoji emoji-id="5215280961062713538">🌊</tg-emoji><tg-emoji emoji-id="5215409208786171970">🌊</tg-emoji><tg-emoji emoji-id="5215568509123181370">🌊</tg-emoji><tg-emoji emoji-id="5215701803433211518">🌊</tg-emoji>',
    '<tg-emoji emoji-id="5215280961062713538">🌊</tg-emoji><tg-emoji emoji-id="5215409208786171970">🌊</tg-emoji><tg-emoji emoji-id="5215568509123181370">🌊</tg-emoji><tg-emoji emoji-id="5215701803433211518">🌊</tg-emoji><tg-emoji emoji-id="5215528291049420035">🌊</tg-emoji>',
    '<tg-emoji emoji-id="5215280961062713538">🌊</tg-emoji><tg-emoji emoji-id="5215409208786171970">🌊</tg-emoji><tg-emoji emoji-id="5215568509123181370">🌊</tg-emoji><tg-emoji emoji-id="5215701803433211518">🌊</tg-emoji><tg-emoji emoji-id="5215528291049420035">🌊</tg-emoji><tg-emoji emoji-id="5217656954150729943">🌊</tg-emoji>',
    '<tg-emoji emoji-id="5215280961062713538">🌊</tg-emoji><tg-emoji emoji-id="5215409208786171970">🌊</tg-emoji><tg-emoji emoji-id="5215568509123181370">🌊</tg-emoji><tg-emoji emoji-id="5215701803433211518">🌊</tg-emoji><tg-emoji emoji-id="5215528291049420035">🌊</tg-emoji><tg-emoji emoji-id="5217656954150729943">🌊</tg-emoji><tg-emoji emoji-id="5215710084130158461">🌊</tg-emoji>',
    '<tg-emoji emoji-id="5215280961062713538">🌊</tg-emoji><tg-emoji emoji-id="5215409208786171970">🌊</tg-emoji><tg-emoji emoji-id="5215568509123181370">🌊</tg-emoji><tg-emoji emoji-id="5215701803433211518">🌊</tg-emoji><tg-emoji emoji-id="5215528291049420035">🌊</tg-emoji><tg-emoji emoji-id="5217656954150729943">🌊</tg-emoji><tg-emoji emoji-id="5215710084130158461">🌊</tg-emoji><tg-emoji emoji-id="5215495645003003236">🌊</tg-emoji>',
]

# Мотивационные фразы
WAVE_MOTIVATIONS = [
    "💪 Давай-давай-давай!",
    "🔥 Горим на полную!",
    "⚡ Энергия зашкаливает!",
    "🚀 Несёмся к победе!",
    "💥 Мощнейший натиск!",
    "🌟 Вы невероятны!",
    "👊 Бьём рекорды!",
    "🏆 Победа близка!",
]

# Фразы при почти победе
WAVE_ALMOST_DONE = [
    "⚡ ФИНИШНЫЙ РЫВОК!!!",
    "🔥 ДОБИВАЕМ!!!",
    "💪 ПОСЛЕДНИЙ НАТИСК!",
    "🚀 НА АБОРДАЖ!!!",
    "⭐ ДОЖИМАЕМ!!!",
]

# Фразы победы
WAVE_VICTORY_PHRASES = [
    "ЛЕГЕНДАРНАЯ ПОБЕДА!",
    "ЭПИЧЕСКАЯ ВОЛНА!",
    "ИСТОРИЧЕСКОЕ ДОСТИЖЕНИЕ!",
    "НЕВЕРОЯТНЫЙ УСПЕХ!",
    "ГРАНДИОЗНАЯ ПОБЕДА!",
]

COMBO_MESSAGES = [
    "🔥 Разогрелись!",
    "⚡ Энергия растёт!",
    "💪 Продолжайте!",
    "🚀 Вперёд!",
    "✨ Отлично!",
    "🎯 В точку!",
]

# Хранилища
_active_waves: Dict[int, dict] = {}
_wave_streaks: Dict[int, int] = {}
_wave_cooldowns: Dict[int, float] = {}


class HasActiveWave:
    """Filter: only matches if there's an active wave in this chat."""
    def __call__(self, message) -> bool:
        return message.chat.id in _active_waves


def _get_streak_multiplier(streak: int) -> float:
    """Множитель за серию."""
    multiplier = 1.0
    for threshold, mult in sorted(WAVE_STREAK_MULTIPLIERS.items()):
        if streak >= threshold:
            multiplier = mult
    return multiplier


def _get_streak_text(streak: int) -> str:
    """Текст серии."""
    if streak >= 10:
        return "🔥🔥🔥 ЛЕГЕНДА x3!"
    elif streak >= 5:
        return "🔥🔥 ОГОНЬ x2!"
    elif streak >= 3:
        return "🔥 РАЗОГРЕВ x1.5!"
    return ""


def _get_wave_phase(progress: float) -> tuple[str, str]:
    """Фаза волны по прогрессу."""
    idx = min(int(progress * len(WAVE_PHASES)), len(WAVE_PHASES) - 1)
    return WAVE_PHASES[idx]


def _build_wave_bar(current: int, target: int, width: int = 20) -> str:
    """Красивый прогресс-бар волны."""
    progress = min(1.0, current / target) if target > 0 else 0
    filled = int(progress * width)
    
    if progress < 0.3:
        bar = "▓" * filled + "░" * (width - filled)
    elif progress < 0.6:
        bar = "█" * filled + "▓" * 2 + "░" * max(0, width - filled - 2)
    elif progress < 0.9:
        bar = "█" * filled + "▓" * 1 + "░" * max(0, width - filled - 1)
    else:
        bar = "█" * width if progress >= 1.0 else "█" * filled + "░" * (width - filled)
    
    return f"[{bar}]"


def _build_animation_frame(frame: int) -> str:
    """Кадр анимации старта."""
    wave = WAVE_START_FRAMES[frame % len(WAVE_START_FRAMES)]
    dots = "●" * ((frame % 3) + 1) + "○" * (3 - (frame % 3))
    
    if frame < 2:
        return (
            f'<tg-emoji emoji-id="5265109462233943179">⚡️</tg-emoji><tg-emoji emoji-id="5264790784250510907">⚡️</tg-emoji><tg-emoji emoji-id="5262490056169391723">⚡️</tg-emoji><tg-emoji emoji-id="5264896053898938796">⚡️</tg-emoji><tg-emoji emoji-id="5264880110980337547">⚡️</tg-emoji>\n'
            f"━━━━━━━━━━━━━━━━━━━\n\n"
            f"  {wave} <i>Волна надвигается...</i>\n\n"
            f"       {dots}"
        )
    elif frame < 4:
        return (
            f'<tg-emoji emoji-id="5206673266780943706">🌊</tg-emoji><tg-emoji emoji-id="5203911310751840943">🌊</tg-emoji> <b>ВОЛНА БЛИЗКО!</b> <tg-emoji emoji-id="5203947985477580413">🌊</tg-emoji><tg-emoji emoji-id="5206574061626339029">🌊</tg-emoji>\n'
            f"━━━━━━━━━━━━━━━━━━━\n\n"
            f"  💨 <i>Готовьтесь писать!</i>\n\n"
            f"       {dots}"
        )
    else:
        return (
            f'<tg-emoji emoji-id="5206320984973390767">🌊</tg-emoji><tg-emoji emoji-id="5204309071968090637">🌊</tg-emoji><tg-emoji emoji-id="5206250169552614531">🌊</tg-emoji> <b>ЦУНАМИ НАЧАЛОСЬ!</b> <tg-emoji emoji-id="5204382155131599428">🌊</tg-emoji><tg-emoji emoji-id="5204032046577498892">🌊</tg-emoji><tg-emoji emoji-id="5206467950164325589">🌊</tg-emoji>\n'
            f"━━━━━━━━━━━━━━━━━━━\n\n"
            f'  <tg-emoji emoji-id="5461136249274244213">😱</tg-emoji> <b>ПИШИТЕ ВСЕ!!!</b> <tg-emoji emoji-id="5461136249274244213">😱</tg-emoji>'
        )


def _build_wave_start_message(
    target: int,
    duration_min: int,
    base_reward: int,
    streak: int
) -> str:
    """Эпичное стартовое сообщение."""
    streak_text = _get_streak_text(streak)
    
    streak_block = ""
    if streak >= 3:
        streak_block = (
            f"\n\n🔥🔥🔥 <b>СЕРИЯ: {streak}</b> 🔥🔥🔥\n"
            f"<i>{streak_text}</i>"
        )
    
    upper_row = (
        '<tg-emoji emoji-id="5206673266780943706">🌊</tg-emoji>'
        '<tg-emoji emoji-id="5203911310751840943">🌊</tg-emoji>'
        '<tg-emoji emoji-id="5203947985477580413">🌊</tg-emoji>'
        '<tg-emoji emoji-id="5206574061626339029">🌊</tg-emoji>'
    )
    lower_row = (
        '<tg-emoji emoji-id="5203934662489030684">🌊</tg-emoji>'
        '<tg-emoji emoji-id="5206339771160341941">🌊</tg-emoji>'
        '<tg-emoji emoji-id="5206218665967499097">🌊</tg-emoji>'
        '<tg-emoji emoji-id="5206597142780589094">🌊</tg-emoji>'
        '<tg-emoji emoji-id="5204019019941688944">🌊</tg-emoji>'
    )
    
    lightning = '<tg-emoji emoji-id="5983307094537801573">⚡️</tg-emoji>'
    muscle = '<tg-emoji emoji-id="5366230485783557962">🤝</tg-emoji>'
    target_emoji = '<tg-emoji emoji-id="5256131095094652290">🎯</tg-emoji>'
    clock = '<tg-emoji emoji-id="5386415655253730366">⏰</tg-emoji>'
    money = '<tg-emoji emoji-id="5224257782013769471">💰</tg-emoji>'
    trophy = '<tg-emoji emoji-id="5447112111605964162">🏆</tg-emoji>'
    medal1 = '<tg-emoji emoji-id="5440539497383087970">🥇</tg-emoji>'
    medal2 = '<tg-emoji emoji-id="5447203607294265305">🥈</tg-emoji>'
    medal3 = '<tg-emoji emoji-id="5453902265922376865">🥉</tg-emoji>'
    group = '<tg-emoji emoji-id="5453957997418004470">👥</tg-emoji>'
    memo = random.choice([
        '<tg-emoji emoji-id="5260382803480037167">🤬</tg-emoji>',
        '<tg-emoji emoji-id="5260471443015089915">👑</tg-emoji>'
    ])

    return (
        f"{upper_row}{upper_row}{upper_row}\n"
        f"  {lightning} <b>ВОЛНА АКТИВА</b> {lightning}\n"
        f"{lower_row}{lower_row}{lower_row}\n\n"
        f"{muscle} <b>ОБЪЕДИНЯЙТЕСЬ!</b>\n\n"
        f"{target_emoji} Цель: <b>{target}</b> сообщений\n"
        f"{clock} Время: <b>{duration_min}</b> минут\n"
        f"{money} Банк: <b>{base_reward:,}+</b> монет\n\n"
        f"{trophy} <b>НАГРАДЫ ЗА ВОЛНУ:</b>\n"
        f"   {medal1} <b>MVP</b> → x3 награда!\n"
        f"   {medal2} Топ-2 → x2 награда\n"
        f"   {medal3} Топ-3 → x1.5 награда\n"
        f"   {group} Все → базовая награда"
        f"{streak_block}\n\n"
        f"{memo} <b>ПИШИТЕ ЧТО УГОДНО!</b>\n"
        f"<i>Каждое сообщение приближает победу!</i>"
    )


def _build_progress_message(
    current: int,
    target: int,
    remaining_seconds: int,
    participants: Set[int],
    message_counts: Counter,
    streak: int
) -> str:
    """Сообщение с прогрессом."""
    progress = current / target if target > 0 else 0
    bar = _build_wave_bar(current, target, 15)
    wave_emoji, wave_text = _get_wave_phase(progress)
    
    mins = remaining_seconds // 60
    secs = remaining_seconds % 60
    time_str = f"{mins}:{secs:02d}"
    
    percent = int(progress * 100)
    
    # Срочность и мотивация - с рандомными фразами
    if remaining_seconds <= 30:
        urgency = f"{Visuals.error_raw()}{Visuals.error_raw()}{Visuals.error_raw()} <b>ПОСЛЕДНИЕ СЕКУНДЫ!!!</b>"
        time_emoji = "⏰💨"
    elif remaining_seconds <= 60:
        urgency = f"{Visuals.error_raw()}{Visuals.error_raw()} <b>ФИНИШНАЯ ПРЯМАЯ!</b>"
        time_emoji = "⏰"
    elif remaining_seconds <= 120:
        urgency = f"🟠 <b>Ускоряемся!</b> {random.choice(WAVE_MOTIVATIONS)}"
        time_emoji = "⏰"
    elif remaining_seconds <= 180:
        urgency = "🟡 <i>Время летит!</i>"
        time_emoji = "⏰"
    else:
        urgency = f"🟢 <i>Стабильно!</i>"
        time_emoji = "⏰"
    
    # Топ-3 контрибьютора с эффектами
    leaders_text = ""
    if message_counts:
        top3 = message_counts.most_common(3)
        medals = ["🥇", "🥈", "🥉"]
        leaders_text = "\n\n🏆 <b>ЛИДЕРЫ ВОЛНЫ:</b>\n"
        for i, (name, count) in enumerate(top3):
            fire = "🔥" if count >= 10 else "⚡" if count >= 5 else ""
            escaped_name = html.escape(name[:10])
            leaders_text += f"   {medals[i]} {escaped_name}: <b>{count}</b> {fire}\n"
    
    # Мотивация с рандомом
    motivation = ""
    if progress < 1.0:
        remaining_msgs = target - current
        if remaining_msgs <= 5:
            motivation = f"\n\n🔥🔥🔥 <b>ВСЕГО {remaining_msgs}!!!</b> 🔥🔥🔥"
        elif remaining_msgs <= 10:
            motivation = f"\n\n⚡ <b>{random.choice(WAVE_ALMOST_DONE)}</b> Осталось {remaining_msgs}!"
        elif remaining_msgs <= 30:
            motivation = f"\n\n💪 Ещё <b>{remaining_msgs}</b>! Почти победа!"
        else:
            motivation = f"\n\n💬 Ещё <b>{remaining_msgs}</b> до победы"
    
    # Достижения
    achievements = ""
    if len(participants) >= 10:
        achievements = "\n🏅 <i>10+ бойцов!</i>"
    if len(participants) >= 20:
        achievements = "\n🏅🏅 <i>20+ бойцов! Армия!</i>"
    if percent >= 50 and percent < 75:
        achievements += "\n⭐ <i>Половина пройдена!</i>"
    if percent >= 75 and percent < 100:
        achievements += "\n⭐⭐ <i>3/4 выполнено!</i>"
    
    return (
        f"🌊 <b>{wave_text}</b> 🌊\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"{wave_emoji}\n\n"
        f"{bar}\n"
        f"📊 <b>{current}/{target}</b> ({percent}%){achievements}\n\n"
        f"{time_emoji} Осталось: <b>{time_str}</b>\n"
        f"👥 Бойцов: <b>{len(participants)}</b>\n\n"
        f"{urgency}"
        f"{leaders_text}"
        f"{motivation}"
    )


def _build_victory_message(
    current: int,
    target: int,
    participants: Set[int],
    message_counts: Counter,
    streak: int,
    base_reward: int
) -> str:
    """Эпичное сообщение победы!"""
    streak_mult = _get_streak_multiplier(streak)
    victory_phrase = random.choice(WAVE_VICTORY_PHRASES)
    
    # MVP rewards
    top3 = message_counts.most_common(3)
    
    # Топ контрибьюторы
    multipliers = [WAVE_MVP_MULTIPLIER, WAVE_TOP2_MULTIPLIER, WAVE_TOP3_MULTIPLIER]
    medals = ["🥇", "🥈", "🥉"]
    titles = ["MVP", "ГЕРОЙ", "ВОИН"]
    
    mvp_text = ""
    for i, (name, count) in enumerate(top3):
        mult = multipliers[i] if i < 3 else 1.0
        reward = int(base_reward * streak_mult * mult)
        fire = f"{Visuals.fire_raw()}{Visuals.fire_raw()}" if i == 0 else Visuals.fire_raw() if i == 1 else "⚡"
        escaped_name = html.escape(name[:12])
        mvp_text += f"   {medals[i]} <b>{titles[i]}</b> {escaped_name}\n"
        mvp_text += f"       {count} сообщ. → <b>+{reward:,}</b> {fire}\n"
    
    # Обычная награда
    regular_reward = int(base_reward * streak_mult)
    total_distributed = int(regular_reward * len(participants) + sum(
        int(base_reward * streak_mult * (multipliers[i] - 1)) 
        for i in range(min(3, len(top3)))
    ))
    
    streak_block = ""
    if streak >= 3:
        streak_text = _get_streak_text(streak)
        streak_block = f"\n\n{Visuals.fire()}{Visuals.fire()}{Visuals.fire()} <b>СЕРИЯ {streak}!</b> {Visuals.fire()}{Visuals.fire()}{Visuals.fire()}\n{streak_text}"
    
    # Достижения армии
    army_achievement = ""
    if len(participants) >= 20:
        army_achievement = "\n\n🏅 <b>ДОСТИЖЕНИЕ:</b> «Непобедимая Армия!»"
    elif len(participants) >= 10:
        army_achievement = "\n\n🏅 <b>ДОСТИЖЕНИЕ:</b> «Сила в единстве!»"
    
    top_border = (
        '<tg-emoji emoji-id="5318932854221069098">🤑</tg-emoji>'
        '<tg-emoji emoji-id="5318824539440831060">🤑</tg-emoji>'
        '<tg-emoji emoji-id="5319190161416803254">🤑</tg-emoji>'
        '<tg-emoji emoji-id="5319083281155643596">🤑</tg-emoji>'
        '<tg-emoji emoji-id="5316522419790307271">🤑</tg-emoji>'
        '<tg-emoji emoji-id="5319029538229868743">🤑</tg-emoji>'
        '<tg-emoji emoji-id="5318793933503879923">🤑</tg-emoji>'
        '<tg-emoji emoji-id="5316811539808807793">🤑</tg-emoji>'
    )
    bottom_border = (
        '<tg-emoji emoji-id="5415807885986789306">�</tg-emoji>'
        '<tg-emoji emoji-id="5415834669402846332">�</tg-emoji>'
        '<tg-emoji emoji-id="5415699884739161559">�</tg-emoji>'
        '<tg-emoji emoji-id="5416039273054894373">�</tg-emoji>'
        '<tg-emoji emoji-id="5415806640446271242">�</tg-emoji>'
        '<tg-emoji emoji-id="5415584968594193062">�</tg-emoji>'
        '<tg-emoji emoji-id="5416079808956232584">�</tg-emoji>'
        '<tg-emoji emoji-id="5415639209736174375">�</tg-emoji>'
        '<tg-emoji emoji-id="5415680454307117394">�</tg-emoji>'
    )
    premium_trophy = '<tg-emoji emoji-id="5447112111605964162">�</tg-emoji>'
    
    victory_wave = random.choice([
        '<tg-emoji emoji-id="5206169707635291145">🌊</tg-emoji>',
        '<tg-emoji emoji-id="5204246893726547065">🌊</tg-emoji>',
        '<tg-emoji emoji-id="5206272473317782147">🌊</tg-emoji>',
        '<tg-emoji emoji-id="5206407781967475993">🌊</tg-emoji>',
        '<tg-emoji emoji-id="5204117842844205046">🌊</tg-emoji>',
        '<tg-emoji emoji-id="5206402954424234617">🌊</tg-emoji>',
        '<tg-emoji emoji-id="5204147911910242898">🌊</tg-emoji>',
        '<tg-emoji emoji-id="5206226839290262426">🌊</tg-emoji>',
        '<tg-emoji emoji-id="5204374187967265711">🌊</tg-emoji>',
        '<tg-emoji emoji-id="5206212146207143685">🌊</tg-emoji>',
        '<tg-emoji emoji-id="5203966260563426049">🌊</tg-emoji>',
        '<tg-emoji emoji-id="5206376793778437124">🌊</tg-emoji>'
    ])
    
    return (
        f"{top_border}\n"
        f"   {premium_trophy} <b>{victory_phrase}</b> {premium_trophy}\n"
        f"{bottom_border}\n\n"
        f"{victory_wave} <b>ВОЛНА ПОКОРЕНА!</b>\n\n"
        f"{Visuals.check_raw()} Цель: <b>{current}/{target}</b>\n"
        f"👥 Бойцов: <b>{len(participants)}</b>\n"
        f"💰 Всего роздано: <b>~{total_distributed:,}</b>\n\n"
        f'<tg-emoji emoji-id="5305750989704274804">🏆</tg-emoji> <b>ГЕРОИ ВОЛНЫ:</b>\n'
        f"{mvp_text}\n"
        f"� Остальные: <b>+{regular_reward:,}</b> каждому"
        f"{streak_block}"
        f"{army_achievement}\n\n"
        f"🎁 <b>Все участники награждены!</b>"
    )


def _build_timeout_message(
    current: int,
    target: int,
    participants: Set[int],
    message_counts: Counter
) -> str:
    """Сообщение о провале."""
    percent = int((current / target) * 100) if target > 0 else 0
    remaining = target - current
    
    # Показываем кто старался
    tried_text = ""
    if message_counts:
        top3 = message_counts.most_common(3)
        medals = ["🥇", "🥈", "🥉"]
        tried_text = "\n\n💪 <b>СРАЖАЛИСЬ ДО КОНЦА:</b>\n"
        for i, (name, count) in enumerate(top3):
            escaped_name = html.escape(name[:10])
            tried_text += f"   {medals[i]} {escaped_name}: <b>{count}</b>\n"
    
    failure_border = (
        '<tg-emoji emoji-id="5431554125152156092">�</tg-emoji>'
        '<tg-emoji emoji-id="5431444113859835179">�</tg-emoji>'
        '<tg-emoji emoji-id="5429574836718434979">�</tg-emoji>'
        '<tg-emoji emoji-id="5431793767147404128">�</tg-emoji>'
        '<tg-emoji emoji-id="5431651857132976759">�</tg-emoji>'
        '<tg-emoji emoji-id="5431587518522881319">�</tg-emoji>'
        '<tg-emoji emoji-id="5429094496165992077">�</tg-emoji>'
        '<tg-emoji emoji-id="5431510853356647863">�</tg-emoji>'
    )
    
    separator_strip = (
        '<tg-emoji emoji-id="5220053631801259840">〰️</tg-emoji>'
        '<tg-emoji emoji-id="5219832002898859117">〰️</tg-emoji>'
        '<tg-emoji emoji-id="5220006417225773757">〰️</tg-emoji>'
        '<tg-emoji emoji-id="5221971124245524858">〰️</tg-emoji>'
        '<tg-emoji emoji-id="5220022682266925997">〰️</tg-emoji>'
        '<tg-emoji emoji-id="5220204900549423954">〰️</tg-emoji>'
        '<tg-emoji emoji-id="5220013993548084819">〰️</tg-emoji>'
        '<tg-emoji emoji-id="5219756243970718240">〰️</tg-emoji>'
        '<tg-emoji emoji-id="5219759332052204342">〰️</tg-emoji>'
    )
    
    return (
        f"{failure_border}\n"
        f"  😢 <b>ВОЛНА ОТКАТИЛАСЬ...</b>\n"
        f"{separator_strip}\n\n"
        f"📊 Прогресс: <b>{current}/{target}</b> ({percent}%)\n"
        f"{Visuals.cross()} Не хватило: <b>{remaining}</b> сообщений\n"
        f"👥 Бойцов: <b>{len(participants)}</b>"
        f"{tried_text}\n"
        f"🔄 <i>Серия сброшена до 0</i>\n\n"
        f"💪 <b>В следующий раз победим!</b>"
    )


def _build_cooldown_message(remaining: int, last_streak: int) -> str:
    """Кулдаун."""
    mins = remaining // 60
    secs = remaining % 60
    time_str = f"{mins}:{secs:02d}" if mins else f"{secs} сек"
    
    streak_block = ""
    if last_streak >= 3:
        streak_block = f"\n\n🔥 Текущая серия: <b>{last_streak}</b>"
    
    return (
        f"🌊 <b>ВОЛНА АКТИВА</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"{Visuals.wait()} <i>Перезарядка...</i>\n\n"
        f"⏰ Ещё <b>{time_str}</b>"
        f"{streak_block}"
    )


def _build_already_active_message(current: int, target: int, remaining: int, participants: int) -> str:
    """Волна уже активна."""
    progress = min(1.0, current / target) if target > 0 else 0
    bar = _build_wave_bar(current, target, 16)
    mins = remaining // 60
    secs = remaining % 60
    
    lines = [
        "🌊 ВОЛНА ИДЁТ!",
        "━━━━━━━━━━━━━━",
        "",
        bar,
        f"  {current}/{target}",
        "",
        f"⏰ {mins}:{secs:02d}",
        f"👥 {participants}",
        "",
        "💬 Пиши чтобы помочь!",
    ]
    return Visuals._frame(lines, width=22)


@router.message(Command("senseiwave"))
async def cmd_senseiwave(message: Message, container: Container):
    """🌊 Запустить ЭПИЧЕСКУЮ волну (только для админов)!"""
    logger.info(f"👉 [WAVE] Step 1: Command triggered by {message.from_user.id} in chat {message.chat.id}")
    
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    logger.info(f"👉 [WAVE] Step 2: Checking chat type: {message.chat.type}")
    if message.chat.type not in ("group", "supergroup"):
        logger.info(f"🌊 Wave rejected: not a group chat (type={message.chat.type})")
        await message.answer("🌊 Волна работает только в групповых чатах!")
        return
    
    # Проверяем права (админ бота или админ чата)
    logger.info(f"👉 [WAVE] Step 3: Checking permissions for user {user_id}")
    is_bot_admin = user_id in settings.admin_ids
    logger.info(f"👉 [WAVE] Step 3a: is_bot_admin = {is_bot_admin}, admin_ids = {settings.admin_ids}")
    
    if not is_bot_admin:
        try:
            member = await message.chat.get_member(user_id)
            is_chat_admin = member.status in ["creator", "administrator"]
            logger.info(f"👉 [WAVE] Step 3b: member.status = {member.status}, is_chat_admin = {is_chat_admin}")
        except Exception as e:
            logger.error(f"👉 [WAVE] Step 3c: Error getting member: {e}")
            is_chat_admin = False
        
        if not is_chat_admin:
            logger.info(f"👉 [WAVE] Step 3d: User is not admin, rejecting")
            await message.answer("🌊 Волну могут запускать только администраторы!")
            return
    
    current_time = time.time()
    
    # Проверяем активную волну
    logger.info(f"👉 [WAVE] Step 4: Checking active waves")
    if chat_id in _active_waves:
        wave = _active_waves[chat_id]
        remaining = int(wave["expires"] - current_time)
        if remaining > 0:
            logger.info(f"👉 [WAVE] Step 4a: Wave already active, {remaining}s remaining")
            msg = _build_already_active_message(
                wave["current"],
                wave["target"],
                remaining,
                len(wave["participants"])
            )
            await message.answer(msg, parse_mode="HTML")
            return
    
    # Проверяем кулдаун
    logger.info(f"👉 [WAVE] Step 5: Checking cooldown")
    if chat_id in _wave_cooldowns:
        cooldown_expires = _wave_cooldowns[chat_id]
        if current_time < cooldown_expires:
            remaining = int(cooldown_expires - current_time)
            logger.info(f"👉 [WAVE] Step 5a: On cooldown, {remaining}s remaining")
            streak = _wave_streaks.get(chat_id, 0)
            msg = _build_cooldown_message(remaining, streak)
            await message.answer(msg, parse_mode="HTML")
            return
    
    streak = _wave_streaks.get(chat_id, 0)
    duration_seconds = WAVE_DURATION_MINUTES * 60
    
    # === АНИМАЦИЯ СТАРТА ===
    anim_msg = await message.answer(
        _build_animation_frame(0),
        parse_mode="HTML"
    )
    
    for frame in range(1, WAVE_ANIMATION_FRAMES):
        await asyncio.sleep(0.4)
        try:
            await anim_msg.edit_text(
                _build_animation_frame(frame),
                parse_mode="HTML"
            )
        except TelegramBadRequest:
            pass
    
    await asyncio.sleep(0.3)
    
    # Показываем стартовое сообщение
    start_msg = _build_wave_start_message(
        WAVE_TARGET_MESSAGES,
        WAVE_DURATION_MINUTES,
        WAVE_BASE_REWARD,
        streak
    )
    await anim_msg.edit_text(start_msg, parse_mode="HTML")
    
    # Сохраняем состояние
    _active_waves[chat_id] = {
        "target": WAVE_TARGET_MESSAGES,
        "current": 0,
        "participants": set(),
        "message_counts": Counter(),  # {name: count} - для отображения
        "user_id_counts": Counter(),  # {user_id: count} - для наград MVP
        "user_names": {},  # {user_id: name}
        "expires": current_time + duration_seconds + 3,
        "message_id": anim_msg.message_id,
        "last_update": current_time,
        "container": container,
        "combo_milestone": 25,  # Следующий комбо-анонс
    }
    
    # Запускаем таймеры
    asyncio.create_task(_wave_worker(message.bot, chat_id, container))
    
    logger.info(f"🌊 EPIC Wave started in {chat_id}, target: {WAVE_TARGET_MESSAGES}")


async def _wave_worker(bot: Bot, chat_id: int, container: Container):
    """Воркер волны с обновлениями."""
    while True:
        await asyncio.sleep(WAVE_UPDATE_INTERVAL)
        
        if chat_id not in _active_waves:
            return
        
        wave = _active_waves[chat_id]
        remaining = int(wave["expires"] - time.time())
        
        # Проверяем завершение
        if remaining <= 0 or wave["current"] >= wave["target"]:
            await _finish_wave(bot, chat_id, container)
            return
        
        # Обновляем UI
        msg = _build_progress_message(
            wave["current"],
            wave["target"],
            remaining,
            wave["participants"],
            wave["message_counts"],
            _wave_streaks.get(chat_id, 0)
        )
        
        try:
            await bot.edit_message_text(
                msg,
                chat_id=chat_id,
                message_id=wave["message_id"],
                parse_mode="HTML"
            )
        except TelegramBadRequest:
            pass
        except Exception as e:
            logger.warning(f"Wave update error: {e}")


async def _finish_wave(bot: Bot, chat_id: int, container: Container):
    """Завершить волну и начислить награды."""
    if chat_id not in _active_waves:
        return
    
    wave = _active_waves.pop(chat_id)
    
    is_success = wave["current"] >= wave["target"]
    participants = wave["participants"]
    message_counts = wave["message_counts"]
    user_names = wave["user_names"]
    streak = _wave_streaks.get(chat_id, 0)
    
    if is_success:
        # Увеличиваем серию
        new_streak = streak + 1
        _wave_streaks[chat_id] = new_streak
        
        streak_mult = _get_streak_multiplier(new_streak)
        
        # Определяем топ-3 для бонусов (по user_id!)
        user_id_counts = wave.get("user_id_counts", Counter())
        top3_user_ids = [uid for uid, _ in user_id_counts.most_common(3)]
        
        # Начисляем награды
        # Подготовка данных для наград
        rewards_data = [] # List[Tuple[int, int, str]]
        total_needed = 0.0
        
        for user_id in participants:
            # Определяем множитель
            if top3_user_ids and user_id == top3_user_ids[0]:
                user_mult = WAVE_MVP_MULTIPLIER
                rank_desc = "MVP!"
            elif len(top3_user_ids) > 1 and user_id == top3_user_ids[1]:
                user_mult = WAVE_TOP2_MULTIPLIER
                rank_desc = "Top-2"
            elif len(top3_user_ids) > 2 and user_id == top3_user_ids[2]:
                user_mult = WAVE_TOP3_MULTIPLIER
                rank_desc = "Top-3"
            else:
                user_mult = 1.0
                rank_desc = ""
            
            reward = int(WAVE_BASE_REWARD * streak_mult * user_mult)
            total_needed += reward
            
            desc = f"Волна #{new_streak}" + (f" ({rank_desc})" if rank_desc else "")
            rewards_data.append((user_id, reward, desc))
            
        # Начисление через сервис экономики
        try:
            economy_service = container.economy_service

            # Депозит общей суммы из банка
            await economy_service._withdraw_from_bank(total_needed)

            # Раздаем награды участникам
            for uid, rew, desc in rewards_data:
                result = await economy_service.process_game_win(
                    user_id=uid,
                    coins=rew,
                    xp=0,  # Волна не дает XP напрямую через это (но можно добавить если нужно)
                    description=desc
                )
                if not result["success"]:
                    logger.error(f"Failed to award wave prize to user {uid}: {result}")

        except Exception as e:
            logger.error(f"Error rewarding wave participants: {e}")
        
        # Финальное сообщение
        final_msg = _build_victory_message(
            wave["current"],
            wave["target"],
            participants,
            message_counts,
            new_streak,
            WAVE_BASE_REWARD
        )
        
        logger.info(f"🌊 Wave SUCCESS in {chat_id}: {wave['current']}/{wave['target']}, {len(participants)} participants")
    else:
        # Сбрасываем серию
        _wave_streaks[chat_id] = 0
        
        final_msg = _build_timeout_message(
            wave["current"],
            wave["target"],
            participants,
            message_counts
        )
        
        logger.info(f"🌊 Wave FAILED in {chat_id}: {wave['current']}/{wave['target']}")
    
    try:
        await bot.edit_message_text(
            final_msg,
            chat_id=chat_id,
            message_id=wave["message_id"],
            parse_mode="HTML"
        )
    except Exception as e:
        logger.warning(f"Failed to edit final wave message: {e}")
    
    # Кулдаун
    _wave_cooldowns[chat_id] = time.time() + WAVE_COOLDOWN


@router.message(F.text & ~F.text.startswith("/"), HasActiveWave())
async def count_wave_message(message: Message, container: Container):
    """Подсчитывает сообщения с комбо-эффектами! Исключает команды."""
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if chat_id not in _active_waves:
        return
    
    wave = _active_waves[chat_id]
    
    if time.time() > wave["expires"]:
        return
    
    if wave["current"] >= wave["target"]:
        return
    
    # Увеличиваем счётчик
    wave["current"] += 1
    wave["participants"].add(user_id)
    
    # Сохраняем имя для статистики
    username = message.from_user.username
    first_name = message.from_user.first_name or ""
    name = f"@{username}" if username else first_name or f"#{str(user_id)[-4:]}"
    
    if user_id not in wave["user_names"]:
        wave["user_names"][user_id] = name
    
    # Счётчик по именам (для отображения)
    wave["message_counts"][name] += 1
    # Счётчик по user_id (для наград MVP)
    wave["user_id_counts"][user_id] += 1
    
    # Комбо-система
    current = wave["current"]
    milestone = wave["combo_milestone"]
    
    if current >= milestone and milestone <= wave["target"]:
        combo_msg = random.choice(COMBO_MESSAGES)
        percent = int((current / wave["target"]) * 100)
        
        try:
            combo_text = (
                f"{combo_msg}\n"
                f"📊 {current}/{wave['target']} ({percent}%)"
            )
            combo_reply = await message.answer(combo_text)
            
            # Удаляем через 3 секунды
            asyncio.create_task(_delete_after(combo_reply, 3))
        except Exception:
            pass
        
        # Следующий милестоун
        wave["combo_milestone"] = milestone + 25
    
    # Достигнута цель
    if wave["current"] >= wave["target"]:
        asyncio.create_task(_finish_wave(
            message.bot,
            chat_id,
            wave.get("container", container)
        ))


async def _delete_after(message: Message, seconds: float):
    """Удаляет сообщение через N секунд."""
    await asyncio.sleep(seconds)
    try:
        await message.delete()
    except Exception:
        pass
