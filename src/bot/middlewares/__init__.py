"""Middlewares package."""

from src.bot.middlewares.database import DatabaseMiddleware
from src.bot.middlewares.db import DependencyMiddleware
from src.bot.middlewares.throttling import ThrottlingMiddleware
from src.bot.middlewares.logging import LoggingMiddleware
from src.bot.middlewares.maintenance import MaintenanceMiddleware
from src.bot.middlewares.user_activity import UserActivityMiddleware
from src.bot.middlewares.moderation import ModerationMiddleware
from src.bot.middlewares.chat_activity import ChatActivityMiddleware
from src.bot.middlewares.subscription import SubscriptionMiddleware

__all__ = [
    "DatabaseMiddleware",
    "DependencyMiddleware",
    "ThrottlingMiddleware",
    "LoggingMiddleware",
    "MaintenanceMiddleware",
    "UserActivityMiddleware",
    "ModerationMiddleware",
    "ChatActivityMiddleware",
    "SubscriptionMiddleware",
]
