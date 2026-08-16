"""
🥋 Middleware сенсея. Не пускает учеников, пока мастер работает.
"""

import logging
import time
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject

from src.core.config import settings
from src.services.maintenance_service import MaintenanceService

logger = logging.getLogger(__name__)


class MaintenanceMiddleware(BaseMiddleware):
    """🥋 Охранник додзё."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        start = time.perf_counter()
        user_id = self._get_user_id(event)
        logger.info(f"[MAINTENANCE] Start processing event {type(event).__name__} user_id={user_id}")

        if user_id is None:
            logger.info("[MAINTENANCE] No user_id, passing to handler")
            result = await handler(event, data)
            logger.info(f"[MAINTENANCE] Handler took {(time.perf_counter() - start)*1000:.2f} ms")
            return result

        # 👑 Сенсей (админ) проходит всегда
        if user_id in settings.admin_ids:
            logger.info(f"[MAINTENANCE] User {user_id} is admin, passing to handler")
            result = await handler(event, data)
            logger.info(f"[MAINTENANCE] Handler took {(time.perf_counter() - start)*1000:.2f} ms")
            return result

        # 🚫 Ученики ждут
        if MaintenanceService.is_enabled():
            logger.info(f"[MAINTENANCE] Maintenance enabled, sending wisdom to user {user_id}")
            await self._send_sensei_wisdom(event)
            logger.info(f"[MAINTENANCE] Finished maintenance block")
            return None

        logger.info(f"[MAINTENANCE] Maintenance disabled, passing to handler for user {user_id}")
        result = await handler(event, data)
        logger.info(f"[MAINTENANCE] Handler took {(time.perf_counter() - start)*1000:.2f} ms")
        return result

    def _get_user_id(self, event: TelegramObject) -> int | None:
        if isinstance(event, Message):
            return event.from_user.id if event.from_user else None
        elif isinstance(event, CallbackQuery):
            return event.from_user.id if event.from_user else None
        return None

    async def _send_sensei_wisdom(self, event: TelegramObject) -> None:
        """Отправить мудрость сенсея."""
        state = MaintenanceService.get_state()
        phrase = MaintenanceService.get_random_phrase()
        suffering = MaintenanceService.get_suffering_time()

        # Формируем послание
        text = f"{phrase}\n\n"

        if state.reason:
            text += f"📋 <i>{state.reason}</i>\n\n"

        if suffering:
            text += f"{suffering}\n"

        if state.estimated_end:
            remaining = (state.estimated_end - datetime.now()).total_seconds()
            if remaining > 0:
                mins = int(remaining // 60)
                text += f"🔮 Пророчество: ~{mins} мин. осталось терпеть\n"

        text += "\n<b>🙏 Жди. Верь. Страдай.</b>"

        if isinstance(event, Message):
            # Случайные стикеры мудрости
            await event.answer(text, parse_mode="HTML")

        elif isinstance(event, CallbackQuery):
            await event.answer(
                "🥋 Сенсей работает! Кнопки временно бесполезны.",
                show_alert=True
            )
