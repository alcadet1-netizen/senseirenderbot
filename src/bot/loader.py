"""
🤖 Загрузчик бота.
"""

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.telegram import TelegramAPIServer
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

    if settings.telegram_widget_beta:
        # Explicit only: production tokens/chats must not be silently moved.
        session.api = TelegramAPIServer(
            base="https://api.telegram.org/beta/bot{token}/test/{method}",
            file="https://api.telegram.org/beta/file/bot{token}/test/{path}",
        )

    return AntiSpamBot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML, protect_content=False),
        session=session
    )


def create_dispatcher() -> Dispatcher:
    """Создание диспетчера."""
    return Dispatcher()
