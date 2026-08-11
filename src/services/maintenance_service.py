"""
🥋 Сенсей работает над ботом. Терпение, юный падаван.
"""

import random
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


# 🎭 Фразы сенсея для пользователей
SENSEI_PHRASES = [
    "🥋 Сенсей медитирует над кодом. Терпение, юный падаван...",
    "🧘 Сенсей в позе лотоса фиксит баги. Не мешай мастеру!",
    "⚔️ Сенсей сражается с демонами легаси-кода. Молись за него.",
    "🍜 Сенсей ушёл за лапшой вдохновения. Скоро вернётся!",
    "📿 Сенсей внедряет фичи. Страдай молча, как подобает ученику.",
    "🏔️ Сенсей на горе мудрости. Там нет интернета, но есть просветление.",
    "🐉 Сенсей укрощает дракона продакшена. Не отвлекай!",
    "💀 Сенсей в бою с NullPointerException. Это личное.",
    "🌸 Сенсей созерцает cherry-pick. Красота требует времени.",
    "🥢 Сенсей ест рамен и думает. Гениальность не торопят!",
    "📜 Сенсей переписывает древние скрипты. Это священный ритуал.",
    "🔮 Сенсей гадает на stack trace. Духи говорят: 'скоро'.",
    "⛩️ Сенсей в храме Git. Коммитит с чистой душой.",
    "🎋 Сенсей как бамбук — гнётся под дедлайном, но не ломается.",
    "☯️ Сенсей балансирует между 'работает' и 'почему работает'.",
]

# 🎌 Фразы для конкретных причин
SENSEI_REASONS = {
    "update": [
        "📦 Сенсей распаковывает новые техники. Ученики ждут в коридоре!",
        "⬆️ Сенсей апгрейдит додзё. Не наступай на мокрый пол!",
    ],
    "db": [
        "🗄️ Сенсей общается с духами базы данных. Они капризные.",
        "💾 Сенсей мигрирует данные. Это как переезд, только больнее.",
    ],
    "fix": [
        "🔧 Сенсей чинит то, что ты сломал. Да-да, ТЫ.",
        "🩹 Сенсей накладывает пластырь на продакшен. Классика.",
    ],
    "deploy": [
        "🚀 Сенсей деплоит в пятницу. Помолимся вместе.",
        "🎰 Сенсей крутит рулетку деплоя. Красное или чёрное?",
    ],
}

# 🏆 Фразы при выключении
SENSEI_BACK_PHRASES = [
    "🥋 Сенсей вернулся! Можешь снова страдать, но уже с новыми фичами.",
    "⚡ Сенсей закончил медитацию. Бот стал на % быстрее. Цени.",
    "🎊 Сенсей победил! Враги повержены, баги устранены (наверное).",
    "🍵 Сенсей попил чаю и всё починил. Магия!",
    "✨ Додзё снова открыто! Заходи, но разувайся.",
]


@dataclass
class MaintenanceState:
    """Состояние режима сенсея."""
    
    enabled: bool = False
    reason: str = ""
    reason_key: str = ""  # update, db, fix, deploy
    enabled_at: Optional[datetime] = None
    enabled_by: Optional[int] = None
    estimated_end: Optional[datetime] = None


class MaintenanceService:
    """🥋 Сервис мудрости сенсея."""
    
    _state: MaintenanceState = MaintenanceState()
    
    @classmethod
    def enable(
        cls,
        reason: str = "",
        reason_key: str = "",
        admin_id: Optional[int] = None,
        estimated_minutes: Optional[int] = None
    ) -> MaintenanceState:
        """Сенсей уходит в режим мудрости."""
        from datetime import timedelta
        
        cls._state = MaintenanceState(
            enabled=True,
            reason=reason,
            reason_key=reason_key,
            enabled_at=datetime.now(),
            enabled_by=admin_id,
            estimated_end=(
                datetime.now() + timedelta(minutes=estimated_minutes)
                if estimated_minutes else None
            )
        )
        
        logger.warning(f"🥋 Sensei mode ENABLED by {admin_id}")
        return cls._state
    
    @classmethod
    def disable(cls, admin_id: Optional[int] = None) -> str:
        """Сенсей возвращается."""
        cls._state = MaintenanceState(enabled=False)
        logger.info(f"✨ Sensei mode DISABLED by {admin_id}")
        return random.choice(SENSEI_BACK_PHRASES)
    
    @classmethod
    def is_enabled(cls) -> bool:
        return cls._state.enabled
    
    @classmethod
    def get_state(cls) -> MaintenanceState:
        return cls._state
    
    @classmethod
    def get_random_phrase(cls) -> str:
        """Получить случайную мудрость сенсея."""
        state = cls._state
        
        # Если есть специфичная причина
        if state.reason_key and state.reason_key in SENSEI_REASONS:
            phrases = SENSEI_REASONS[state.reason_key]
            return random.choice(phrases)
        
        return random.choice(SENSEI_PHRASES)
    
    @classmethod
    def get_suffering_time(cls) -> str:
        """Сколько уже страдаем."""
        if not cls._state.enabled_at:
            return ""
        
        mins = int((datetime.now() - cls._state.enabled_at).total_seconds() // 60)
        
        if mins < 1:
            return "⏱ Только начали страдать"
        elif mins < 5:
            return f"⏱ Страдаем уже {mins} мин. Это только начало!"
        elif mins < 15:
            return f"⏱ {mins} мин. страданий. Сенсей ценит твоё терпение."
        elif mins < 30:
            return f"⏱ {mins} мин.! Ты настоящий ученик!"
        else:
            return f"⏱ {mins} мин... Сенсей, возможно, уснул. 💤"
