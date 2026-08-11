"""
🥋 Middleware сенсея. Не пускает учеников, пока мастер работает.
"""

import logging
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
        user_id = self._get_user_id(event)
        
        if user_id is None:
            return await handler(event, data)
        
        # 👑 Сенсей (админ) проходит всегда
        if user_id in settings.admin_ids:
            return await handler(event, data)
        
        # 🚫 Ученики ждут
        if MaintenanceService.is_enabled():
            await self._send_sensei_wisdom(event)
            return None
        
        return await handler(event, data)
    
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
