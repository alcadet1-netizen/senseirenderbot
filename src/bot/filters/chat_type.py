"""
💬 Фильтры типов чатов.
"""

from aiogram.filters import BaseFilter
from aiogram.types import Message


class GroupChatFilter(BaseFilter):
    """Фильтр для групповых чатов."""

    async def __call__(self, message: Message) -> bool:
        return message.chat.type in ("group", "supergroup")


class PrivateChatFilter(BaseFilter):
    """Фильтр для личных сообщений."""

    async def __call__(self, message: Message) -> bool:
        return message.chat.type == "private"