"""
🚀 Точка входа SENSEI ULTIMATE 2.1.
"""

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand

from src.bot import create_bot, create_dispatcher
from src.bot.handlers import setup_routers
from src.bot.middlewares import (
    DatabaseMiddleware,
    DependencyMiddleware,
    ThrottlingMiddleware,
    LoggingMiddleware,
    MaintenanceMiddleware,
    UserActivityMiddleware,
    ModerationMiddleware,
    ChatActivityMiddleware,
    SubscriptionMiddleware,
)
from src.bot.middlewares.digest import DigestMiddleware
from src.bot.middlewares.cleanup import CommandCleanupMiddleware
from src.core.config import settings
from src.core.container import Container
from src.core.logger import setup_logging
from src.infra.database import session_factory, engine
from src.infra.database.models import Base
from src.infra.redis import redis_client
from src.infra.redis.throttling import ThrottleManager
from src.infra.database.migrations.run import run_migrations


# Настройка логирования
setup_logging()
logger = logging.getLogger(__name__)


async def setup_bot_commands(bot: Bot) -> None:
    """Установка команд бота."""
    commands = [
        BotCommand(command="senseihelp", description="📋 Помощь"),
        BotCommand(command="mysensei", description="👤 Мой профиль"),
        BotCommand(command="senseitop", description="🏆 Топ игроков"),
        BotCommand(command="senseidaily", description="🎁 Ежедневный бонус"),
        BotCommand(command="senseiobmen", description="💱 Обмен валют"),
        BotCommand(command="senseiviktorina", description="🎮 Викторина"),
    ]
    await bot.set_my_commands(commands)


async def on_startup(bot: Bot, container: Container) -> None:
    """Действия при запуске."""
    logger.info("🥋 SENSEI ULTIMATE 2.1 starting...")
    
    # Запускаем миграции
    await run_migrations()
    logger.info("✅ Database migrations completed")
    
    # Заполняем достижения
    count = await container.achievement_service.seed_achievements()
    if count > 0:
        logger.info(f"✅ Seeded {count} achievements")

    # Загружаем кэш модерации
    await container.moderation_service.load_muted_users_cache()
    logger.info("✅ Moderation cache loaded")

    # Запускаем мониторинг активности чатов
    await container.chat_activity_service.start_monitoring(bot)
    logger.info("✅ Chat activity monitoring started")
    
    # Устанавливаем команды
    await setup_bot_commands(bot)
    logger.info("✅ Bot commands set")
    
    logger.info("🚀 Bot started successfully!")


async def on_shutdown(bot: Bot, container: Container | None = None) -> None:
    """Действия при остановке."""
    logger.info("🛑 Shutting down...")
    
    if container:
        # Возвращаем ставки из активных дуэлей
        await container.duel_service.shutdown()
        logger.info("✅ Active duels refunded")
    
    await redis_client.disconnect()
    await engine.dispose()
    logger.info("👋 Goodbye!")


async def main() -> None:
    """Главная функция."""
    # Создаём бота и диспетчер
    bot = create_bot()
    dp = create_dispatcher()
    
    # Подключаемся к Redis
    redis = await redis_client.connect()
    logger.info("✅ Redis connected")
    
    # Создаём контейнер
    container = Container(
        settings=settings,
        session_factory=session_factory,
        redis=redis,
    )
    
    # Создаём throttle manager
    throttle_manager = ThrottleManager(redis)
    
    # Регистрируем middleware для сообщений
    dp.message.middleware(LoggingMiddleware())
    dp.message.middleware(MaintenanceMiddleware())
    dp.message.middleware(DatabaseMiddleware(container))
    dp.message.outer_middleware(DependencyMiddleware(session_factory, redis))
    dp.message.middleware(ModerationMiddleware())
    dp.message.middleware(SubscriptionMiddleware())
    dp.message.middleware(ThrottlingMiddleware(throttle_manager))
    dp.message.middleware(UserActivityMiddleware(throttle_manager))
    dp.message.middleware(ChatActivityMiddleware())
    dp.message.middleware(DigestMiddleware(container))
    dp.message.middleware(CommandCleanupMiddleware())
    
    # Регистрируем middleware для callback
    dp.callback_query.middleware(LoggingMiddleware())
    dp.callback_query.middleware(MaintenanceMiddleware())
    dp.callback_query.middleware(DatabaseMiddleware(container))
    dp.callback_query.outer_middleware(DependencyMiddleware(session_factory, redis))
    
    # Регистрируем middleware для chat_member
    dp.chat_member.middleware(DatabaseMiddleware(container))
    
    # Подключаем роутеры
    main_router = setup_routers()
    dp.include_router(main_router)
    
    # Выполняем startup
    await on_startup(bot, container)
    
    # Запускаем polling
    try:
        logger.info("🔄 Starting polling...")
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            close_bot_session=True,
        )
    finally:
        await on_shutdown(bot, container)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
