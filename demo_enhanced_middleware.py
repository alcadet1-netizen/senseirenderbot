"""
Демонстрация улучшенного middleware активности пользователя.
"""

import asyncio
from unittest.mock import MagicMock, AsyncMock
from aiogram.types import User, Chat, Message

from src.bot.middlewares.user_activity import (
    ActivityConfig,
    EnhancedUserActivityMiddleware,
    MessageBuilder,
    DefaultNotificationFormatter,
    NotificationQueue,
    Notification,
    NotificationType,
    LevelUpData,
    AchievementData,
    TicketData,
    get_user_mention,
    format_number,
)


def demo_message_builder():
    """Демонстрация MessageBuilder."""
    print("=== MessageBuilder Demo ===")
    
    # Создаём тестового пользователя
    user = User(
        id=123456789,
        is_bot=False,
        first_name="Test",
        last_name="User",
        username="testuser",
    )
    
    # Демонстрация построения сообщения
    builder = MessageBuilder()
    message = (
        builder
        .title("🏆 Достижение разблокировано!")
        .separator()
        .blank_line()
        .mention(user)
        .blank_line()
        .bold("Сотня сообщений!")
        .italic("Ты отправил 100 сообщений")
        .blank_line()
        .reward(xp=500, coins=200)
        .build()
    )
    
    print("Сообщение о достижении:")
    print(message)
    print()


def demo_notification_formatter():
    """Демонстрация DefaultNotificationFormatter."""
    print("=== DefaultNotificationFormatter Demo ===")
    
    user = User(
        id=123456789,
        is_bot=False,
        first_name="Test",
        last_name="User",
        username="testuser",
    )
    
    formatter = DefaultNotificationFormatter()
    
    # Форматирование уведомления о повышении уровня
    level_data = LevelUpData(
        old_level=10,
        new_level=11,
        level_name="Advanced User"
    )
    
    level_message = formatter.format_level_up(user, level_data)
    print("Уведомление о повышении уровня:")
    print(level_message)
    print()
    
    # Форматирование уведомления о достижении
    achievement_data = AchievementData(
        id="milestone_100",
        name="Сотня сообщений",
        description="Отправлено 100 сообщений",
        xp_reward=500,
        coin_reward=200,
        rarity="rare"
    )
    
    achievement_message = formatter.format_achievement(user, achievement_data)
    print("Уведомление о достижении:")
    print(achievement_message)
    print()
    
    # Форматирование уведомления о билете
    ticket_data = TicketData(
        code="WINNER123",
        event_name="Розыгрыш призов"
    )
    
    ticket_message = formatter.format_ticket(user, ticket_data)
    print("Уведомление о билете:")
    print(ticket_message)
    print()


def demo_notification_queue():
    """Демонстрация NotificationQueue."""
    print("=== NotificationQueue Demo ===")
    
    user = User(
        id=123456789,
        is_bot=False,
        first_name="Test",
        last_name="User",
        username="testuser",
    )
    
    queue = NotificationQueue(max_per_batch=2)
    
    # Добавляем уведомления с разными приоритетами
    notifications = [
        Notification(
            type=NotificationType.TICKET,
            user=user,
            chat_id=987654321,
            text="Новый билет!",
            priority=5
        ),
        Notification(
            type=NotificationType.LEVEL_UP,
            user=user,
            chat_id=987654321,
            text="Повышение уровня!",
            priority=10  # Самый высокий приоритет
        ),
        Notification(
            type=NotificationType.ACHIEVEMENT,
            user=user,
            chat_id=987654321,
            text="Новое достижение!",
            priority=8
        ),
    ]
    
    for notification in notifications:
        queue.add(notification)
    
    print(f"Добавлено уведомлений: {len(queue)}")
    
    # Получаем пакет (должен быть отсортирован по приоритету)
    batch = queue.get_batch()
    print(f"Получено уведомлений в пакете: {len(batch)}")
    print("Приоритеты в пакете:", [n.priority for n in batch])
    print(f"Осталось в очереди: {len(queue)}")
    print()


def demo_utilities():
    """Демонстрация утилит."""
    print("=== Utilities Demo ===")
    
    # Демонстрация упоминания пользователя
    user_with_username = User(
        id=123456789,
        is_bot=False,
        first_name="Test",
        last_name="User",
        username="testuser",
    )
    
    user_without_username = User(
        id=987654321,
        is_bot=False,
        first_name="Another",
        last_name="User",
        username=None,
    )
    
    print("Упоминание пользователя с username:")
    print(get_user_mention(user_with_username))
    print()
    
    print("Упоминание пользователя без username:")
    print(get_user_mention(user_without_username))
    print()
    
    # Демонстрация форматирования чисел
    print("Форматирование чисел:")
    print(f"1234567 -> {format_number(1234567)}")
    print(f"1234.56 -> {format_number(1234.56)}")
    print(f"999 -> {format_number(999)}")
    print()


async def demo_enhanced_middleware():
    """Демонстрация EnhancedUserActivityMiddleware."""
    print("=== EnhancedUserActivityMiddleware Demo ===")
    
    # Создаём мок throttle manager
    throttle_manager = MagicMock()
    throttle_manager.throttle = AsyncMock(return_value=True)
    
    # Конфигурация middleware
    config = ActivityConfig(
        throttle_seconds=60,
        enable_achievements=True,
        enable_level_notifications=True,
        enable_ticket_notifications=True,
        enable_random_phrases=False,  # Отключаем для демонстрации
        background_processing=False,    # Синхронная обработка
        max_notifications_per_message=3,
    )
    
    # Создаём middleware
    middleware = EnhancedUserActivityMiddleware(throttle_manager, config)
    
    print("Конфигурация middleware:")
    print(f"  Throttle seconds: {config.throttle_seconds}")
    print(f"  Achievements enabled: {config.enable_achievements}")
    print(f"  Background processing: {config.background_processing}")
    print()
    
    # Демонстрация метрик
    print("Начальные метрики:")
    metrics = middleware.get_metrics()
    for key, value in metrics.items():
        print(f"  {key}: {value}")
    print()
    
    # Симуляция обработки сообщений
    print("Симуляция обработки сообщений...")
    middleware.metrics.messages_processed = 10
    middleware.metrics.notifications_sent = 5
    middleware.metrics.achievements_unlocked = 2
    middleware.metrics.level_ups = 1
    
    print("Обновлённые метрики:")
    metrics = middleware.get_metrics()
    for key, value in metrics.items():
        print(f"  {key}: {value}")
    print()
    
    # Сброс метрик
    print("Сброс метрик...")
    middleware.reset_metrics()
    metrics = middleware.get_metrics()
    print("Метрики после сброса:")
    for key, value in metrics.items():
        print(f"  {key}: {value}")
    print()


def main():
    """Главная функция демонстрации."""
    print("🚀 Демонстрация улучшенного middleware активности пользователя")
    print("=" * 60)
    print()
    
    # Запускаем демонстрации
    demo_message_builder()
    demo_notification_formatter()
    demo_notification_queue()
    demo_utilities()
    
    # Асинхронная демонстрация middleware
    asyncio.run(demo_enhanced_middleware())
    
    print("✅ Демонстрация завершена!")
    print()
    print("Основные возможности улучшенного middleware:")
    print("• Продвинутая система уведомлений с приоритетами")
    print("• Конфигурируемое поведение через ActivityConfig")
    print("• Сбор метрик и observability")
    print("• Фоновая обработка уведомлений")
    print("• Улучшенная обработка ошибок")
    print("• Rate limiting и защита от спама")
    print("• Красивое форматирование сообщений")
    print("• Поддержка различных типов уведомлений")


if __name__ == "__main__":
    main()