"""
🚀 Точка входа SENSEI ULTIMATE 2.1.
"""

import asyncio
import logging
import os
import sys

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from src.bot.handlers.donate import DonationPaymentMiddleware
from src.bot.middlewares.comment_campaign import CommentCampaignMiddleware

from src.bot import create_bot, create_dispatcher
from src.bot.handlers import setup_routers
from src.bot.native_widgets import HedgehogWidgetMiddleware
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
from src.web.hedgehog_app import setup_hedgehog
from src.web.daily_pet_app import setup_daily_pet
from src.core.config import settings
from src.core.container import Container
from src.core.logger import setup_logging
from src.core.visuals import Visuals
from src.infra.mongo.client import MongoClient


# Настройка логирования
setup_logging()
logger = logging.getLogger(__name__)


async def setup_bot_commands(bot: Bot) -> None:
    """Установка команд бота."""
    commands = [
        BotCommand(command="donate", description="❤️ Поддержать проект"),
        BotCommand(command="paysupport", description="Поддержка по вопросам оплаты"),
        BotCommand(command="senseihelp", description="📋 Помощь"),
        BotCommand(command="senseiwidget", description="🧩 Карточки профиля и рейтинга"),
        BotCommand(command="mysensei", description="👤 Мой профиль"),
        BotCommand(command="senseitop", description="🏆 Топ игроков"),
        BotCommand(command="senseidaily", description="🎁 Ежедневный бонус"),
        BotCommand(command="senseiobmen", description="💱 Обмен валют"),
        BotCommand(command="senseiviktorina", description="🎮 Викторина"),
    ]
    await bot.set_my_commands(commands)


async def on_startup(bot: Bot, container: Container) -> None:
    """Действия при запуске."""
    logger.info(" SENSEI ULTIMATE 2.1 starting...")

    # Подключаемся к MongoDB
    await container.mongo_client.connect()
    logger.info("✅ MongoDB connected")

    await container.hedgehog_service.ensure_indexes()

    # Заполняем достижения
    count = await container.achievement_service.seed_achievements()
    if count > 0:
        logger.info(f"✅ Seeded {count} achievements")

    # Загружаем настройку визуала из MongoDB
    try:
        doc = await container.mongo_client.database.settings.find_one({"_id": "visual_style"})
        if doc and "value" in doc:
            Visuals.STYLE = doc["value"]
            logger.info(f"✅ Loaded visual style from DB: {Visuals.STYLE}")
        else:
            Visuals.STYLE = "classic"
            logger.info("✅ Visual style set to default: classic")
    except Exception as e:
        logger.warning(f"Failed to load visual style from DB, using default: {e}")
        Visuals.STYLE = "classic"

    # Загружаем кэш модерации (if needed)
    # TODO: implement muted users cache in MongoDB
    logger.info("✅ Moderation cache loaded (placeholder)")

    # Запускаем мониторинг активности чатов
    await container.chat_activity_service.start_monitoring(bot)
    logger.info("✅ Chat activity monitoring started")

    # Восстанавливаем активные игры БАНЗАЙ
    restored = await container.banzai_service.restore_workers(bot)
    if restored > 0:
        logger.info(f"✅ Restored {restored} Banzai workers")

    await container.comment_campaign_service.start(bot)

    # Устанавливаем команды
    await setup_bot_commands(bot)
    logger.info("✅ Bot commands set")

    logger.info("🚀 Bot started successfully!")


async def on_shutdown(bot: Bot, container: Container | None = None) -> None:
    """Действия при остановке."""
    logger.info(" Shutting down...")

    if container:
        campaigns = getattr(container, '_comment_campaign_service', None)
        if campaigns is not None:
            await campaigns.stop()
        # Возвращаем ставки из активных дуэлей
        try:
            await container.duel_service.shutdown()
            logger.info("✅ Active duels refunded")
        finally:
            # Close even if one settlement fails; never mask it as a success.
            await container.mongo_client.close()
            logger.info("✅ MongoDB disconnected")

    logger.info("👋 Goodbye!")


import time

async def main() -> None:
    """Главная функция."""
    # Создаём бота и диспетчер
    bot = create_bot()
    dp = create_dispatcher()

    # Создаём MongoDB клиент
    mongo_client = MongoClient()
    # Подключаемся к MongoDB
    await mongo_client.connect()
    logger.info("✅ MongoDB connected")

    # Создаём контейнер
    container = Container(
        settings=settings,
        mongo_client=mongo_client,
    )
    # Set start time for uptime calculation
    container.start_time = time.time()
    # Attach container to bot for access in handlers
    bot.container = container

    # Start web server for health checks
    app = web.Application(client_max_size=16 * 1024)
    setup_hedgehog(app, container)
    setup_daily_pet(app, container)
    app.router.add_get('/', lambda request: web.Response(text="OK"))
    app.router.add_get('/health', lambda request: web.Response(text="OK"))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.environ.get('PORT', '10000')))
    await site.start()

    dp.update.outer_middleware(CommentCampaignMiddleware(container.comment_campaign_service))

    # Future Bot API widget queries are extras until aiogram types catch up.
    dp.update.outer_middleware(HedgehogWidgetMiddleware(container))

    dp.update.outer_middleware(DonationPaymentMiddleware(container))

    # Регистрируем middleware для сообщений
    dp.message.middleware(LoggingMiddleware())
    dp.message.middleware(MaintenanceMiddleware())
    dp.message.middleware(DatabaseMiddleware(container))
    dp.message.outer_middleware(DependencyMiddleware(container))
    dp.message.middleware(ModerationMiddleware())
    dp.message.middleware(SubscriptionMiddleware())
    dp.message.middleware(ThrottlingMiddleware(container.throttle_service))  # Fixed: pass throttle service
    dp.message.middleware(UserActivityMiddleware(container))
    dp.message.middleware(ChatActivityMiddleware())
    dp.message.middleware(DigestMiddleware(container))
    dp.message.middleware(CommandCleanupMiddleware())

    # Регистрируем middleware для callback
    dp.callback_query.middleware(LoggingMiddleware())
    dp.callback_query.middleware(MaintenanceMiddleware())
    dp.callback_query.middleware(DatabaseMiddleware(container))
    dp.callback_query.outer_middleware(DependencyMiddleware(container))

    # Регистрируем middleware для chat_member
    dp.chat_member.middleware(DatabaseMiddleware(container))

    # Подключаем роутеры
    main_router = setup_routers()
    dp.include_router(main_router)

    # Выполняем startup
    await on_startup(bot, container)

    # Запускаем polling
    try:
        if settings.native_widget_transport == 'mtproto':
            from src.infra.mtproto.widgets import MtprotoWidgets
            container.native_widget_transport = await MtprotoWidgets.start(container, bot.id)
        logger.info("🔄 Starting polling...")
        await dp.start_polling(
            bot,
            allowed_updates=list(dict.fromkeys([*dp.resolve_used_update_types(), "channel_post", "message", "widget_query", "shared_widget_query"])),
            close_bot_session=True,
        )
    finally:
        try:
            if container.native_widget_transport is not None:
                await container.native_widget_transport.close()
        finally:
            try:
                await runner.cleanup()
            finally:
                await on_shutdown(bot, container)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")