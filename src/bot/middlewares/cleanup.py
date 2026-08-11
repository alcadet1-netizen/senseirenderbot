from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message

class CommandCleanupMiddleware(BaseMiddleware):
    """Middleware для удаления сообщений с командами."""

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        # Выполняем хендлер
        result = await handler(event, data)
        
        # Если это сообщение и оно начинается с /, пытаемся удалить
        if isinstance(event, Message) and event.text and event.text.startswith('/'):
            try:
                await event.delete()
            except Exception:
                pass
                
        return result
