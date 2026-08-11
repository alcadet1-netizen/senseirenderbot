"""
🔒 Middleware для проверки подписки на канал.
"""

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, TelegramObject
from aiogram.filters import CommandStart

from src.core.config import settings
from src.core.container import Container

class SubscriptionMiddleware(BaseMiddleware):
    """
    Middleware для проверки подписки на канал @SenseiDurova в личных сообщениях.
    """

    def __init__(self):
        self.channel_username = "@SenseiDurova"
        self.channel_url = "https://t.me/SenseiDurova"
        self.cache_ttl = 300  # 5 минут кэша

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Работаем только с сообщениями
        if not isinstance(event, Message):
            return await handler(event, data)
        
        message: Message = event
        
        # Только для личных сообщений
        if message.chat.type != "private":
            return await handler(event, data)
            
        # Пропускаем /start для регистрации и рефералов
        if message.text and message.text.startswith("/start"):
            return await handler(event, data)
            
        # Пропускаем админов
        if message.from_user.id in settings.admin_ids:
            return await handler(event, data)

        container: Container = data.get("container")
        if not container:
            return await handler(event, data)

        user_id = message.from_user.id
        cache_key = f"user:{user_id}:subscribed"
        
        # Проверяем кэш
        is_subscribed = await container.redis.get(cache_key)
        if is_subscribed:
            return await handler(event, data)

        # Проверяем подписку через API
        try:
            member = await message.bot.get_chat_member(chat_id=self.channel_username, user_id=user_id)
            if member.status in ("creator", "administrator", "member", "restricted"):
                # Если restricted, надо проверить, может ли он писать, но для канала это usually member
                # Кэшируем результат
                await container.redis.set(cache_key, "1", ex=self.cache_ttl)
                return await handler(event, data)
        except Exception:
            # Если ошибка (например, бот не админ или канал не найден), пропускаем
            # чтобы не блокировать пользователей из-за технических проблем
            return await handler(event, data)

        # Если не подписан
        await message.answer(
            "🔒 <b>Доступ ограничен!</b>\n\n"
            "Для использования бота необходимо подписаться на наш канал:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="👉 Подписаться", url=self.channel_url)],
                [InlineKeyboardButton(text="✅ Я подписался", callback_data="check_sub")]
            ]),
            parse_mode="HTML"
        )
        return None
