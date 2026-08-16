"""
🛡️ Фильтр администраторов.
"""

import logging
import os
from aiogram.filters import BaseFilter
from aiogram.types import Message

from src.core.config import settings

logger = logging.getLogger(__name__)


class AdminFilter(BaseFilter):
    """Фильтр для проверки прав администратора."""

    async def __call__(self, message: Message) -> bool:
        if not message.from_user:
            logger.info("[ADMINFILTER] No from_user")
            return False
        user_id = message.from_user.id
        admin_ids_str = settings.admin_ids_str
        admin_ids = settings.admin_ids
        raw_env = os.getenv("ADMIN_IDS")
        logger.info(f"[ADMINFILTER] Checking user {user_id} against admin_ids_str '{admin_ids_str}' parsed as {admin_ids}, raw env ADMIN_IDS='{raw_env}'")
        result = user_id in admin_ids
        logger.info(f"[ADMINFILTER] Result for user {user_id}: {result}")
        return result