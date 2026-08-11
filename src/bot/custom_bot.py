from typing import Any, Optional

from aiogram import Bot
from aiogram.methods import TelegramMethod


class AntiSpamBot(Bot):
    """
    Бот.
    Ранее имел функцию автоматического удаления, теперь отключена по требованию:
    все сообщения должны оставаться в чате.
    """

    async def __call__(
        self, method: TelegramMethod[Any], timeout: Optional[int] = None, **kwargs: Any
    ) -> Any:
        # Выполняем метод
        if timeout is not None:
            kwargs["request_timeout"] = timeout
            
        result = await super().__call__(method, **kwargs)
        
        # Логика удаления отключена
        return result
