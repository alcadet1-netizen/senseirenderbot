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
        # Copying is allowed for every outgoing Bot API method that supports it,
        # including callers explicitly passing True or overriding bot defaults.
        # Copy instead of mutating a potentially reused request object.
        if 'protect_content' in type(method).model_fields:
            method = method.model_copy(update={'protect_content': False})
        # Выполняем метод
        if timeout is not None:
            kwargs["request_timeout"] = timeout
            
        result = await super().__call__(method, **kwargs)
        
        # Логика удаления отключена
        return result
