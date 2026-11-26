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
        # Defense in depth for restored workers, scheduled jobs and admin flows.
        # Read-only Telegram lookups (including task subscription checks) are
        # deliberately unrestricted. Private IDs remain usable for payments.
        target = getattr(method, 'chat_id', None)
        game_chat = getattr(self, 'game_chat_id', None)
        api_method = getattr(method, '__api_method__', '')
        if game_chat is not None and target is not None and not api_method.startswith('get'):
            allowed = (type(target) is int and (target > 0 or target == game_chat))
            allowed = allowed or (isinstance(target, str) and target.lower() == '@airchatton')
            if not allowed:
                raise ValueError('Telegram action blocked outside @airchatton')
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
