from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject


class DependencyMiddleware(BaseMiddleware):
    def __init__(self, session_factory, redis):
        self.session_factory = session_factory
        self.redis = redis

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        data["session_factory"] = self.session_factory
        data["redis"] = self.redis
        return await handler(event, data)
