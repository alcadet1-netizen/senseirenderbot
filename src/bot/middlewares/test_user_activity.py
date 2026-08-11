"""
Тесты для улучшенного middleware активности пользователя.
"""

import asyncio
import logging
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.types import Message, User, Chat

from src.bot.middlewares.user_activity import (
    ActivityConfig,
    ActivityMetrics,
    ActivityProcessor,
    AchievementData,
    LevelUpData,
    TicketData,
    RewardResult,
    Notification,
    NotificationType,
    MessageBuilder,
    DefaultNotificationFormatter,
    TelegramNotificationSender,
    NotificationQueue,
    EnhancedUserActivityMiddleware,
    get_user_mention,
    format_number,
)
from src.core.container import Container
from src.infra.redis.throttling import ThrottleManager


# Тестовые данные
TEST_USER = User(
    id=123456789,
    is_bot=False,
    first_name="Test",
    last_name="User",
    username="testuser",
)

TEST_CHAT = Chat(
    id=987654321,
    type="private",
    title="Test Chat",
)

TEST_MESSAGE = Message(
    message_id=1,
    from_user=TEST_USER,
    chat=TEST_CHAT,
    date=1234567890,
)


class TestMessageBuilder:
    """Тесты для MessageBuilder."""
    
    def test_basic_message(self):
        """Тест базового построения сообщения."""
        builder = MessageBuilder()
        message = (
            builder
            .title("Test Title")
            .separator()
            .text("Regular text")
            .bold("Bold text")
            .italic("Italic text")
            .code("code")
            .build()
        )
        
        expected = "<b>Test Title</b>\n────────────────────────\nRegular text\n<b>Bold text</b>\n<i>Italic text</i>\n<code>code</code>"
        assert message == expected
    
    def test_field_formatting(self):
        """Тест форматирования полей."""
        builder = MessageBuilder()
        message = builder.field("XP", 100, "⚡").build()
        assert message == "⚡ XP: <b>100</b>"
    
    def test_user_mention(self):
        """Тест упоминания пользователя."""
        builder = MessageBuilder()
        message = builder.mention(TEST_USER).build()
        assert "@testuser" in message
    
    def test_reward_formatting(self):
        """Тест форматирования наград."""
        builder = MessageBuilder()
        message = builder.reward(xp=100, coins=50).build()
        assert "⚡ +100 XP" in message
        assert "💰 +50 монет" in message
    
    def test_level_change(self):
        """Тест форматирования изменения уровня."""
        builder = MessageBuilder()
        message = builder.level_change(1, 2, "Newbie").build()
        assert "Уровень: <b>1</b> → <b>2</b>" in message
        assert "Ранг: <i>Newbie</i>" in message


class TestDefaultNotificationFormatter:
    """Тесты для DefaultNotificationFormatter."""
    
    def setup_method(self):
        """Настройка тестов."""
        self.formatter = DefaultNotificationFormatter()
    
    def test_format_level_up(self):
        """Тест форматирования уведомления о повышении уровня."""
        level_data = LevelUpData(
            old_level=1,
            new_level=2,
            level_name="Newbie"
        )
        
        message = self.formatter.format_level_up(TEST_USER, level_data)
        assert "LEVEL UP!" in message
        assert "@testuser" in message
        assert "Уровень: <b>1</b> → <b>2</b>" in message
    
    def test_format_achievement(self):
        """Тест форматирования уведомления о достижении."""
        achievement_data = AchievementData(
            id="test_achievement",
            name="Test Achievement",
            description="Test description",
            xp_reward=100,
            coin_reward=50,
            rarity="rare"
        )
        
        message = self.formatter.format_achievement(TEST_USER, achievement_data)
        assert "Достижение разблокировано!" in message
        assert "🥇" in message  # Rare emoji
        assert "Test Achievement" in message
        assert "⚡ +100 XP" in message
        assert "💰 +50 монет" in message
    
    def test_format_ticket(self):
        """Тест форматирования уведомления о билете."""
        ticket_data = TicketData(code="TEST123")
        
        message = self.formatter.format_ticket(TEST_USER, ticket_data)
        assert "Новый билет!" in message
        assert "@testuser" in message
        assert "<code>TEST123</code>" in message
    
    def test_level_emoji_selection(self):
        """Тест выбора эмодзи для уровня."""
        assert self.formatter._get_level_emoji(5) == "⬆️"
        assert self.formatter._get_level_emoji(10) == "🌟"
        assert self.formatter._get_level_emoji(25) == "⭐"
        assert self.formatter._get_level_emoji(50) == "💫"
        assert self.formatter._get_level_emoji(100) == "🌠"


class TestNotificationQueue:
    """Тесты для NotificationQueue."""
    
    def test_queue_operations(self):
        """Тест операций с очередью."""
        queue = NotificationQueue(max_per_batch=2)
        
        # Добавляем уведомления
        notification1 = Notification(
            type=NotificationType.LEVEL_UP,
            user=TEST_USER,
            chat_id=TEST_CHAT.id,
            text="Test 1",
            priority=10
        )
        notification2 = Notification(
            type=NotificationType.ACHIEVEMENT,
            user=TEST_USER,
            chat_id=TEST_CHAT.id,
            text="Test 2",
            priority=5
        )
        notification3 = Notification(
            type=NotificationType.TICKET,
            user=TEST_USER,
            chat_id=TEST_CHAT.id,
            text="Test 3",
            priority=1
        )
        
        queue.add(notification1)
        queue.add(notification2)
        queue.add(notification3)
        
        assert len(queue) == 3
        
        # Получаем пакет (должен быть отсортирован по приоритету)
        batch = queue.get_batch()
        assert len(batch) == 2  # max_per_batch=2
        assert batch[0].priority == 10  # Наивысший приоритет
        assert batch[1].priority == 5
        
        # Очередь должна быть очищена
        assert len(queue) == 0
    
    def test_clear_queue(self):
        """Тест очистки очереди."""
        queue = NotificationQueue()
        
        notification = Notification(
            type=NotificationType.LEVEL_UP,
            user=TEST_USER,
            chat_id=TEST_CHAT.id,
            text="Test"
        )
        
        queue.add(notification)
        assert len(queue) == 1
        
        queue.clear()
        assert len(queue) == 0


class TestUtilities:
    """Тесты утилит."""
    
    def test_get_user_mention_with_username(self):
        """Тест упоминания пользователя с username."""
        mention = get_user_mention(TEST_USER)
        assert mention == "@testuser"
    
    def test_get_user_mention_without_username(self):
        """Тест упоминания пользователя без username."""
        user = User(
            id=123456789,
            is_bot=False,
            first_name="Test",
            last_name="User",
            username=None,  # Нет username
        )
        
        mention = get_user_mention(user)
        assert '<a href="tg://user?id=123456789">Test User</a>' == mention
    
    def test_format_number_integer(self):
        """Тест форматирования целого числа."""
        assert format_number(1234567) == "1 234 567"
        assert format_number(1000) == "1 000"
    
    def test_format_number_float(self):
        """Тест форматирования дробного числа."""
        assert format_number(1234.56) == "1 234.56"
        assert format_number(999.99) == "999.99"


class TestActivityProcessor:
    """Тесты для ActivityProcessor."""
    
    def setup_method(self):
        """Настройка тестов."""
        self.container = MagicMock(spec=Container)
        self.config = ActivityConfig()
        self.processor = ActivityProcessor(self.container, self.config)
    
    @pytest.mark.asyncio
    async def test_process_message_success(self):
        """Тест успешной обработки сообщения."""
        # Мокаем economy_service
        self.container.economy_service.process_message_reward = AsyncMock(return_value={
            "success": True,
            "messages_count": 10,
            "new_xp": 100,
            "new_coins": 50,
            "level_up": (1, 2, "Newbie"),
            "ticket_created": "TEST123"
        })
        
        # Мокаем achievement_service
        self.container.achievement_service.check_and_unlock_achievements = AsyncMock(return_value=[
            {
                "id": "test_achievement",
                "name": "Test Achievement",
                "description": "Test description",
                "xp_reward": 25,
                "coin_reward": 10,
                "rarity": "common"
            }
        ])
        
        notifications = await self.processor.process_message(
            user=TEST_USER,
            chat_id=TEST_CHAT.id,
            apply_rewards=True
        )
        
        # Проверяем количество уведомлений
        assert len(notifications) == 3  # level_up, ticket, achievement
        
        # Проверяем типы уведомлений
        types = [n.type for n in notifications]
        assert NotificationType.LEVEL_UP in types
        assert NotificationType.TICKET in types
        assert NotificationType.ACHIEVEMENT in types
    
    @pytest.mark.asyncio
    async def test_process_message_no_rewards(self):
        """Тест обработки сообщения без наград."""
        self.container.economy_service.process_message_reward = AsyncMock(return_value={
            "success": True,
            "messages_count": 10,
            "new_xp": 0,
            "new_coins": 0,
        })
        
        self.container.achievement_service.check_and_unlock_achievements = AsyncMock(return_value=[])
        
        notifications = await self.processor.process_message(
            user=TEST_USER,
            chat_id=TEST_CHAT.id,
            apply_rewards=False
        )
        
        assert len(notifications) == 0
    
    @pytest.mark.asyncio
    async def test_process_message_error(self):
        """Тест обработки сообщения с ошибкой."""
        self.container.economy_service.process_message_reward = AsyncMock(
            side_effect=Exception("Service error")
        )
        
        notifications = await self.processor.process_message(
            user=TEST_USER,
            chat_id=TEST_CHAT.id,
            apply_rewards=True
        )
        
        assert len(notifications) == 0


class TestEnhancedUserActivityMiddleware:
    """Тесты для EnhancedUserActivityMiddleware."""
    
    def setup_method(self):
        """Настройка тестов."""
        self.throttle_manager = MagicMock(spec=ThrottleManager)
        self.config = ActivityConfig()
        self.middleware = EnhancedUserActivityMiddleware(
            self.throttle_manager,
            self.config
        )
    
    @pytest.mark.asyncio
    async def test_middleware_valid_event(self):
        """Тест middleware с валидным событием."""
        # Мокаем throttle
        self.throttle_manager.throttle = AsyncMock(return_value=True)
        
        # Мокаем контейнер
        container = MagicMock(spec=Container)
        container.economy_service.process_message_reward = AsyncMock(return_value={
            "success": True,
            "messages_count": 1,
            "new_xp": 10,
            "new_coins": 5,
        })
        container.achievement_service.check_and_unlock_achievements = AsyncMock(return_value=[])
        
        # Мокаем обработчик
        handler = AsyncMock(return_value="handler_result")
        
        # Данные middleware
        data = {"container": container}
        
        # Мокаем бота
        TEST_MESSAGE.bot = MagicMock()
        
        result = await self.middleware(handler, TEST_MESSAGE, data)
        
        # Проверяем, что обработчик был вызван
        handler.assert_called_once_with(TEST_MESSAGE, data)
        assert result == "handler_result"
    
    @pytest.mark.asyncio
    async def test_middleware_invalid_event(self):
        """Тест middleware с невалидным событием."""
        # Создаём сообщение без пользователя
        invalid_message = Message(
            message_id=1,
            from_user=None,
            chat=TEST_CHAT,
            date=1234567890,
        )
        
        handler = AsyncMock(return_value="handler_result")
        data = {}
        
        result = await self.middleware(handler, invalid_message, data)
        
        # Обработчик должен быть вызван без обработки активности
        handler.assert_called_once_with(invalid_message, data)
        assert result == "handler_result"
    
    def test_metrics_collection(self):
        """Тест сбора метрик."""
        # Проверяем начальные метрики
        metrics = self.middleware.get_metrics()
        assert metrics["messages_processed"] == 0
        assert metrics["errors"] == 0
        
        # Симулируем обработку сообщений
        self.middleware.metrics.messages_processed = 5
        self.middleware.metrics.errors = 1
        
        metrics = self.middleware.get_metrics()
        assert metrics["messages_processed"] == 5
        assert metrics["errors"] == 1
    
    def test_metrics_reset(self):
        """Тест сброса метрик."""
        # Устанавливаем метрики
        self.middleware.metrics.messages_processed = 10
        self.middleware.metrics.errors = 2
        
        # Сбрасываем метрики
        self.middleware.reset_metrics()
        
        metrics = self.middleware.get_metrics()
        assert metrics["messages_processed"] == 0
        assert metrics["errors"] == 0
    
    def test_configuration(self):
        """Тест конфигурации middleware."""
        # Проверяем конфигурацию по умолчанию
        assert self.middleware.config.throttle_seconds == THROTTLE_RATE_LIMIT_MESSAGES
        assert self.middleware.config.enable_achievements is True
        
        # Создаём middleware с кастомной конфигурацией
        custom_config = ActivityConfig(
            throttle_seconds=300,
            enable_achievements=False,
            background_processing=False
        )
        
        custom_middleware = EnhancedUserActivityMiddleware(
            self.throttle_manager,
            custom_config
        )
        
        assert custom_middleware.config.throttle_seconds == 300
        assert custom_middleware.config.enable_achievements is False
        assert custom_middleware.config.background_processing is False


@pytest.mark.asyncio
async def test_integration():
    """Интеграционный тест middleware."""
    # Создаём полный стек
    throttle_manager = MagicMock(spec=ThrottleManager)
    throttle_manager.throttle = AsyncMock(return_value=True)
    
    config = ActivityConfig(
        enable_random_phrases=False,  # Отключаем случайные фразы для теста
        background_processing=False,  # Синхронная обработка
    )
    
    middleware = EnhancedUserActivityMiddleware(throttle_manager, config)
    
    # Мокаем контейнер и сервисы
    container = MagicMock(spec=Container)
    container.economy_service.process_message_reward = AsyncMock(return_value={
        "success": True,
        "messages_count": 100,
        "new_xp": 1000,
        "new_coins": 500,
        "level_up": (10, 11, "Advanced"),
        "ticket_created": "WINNER123"
    })
    container.achievement_service.check_and_unlock_achievements = AsyncMock(return_value=[
        {
            "id": "milestone_100",
            "name": "Сотня сообщений",
            "description": "Отправлено 100 сообщений",
            "xp_reward": 500,
            "coin_reward": 200,
            "rarity": "rare"
        }
    ])
    
    # Мокаем бота
    bot = MagicMock()
    bot.send_message = AsyncMock()
    
    # Создаём тестовое сообщение
    message = Message(
        message_id=1,
        from_user=TEST_USER,
        chat=TEST_CHAT,
        date=1234567890,
    )
    message.bot = bot
    
    # Мокаем обработчик
    handler = AsyncMock(return_value="success")
    
    # Данные middleware
    data = {"container": container}
    
    # Запускаем middleware
    result = await middleware(handler, message, data)
    
    # Проверяем результаты
    assert result == "success"
    handler.assert_called_once()
    
    # Проверяем метрики
    metrics = middleware.get_metrics()
    assert metrics["messages_processed"] == 1
    
    # Проверяем, что уведомления были отправлены
    # (в синхронном режиме должны быть отправлены сразу)
    assert bot.send_message.called


if __name__ == "__main__":
    # Запускаем базовые тесты
    pytest.main([__file__, "-v"])