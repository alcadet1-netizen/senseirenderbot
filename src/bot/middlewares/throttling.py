"""
⏱️ Middleware для throttling.
"""

import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message

from src.core.constants import THROTTLE_RATE_LIMIT
from src.services.throttle_service import ThrottleService

logger = logging.getLogger(__name__)


class ThrottlingMiddleware(BaseMiddleware):
    """Middleware для ограничения частоты команд."""

    def __init__(self, throttle_service: ThrottleService):
        self.throttle = throttle_service

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        if not isinstance(event, Message):
            return await handler(event, data)

        if not event.from_user:
            return await handler(event, data)

        user_id = event.from_user.id

        # Проверяем, является ли сообщение командой
        is_command = event.text and event.text.startswith("/")

        # Применяем строгий троттлинг только к командам
        if is_command:
            # Основная проверка на частоту команд
            can_proceed = await self.throttle.throttle(
                key=str(user_id),
                limit_seconds=THROTTLE_RATE_LIMIT,
                scope="commands"
            )

            if not can_proceed:
                # Log throttling event
                logger.info(f"🚫 [THROTTLE] User {user_id} blocked by rate limit (command)")

                # Если заблокирован, проверяем, нужно ли отправить предупреждение
                # Предупреждаем не чаще чем раз в 3 секунды
                should_warn = await self.throttle.throttle(
                    key=str(user_id),
                    limit_seconds=3,
                    scope="throttle_warning"
                )

                if should_warn:
                    try:
                        await event.answer("⏳ <b>Слишком быстро!</b>\nПодождите немного.", parse_mode="HTML")
                        logger.info(f"📤 [THROTTLE] Warning sent to user {user_id}")
                    except Exception as warn_err:
                        logger.error(f"⚠️ [THROTTLE] Failed to send warning: {warn_err}")
                else:
                    logger.info(f"🔇 [THROTTLE] Warning skipped for user {user_id} (cooldown)")

                logger.info(f"🔄 [THROTTLE] Proceeding to command handler for user {user_id}")

        return await handler(event, data)