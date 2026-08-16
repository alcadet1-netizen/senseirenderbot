"""
📊 Middleware для отслеживания активности пользователей.
Модуль предоставляет production-ready middleware для:
- Отслеживания и награждения активности
- Уведомлений о достижениях и уровнях
- Rate limiting и защиты от спама
- Сбора метрик и observability

Author: Your Team
Version: 2.0.0
"""
from __future__ import annotations

import asyncio
import logging
import random
import time
from abc import ABC, abstractmethod
from contextlib import suppress
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Final,
    List,
    Optional,
    Protocol,
    TypeAlias,
    TypedDict,
    Union,
)

from aiogram import BaseMiddleware, Bot
from aiogram.types import Message, User

from src.core.constants import RANDOM_MESSAGE_CHANCE, THROTTLE_RATE_LIMIT_MESSAGES
from src.core.container import Container
from src.core.visuals import Visuals
from src.services.throttle_service import ThrottleService
from src.texts.phrases import get_random_phrase

#
#                                 CONFIGURATION
#
logger: Final[logging.Logger] = logging.getLogger(__name__)

# Type aliases
HandlerType: TypeAlias = Callable[[Message, Dict[str, Any]], Awaitable[Any]]
MiddlewareData: TypeAlias = Dict[str, Any]


@dataclass(frozen=True, slots=True)
class ActivityConfig:
    """
    Конфигурация middleware активности.

    Attributes:
        throttle_seconds: Интервал между начислением наград (в секундах)
        random_phrase_chance: Вероятность отправки случайной фразы (0.0-1.0)
        notification_cooldown: Cooldown между уведомлениями одного типа
        max_notifications_per_message: Максимум уведомлений на одно сообщение
        enable_achievements: Включить проверку достижений
        enable_level_notifications: Включить уведомления о level up
        enable_ticket_notifications: Включить уведомления о билетах
        enable_random_phrases: Включить случайные фразы
        background_processing: Обрабатывать уведомления в фоне
    """
    throttle_seconds: int = THROTTLE_RATE_LIMIT_MESSAGES
    random_phrase_chance: float = RANDOM_MESSAGE_CHANCE
    notification_cooldown: int = 60
    max_notifications_per_message: int = 3
    enable_achievements: bool = True
    enable_level_notifications: bool = True
    enable_ticket_notifications: bool = True
    enable_random_phrases: bool = True
    background_processing: bool = True


#
#                                 DATA MODELS
#

class NotificationType(Enum):
    """Типы уведомлений."""
    LEVEL_UP = auto()
    ACHIEVEMENT = auto()
    TICKET = auto()
    RANDOM_PHRASE = auto()


@dataclass(slots=True)
class LevelUpData:
    """Данные о повышении уровня."""
    old_level: int
    new_level: int
    level_name: str
    bonus_coins: int = 0
    bonus_xp: int = 0


@dataclass(slots=True)
class AchievementData:
    """Данные о достижении."""
    id: str
    name: str
    description: str
    xp_reward: int
    coin_reward: int
    rarity: str = "common"
    icon: str = "🏆"


@dataclass(slots=True)
class TicketData:
    """Данные о билете."""
    code: str
    event_name: Optional[str] = None


@dataclass(slots=True)
class RewardResult:
    """Результат обработки награды."""
    success: bool
    messages_count: int = 0
    new_xp: int = 0
    new_coins: int = 0
    level_up: Optional[LevelUpData] = None
    ticket: Optional[TicketData] = None
    error: Optional[str] = None


@dataclass(slots=True)
class Notification:
    """Уведомление для отправки."""
    type: NotificationType
    user: User
    chat_id: int
    text: str
    priority: int = 0  # Выше = важнее
    silent: bool = False


@dataclass
class ActivityMetrics:
    """Метрики активности для observability."""
    messages_processed: int = 0
    rewards_granted: int = 0
    rewards_throttled: int = 0
    achievements_unlocked: int = 0
    level_ups: int = 0
    notifications_sent: int = 0
    notifications_failed: int = 0
    errors: int = 0
    processing_time_ms: List[float] = field(default_factory=list)

    def record_processing_time(self, duration_ms: float) -> None:
        """Записывает время обработки (хранит последние 1000)."""
        self.processing_time_ms.append(duration_ms)
        if len(self.processing_time_ms) > 1000:
            self.processing_time_ms = self.processing_time_ms[-1000:]

    @property
    def avg_processing_time_ms(self) -> float:
        """Среднее время обработки."""
        if not self.processing_time_ms:
            return 0.0
        return sum(self.processing_time_ms) / len(self.processing_time_ms)

    def to_dict(self) -> Dict[str, Any]:
        """Конвертирует в словарь для логирования/мониторинга."""
        return {
            "messages_processed": self.messages_processed,
            "rewards_granted": self.rewards_granted,
            "rewards_throttled": self.rewards_throttled,
            "achievements_unlocked": self.achievements_unlocked,
            "level_ups": self.level_ups,
            "notifications_sent": self.notifications_sent,
            "notifications_failed": self.notifications_failed,
            "errors": self.errors,
            "avg_processing_time_ms": round(self.avg_processing_time_ms, 2),
        }


#
#                              PROTOCOLS & INTERFACES
#

class NotificationFormatter(Protocol):
    """Протокол для форматтеров уведомлений."""

    def format(self, notification: Notification) -> str:
        """Форматирует уведомление в текст."""
        ...


class NotificationSender(Protocol):
    """Протокол для отправителей уведомлений."""

    async def send(self, bot: Bot, notification: Notification) -> bool:
        """Отправляет уведомление. Возвращает успех."""
        ...


class RewardProcessor(Protocol):
    """Протокол для обработчиков наград."""

    async def process(
        self,
        user_id: int,
        username: Optional[str],
        first_name: str,
        last_name: Optional[str],
        apply_rewards: bool
    ) -> RewardResult:
        """Обрабатывает награду за сообщение."""
        ...


#
#                              NOTIFICATION SYSTEM
#

class MessageBuilder:
    """
    Builder для создания форматированных сообщений.

    Использует Fluent Interface для удобного построения сообщений.

    Example:
        >>> msg = (MessageBuilder()
        ...     .title("🏆 Достижение!")
        ...     .separator()
        ...     .mention(user)
        ...     .blank_line()
        ...     .field("Награда", "+100 XP")
        ...     .build())
    """

    SEPARATOR: Final[str] = "─" * 24

    def __init__(self) -> None:
        self._lines: List[str] = []

    def title(self, text: str, bold: bool = True) -> "MessageBuilder":
        """Добавляет заголовок."""
        formatted = f"<b>{text}</b>" if bold else text
        self._lines.append(formatted)
        return self

    def separator(self, char: str = "─", length: int = 24) -> "MessageBuilder":
        """Добавляет разделитель."""
        self._lines.append(char * length)
        return self

    def blank_line(self) -> "MessageBuilder":
        """Добавляет пустую строку."""
        self._lines.append("")
        return self

    def text(self, text: str) -> "MessageBuilder":
        """Добавляет обычный текст."""
        self._lines.append(text)
        return self

    def bold(self, text: str) -> "MessageBuilder":
        """Добавляет жирный текст."""
        self._lines.append(f"<b>{text}</b>")
        return self

    def italic(self, text: str) -> "MessageBuilder":
        """Добавляет курсивный текст."""
        self._lines.append(f"<i>{text}</i>")
        return self

    def code(self, text: str) -> "MessageBuilder":
        """Добавляет моноширинный текст."""
        self._lines.append(f"<code>{text}</code>")
        return self

    def field(
        self,
        label: str,
        value: Any,
        emoji: str = ""
    ) -> "MessageBuilder":
        """Добавляет поле с меткой и значением."""
        prefix = f"{emoji} " if emoji else ""
        self._lines.append(f"{prefix}{label}: <b>{value}</b>")
        return self

    def mention(self, user: User, prefix: str = "👤") -> "MessageBuilder":
        """Добавляет упоминание пользователя."""
        mention_text = get_user_mention(user)
        self._lines.append(f"{prefix} {mention_text}")
        return self

    def reward(self, xp: int = 0, coins: int = 0) -> "MessageBuilder":
        """Добавляет строки с наградами."""
        if xp > 0:
            self._lines.append(f"⚡ +{format_number(xp)} XP")
        if coins > 0:
            self._lines.append(f"💰 +{format_number(coins)} монет")
        return self

    def level_change(
        self,
        old_level: int,
        new_level: int,
        level_name: str
    ) -> "MessageBuilder":
        """Добавляет информацию о смене уровня."""
        self._lines.append(f"📊 Уровень: <b>{old_level}</b> → <b>{new_level}</b>")
        self._lines.append(f"🏅 Ранг: <i>{level_name}</i>")
        return self

    def build(self) -> str:
        """Собирает финальное сообщение."""
        return "\n".join(self._lines)


class DefaultNotificationFormatter:
    """Форматтер уведомлений по умолчанию."""

    # Эмодзи для разных редкостей достижений
    RARITY_EMOJI: Final[Dict[str, str]] = {
        "common": "🥉",
        "uncommon": "🥈",
        "rare": "🥇",
        "epic": "💎",
        "legendary": "👑",
    }

    # Эмодзи для уровней
    LEVEL_EMOJI: Final[Dict[int, str]] = {
        10: "🌟",
        25: "⭐",
        50: "💫",
        100: "🌠",
    }

    def format_level_up(self, user: User, data: LevelUpData) -> str:
        """Форматирует уведомление о повышении уровня."""
        username = user.username or user.full_name or "Sensei User"
        return Visuals.get_level_up_animation(
            level=data.new_level,
            level_name=data.level_name,
            username=username
        )

    def format_achievement(self, user: User, data: AchievementData) -> str:
        """Форматирует уведомление о достижении."""
        emoji = self.RARITY_EMOJI.get(data.rarity, "🏆")

        rewards_list = []
        if data.xp_reward > 0:
            rewards_list.append(f"+{data.xp_reward} XP")
        if data.coin_reward > 0:
            rewards_list.append(f"+{data.coin_reward}  💰")

        rewards_str = " ".join(rewards_list)

        name = Visuals.escape(data.name)
        description = Visuals.escape(data.description)

        # Line 1: Emoji Name | Rewards
        line1 = f"{emoji} {name}"
        if rewards_str:
            line1 += f" | {rewards_str}"

        # Line 2: Description
        line2 = description

        return f"<code>{line1}\n{line2}</code>"

    def format_ticket(self, user: User, data: TicketData) -> str:
        """Форматирует уведомление о новом билете."""
        builder = (
            MessageBuilder()
            .title("🎫 Новый билет!")
            .separator()
            .blank_line()
            .mention(user)
            .blank_line()
            .field("Код", "", "🎟")
        )

        # Код билета отдельно для копирования
        builder.code(data.code)
        builder.blank_line()
        builder.italic("Используй в следующем розыгрыше!")

        return builder.build()

    def _get_level_emoji(self, level: int) -> str:
        """Возвращает эмодзи для уровня."""
        for threshold, emoji in sorted(
            self.LEVEL_EMOJI.items(),
            reverse=True
        ):
            if level >= threshold:
                return emoji
        return "⬆️"


class TelegramNotificationSender:
    """Отправитель уведомлений через Telegram."""

    def __init__(
        self,
        throttle_service: ThrottleService,
        cooldown_seconds: int = 60
    ):
        self._throttle = throttle_service
        self._cooldown = cooldown_seconds
        self._formatter = DefaultNotificationFormatter()

    async def send(self, bot: Bot, notification: Notification) -> bool:
        """
        Отправляет уведомление в Telegram.

        Args:
            bot: Экземпляр бота
            notification: Уведомление для отправки

        Returns:
            True если успешно отправлено
        """
        # Проверяем cooldown для пользователя и типа уведомления
        cooldown_key = f"{notification.user.id}:{notification.type.name}"

        is_throttled = not await self._throttle.throttle(
            key=cooldown_key,
            limit_seconds=self._cooldown,
            scope="notification_cooldown"
        )

        if is_throttled:
            logger.debug(
                f"Notification throttled for user {notification.user.id}, "
                f"type: {notification.type.name}"
            )
            return False

        try:
            await bot.send_message(
                chat_id=notification.chat_id,
                text=notification.text,
                parse_mode="HTML",
                disable_notification=notification.silent,
            )
            return True

        except Exception as e:
            logger.warning(
                f"Failed to send notification to chat {notification.chat_id}: {e}"
            )
            return False


class NotificationQueue:
    """
    Очередь уведомлений с приоритетами.

    Позволяет собирать уведомления и отправлять их пакетно,
    с учётом приоритетов и лимитов.
    """

    def __init__(self, max_per_batch: int = 3):
        self._queue: List[Notification] = []
        self._max_per_batch = max_per_batch

    def add(self, notification: Notification) -> None:
        """Добавляет уведомление в очередь."""
        self._queue.append(notification)

    def get_batch(self) -> List[Notification]:
        """
        Возвращает пакет уведомлений для отправки.

        Сортирует по приоритету и обрезает до лимита.
        """
        # Сортируем по приоритету (выше = важнее)
        sorted_queue = sorted(
            self._queue,
            key=lambda n: n.priority,
            reverse=True
        )

        # Возвращаем первые N
        batch = sorted_queue[:self._max_per_batch]

        # Очищаем очередь
        self._queue.clear()

        return batch

    def clear(self) -> None:
        """Очищает очередь."""
        self._queue.clear()

    def __len__(self) -> int:
        return len(self._queue)


#
#                                   UTILITIES
#

def get_user_mention(user: User) -> str:
    """
    Формирует кликабельное упоминание пользователя.

    Args:
        user: Объект пользователя Telegram

    Returns:
        HTML-форматированное упоминание
    """
    if user.username:
        return f"@{user.username}"

    name = user.full_name or f"User {user.id}"
    # Экранируем HTML-символы в имени
    safe_name = (
        name
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    return f'<a href="tg://user?id={user.id}">{safe_name}</a>'


def format_number(value: Union[int, float]) -> str:
    """
    Форматирует число с разделителями тысяч.

    Args:
        value: Число для форматирования

    Returns:
        Отформатированная строка

    Examples:
        >>> format_number(1234567)
        '1 234 567'
        >>> format_number(1234.56)
        '1 234.56'
    """
    if isinstance(value, float):
        return f"{value:,.2f}".replace(",", " ")
    return f"{value:,}".replace(",", " ")


#
#                              ACTIVITY PROCESSOR
#

class ActivityProcessor:
    """
    Процессор активности пользователя.

    Инкапсулирует логику обработки активности, создания уведомлений
    и проверки достижений. Следует принципу Single Responsibility.
    """

    def __init__(
        self,
        container: Container,
        config: ActivityConfig,
        formatter: Optional[DefaultNotificationFormatter] = None,
    ):
        self._container = container
        self._config = config
        self._formatter = formatter or DefaultNotificationFormatter()

    async def process_message(
        self,
        user: User,
        chat_id: int,
        apply_rewards: bool,
    ) -> List[Notification]:
        """
        Обрабатывает сообщение пользователя.

        Args:
            user: Пользователь Telegram
            chat_id: ID чата
            apply_rewards: Применять ли награды

        Returns:
            Список уведомлений для отправки
        """
        notifications: List[Notification] = []

        # Обрабатываем награду за сообщение
        result = await self._process_reward(user, apply_rewards)

        if not result.success:
            logger.debug(f"Reward processing failed for {user.id}: {result.error}")
            return notifications

        # Создаём уведомления
        if result.level_up and self._config.enable_level_notifications:
            notifications.append(
                self._create_level_up_notification(user, chat_id, result.level_up)
            )

        if result.ticket and self._config.enable_ticket_notifications:
            notifications.append(
                self._create_ticket_notification(user, chat_id, result.ticket)
            )

        # Проверяем достижения
        if self._config.enable_achievements:
            achievement_notifications = await self._check_achievements(
                user, chat_id, result
            )
            notifications.extend(achievement_notifications)

        return notifications

    async def _process_reward(
        self,
        user: User,
        apply_rewards: bool
    ) -> RewardResult:
        """Обрабатывает награду за сообщение."""
        try:
            raw_result = await self._container.economy_service.process_message_reward(
                user_id=user.id,
                username=user.username,
                first_name=user.first_name or "",
                last_name=user.last_name,
                is_bot=user.is_bot or False,
                apply_rewards=apply_rewards,
            )

            if not raw_result or not raw_result.get("success"):
                return RewardResult(
                    success=False,
                    error=raw_result.get("error") if raw_result else "Unknown error"
                )

            # Парсим level up
            level_up_data = None
            if raw_result.get("level_up"):
                old, new, name = raw_result["level_up"]
                level_up_data = LevelUpData(
                    old_level=old,
                    new_level=new,
                    level_name=name,
                )

            # Парсим билет
            ticket_data = None
            if raw_result.get("ticket_created"):
                ticket_data = TicketData(code=raw_result["ticket_created"])

            return RewardResult(
                success=True,
                messages_count=raw_result.get("messages_count", 0),
                new_xp=raw_result.get("new_xp", 0),
                new_coins=raw_result.get("new_coins", 0),
                level_up=level_up_data,
                ticket=ticket_data,
            )

        except Exception as e:
            logger.error(f"Error processing reward for user {user.id}: {e}")
            return RewardResult(success=False, error=str(e))

    def _create_level_up_notification(
        self,
        user: User,
        chat_id: int,
        level_up: LevelUpData
    ) -> Notification:
        """Создаёт уведомление о повышении уровня."""
        text = self._formatter.format_level_up(user, level_up)
        return Notification(
            type=NotificationType.LEVEL_UP,
            user=user,
            chat_id=chat_id,
            text=text,
            priority=10,  # Высокий приоритет
        )

    def _create_ticket_notification(
        self,
        user: User,
        chat_id: int,
        ticket: TicketData
    ) -> Notification:
        """Создаёт уведомление о новом билете."""
        text = self._formatter.format_ticket(user, ticket)
        return Notification(
            type=NotificationType.TICKET,
            user=user,
            chat_id=chat_id,
            text=text,
            priority=5,  # Средний приоритет
        )

    async def _check_achievements(
        self,
        user: User,
        chat_id: int,
        result: RewardResult
    ) -> List[Notification]:
        """Проверяет и создаёт уведомления о достижениях."""
        notifications: List[Notification] = []

        try:
            achievements = await self._container.achievement_service.check_and_unlock_achievements(
                user_id=user.id,
                context={
                    "messages_count": result.messages_count,
                    "xp": result.new_xp,
                    "coins": result.new_coins,
                }
            )

            for ach in achievements:
                achievement_data = AchievementData(
                    id=ach.get("id", ""),
                    name=ach.get("name", ""),
                    description=ach.get("description", ""),
                    xp_reward=ach.get("xp_reward", 0),
                    coin_reward=ach.get("coin_reward", 0),
                    rarity=ach.get("rarity", "common"),
                    icon=ach.get("icon", "🏆"),
                )

                text = self._formatter.format_achievement(user, achievement_data)
                notification = Notification(
                    type=NotificationType.ACHIEVEMENT,
                    user=user,
                    chat_id=chat_id,
                    text=text,
                    priority=8,  # Высокий приоритет
                )
                notifications.append(notification)

        except Exception as e:
            logger.error(f"Error checking achievements for user {user.id}: {e}")

        return notifications


#
#                              ENHANCED MIDDLEWARE
#

class EnhancedUserActivityMiddleware(BaseMiddleware):
    """
    Улучшенный middleware для обработки активности пользователя.

    Основные возможности:
    - Продвинутая система уведомлений с приоритетами
    - Сбор метрик и observability
    - Конфигурируемое поведение через ActivityConfig
    - Фоновая обработка уведомлений
    - Улучшенная обработка ошибок
    - Rate limiting и защита от спама
    """

    def __init__(
        self,
        container: Container,
        config: Optional[ActivityConfig] = None,
    ):
        self.throttle = container.throttle_service
        self.config = config or ActivityConfig()
        self.metrics = ActivityMetrics()
        self._notification_queue = NotificationQueue(
            max_per_batch=self.config.max_notifications_per_message
        )

        # Инициализируем sender при первом использовании
        self._sender: Optional[TelegramNotificationSender] = None

    async def __call__(
        self,
        handler: HandlerType,
        event: Message,
        data: MiddlewareData,
    ) -> Any:
        """
        Основной метод middleware.

        Args:
            handler: Следующий обработчик в цепочке
            event: Сообщение от пользователя
            data: Данные middleware

        Returns:
            Результат выполнения следующего обработчика
        """
        start_time = time.time()
        logger.info(f"[USER_ACTIVITY] Start processing message from user {event.from_user.id if event.from_user else 'Unknown'}")

        try:
            # Проверяем валидность события
            if not self._is_valid_event(event):
                return await handler(event, data)

            # Обрабатываем активность
            await self._process_user_activity(event, data)

            # Обновляем метрики
            self._update_metrics(success=True, processing_time=start_time)

        except Exception as e:
            self._update_metrics(success=False, error=e)
            logger.error(f"Error in activity middleware: {e}", exc_info=True)

        # Всегда продолжаем обработку
        duration_ms = (time.time() - start_time) * 1000
        logger.info(f"[USER_ACTIVITY] Finished processing message from user {event.from_user.id if event.from_user else 'Unknown'} in {duration_ms:.2f} ms")
        return await handler(event, data)

    def _is_valid_event(self, event: Message) -> bool:
        """Проверяет валидность события для обработки."""
        if not isinstance(event, Message):
            return False

        if not event.from_user:
            return False

        # Игнорируем служебные сообщения
        if event.content_type and event.content_type in ["migrate_to_chat_id", "migrate_from_chat_id"]:
            return False

        return True

    async def _process_user_activity(
        self,
        event: Message,
        data: MiddlewareData
    ) -> None:
        """Обрабатывает активность пользователя."""
        user = event.from_user
        user_id = user.id
        chat_id = event.chat.id

        # Проверяем throttle для наград
        # Награды начисляем только в групповых чатах (не в лс)
        is_private = event.chat.type == "private"
        can_reward = False

        if not is_private:
            # Temporarily disable throttling for message rewards
            can_reward = True
            # Original code (to restore later):
            # can_reward = await self.throttle.throttle(
            #     key=str(user_id),
            #     limit_seconds=self.config.throttle_seconds,
            #     scope="message_rewards"
            # )

        # Получаем контейнер сервисов
        container: Container = data.get("container")
        if not container:
            logger.warning(f"Container not found in middleware data for user {user_id}")
            return

        # Создаём процессор активности
        processor = ActivityProcessor(container, self.config)

        # Обрабатываем сообщение и получаем уведомления
        notifications = await processor.process_message(
            user=user,
            chat_id=chat_id,
            apply_rewards=can_reward
        )

        # Добавляем уведомления в очередь
        for notification in notifications:
            self._notification_queue.add(notification)

        # Отправляем уведомления
        await self._send_notifications(event.bot)

        # Обрабатываем случайные фразы
        if self.config.enable_random_phrases and random.random() < self.config.random_phrase_chance:
            await self._handle_random_phrase(event, user, chat_id)

    async def _send_notifications(self, bot: Bot) -> None:
        """Отправляет накопленные уведомления."""
        if not self._sender:
            self._sender = TelegramNotificationSender(
                self.throttle,
                cooldown_seconds=self.config.notification_cooldown
            )

        # Получаем пакет уведомлений
        batch = self._notification_queue.get_batch()

        if not batch:
            return

        if self.config.background_processing:
            # Фоновая обработка
            asyncio.create_task(self._send_notification_batch(bot, batch))
        else:
            # Синхронная обработка
            await self._send_notification_batch(bot, batch)

    async def _send_notification_batch(
        self,
        bot: Bot,
        batch: List[Notification]
    ) -> None:
        """Отправляет пакет уведомлений."""
        for notification in batch:
            try:
                success = await self._sender.send(bot, notification)
                if success:
                    self.metrics.notifications_sent += 1
                else:
                    self.metrics.notifications_failed += 1
            except Exception as e:
                logger.error(f"Failed to send notification: {e}")
                self.metrics.notifications_failed += 1

    async def _handle_random_phrase(
        self,
        event: Message,
        user: User,
        chat_id: int
    ) -> None:
        """Обрабатывает отправку случайной фразы."""
        try:
            phrase = get_random_phrase()
            if phrase:
                notification = Notification(
                    type=NotificationType.RANDOM_PHRASE,
                    user=user,
                    chat_id=chat_id,
                    text=phrase,
                    priority=-1,  # Низкий приоритет
                    silent=True,
                )

                if self._sender:
                    await self._sender.send(event.bot, notification)

        except Exception as e:
            logger.debug(f"Failed to send random phrase: {e}")

    def _update_metrics(
        self,
        success: bool = True,
        processing_time: Optional[float] = None,
        error: Optional[Exception] = None
    ) -> None:
        """Обновляет метрики middleware."""
        self.metrics.messages_processed += 1

        if not success:
            self.metrics.errors += 1

        if processing_time:
            duration_ms = (time.time() - processing_time) * 1000
            self.metrics.record_processing_time(duration_ms)

    def get_metrics(self) -> Dict[str, Any]:
        """Возвращает текущие метрики."""
        return self.metrics.to_dict()

    def reset_metrics(self) -> None:
        """Сбрасывает метрики."""
        self.metrics = ActivityMetrics()


# Для обратной совместимости - экспортируем оригинальный middleware
UserActivityMiddleware = EnhancedUserActivityMiddleware