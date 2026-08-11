"""
🤖 Загрузчик бота.
"""

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode

from src.core.config import settings
from src.bot.custom_bot import AntiSpamBot


def create_bot() -> Bot:
    """Создание экземпляра бота."""
    if settings.proxy_url:
        session = AiohttpSession(proxy=settings.proxy_url)
    else:
        session = AiohttpSession()

    return AntiSpamBot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        session=session
    )


def create_dispatcher() -> Dispatcher:
    """Создание диспетчера."""
    return Dispatcher()
