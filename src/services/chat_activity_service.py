"""
💤 Сервис мониторинга активности чатов.
"""

import asyncio
import logging
import time
from typing import Set, Optional
from datetime import datetime, timezone

from aiogram import Bot

from src.core.config import settings
from src.infra.mongo.client import MongoClient
from src.texts.reminders import get_inactive_reminder

logger = logging.getLogger(__name__)


class ChatActivityService:
    """Сервис для отслеживания неактивности в чатах."""

    def __init__(self, mongo_client: MongoClient):
        self.mongo_client = mongo_client
        self.db = mongo_client.database
        # Collection for storing chat last activity times
        self.chat_activities = self.db.chat_activities  # {chat_id: X, last_activity: timestamp, updated_at: timestamp}
        self._monitoring_task: asyncio.Task | None = None
        self._inactivity_threshold = 60 * 60  # 60 minutes in seconds
        self._check_interval = 60  # Check every minute

    async def update_activity(self, chat_id: int):
        """Обновляет время последней активности в чате."""
        current_time = int(time.time())
        now = datetime.now(timezone.utc)

        await self.chat_activities.update_one(
            {"chat_id": chat_id},
            {"$set": {
                "last_activity": current_time,
                "updated_at": now
            }},
            upsert=True
        )

    async def start_monitoring(self, bot: Bot):
        """Запускает фоновую задачу мониторинга."""
        if self._monitoring_task and not self._monitoring_task.done():
            return

        self._monitoring_task = asyncio.create_task(self._monitor_loop(bot))
        logger.info("💤 Chat activity monitoring started")

    async def stop_monitoring(self):
        """Останавливает мониторинг."""
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            self._monitoring_task = None
            logger.info("💤 Chat activity monitoring stopped")

    async def _monitor_loop(self, bot: Bot):
        """Цикл мониторинга."""
        while True:
            try:
                await asyncio.sleep(self._check_interval)
                await self._check_chats(bot)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Error in chat activity monitor: {e}", exc_info=True)
                await asyncio.sleep(60)  # Wait a minute before retrying on error

    async def _send_reminder(self, bot: Bot, chat_id: int) -> bool:
        """Send reminder with retry logic.

        Returns True if message was sent successfully, False otherwise.
        """
        max_retries = 3
        for attempt in range(max_retries):
            try:
                text = get_inactive_reminder()
                await bot.send_message(chat_id, text, parse_mode="HTML")
                logger.info(f"💤 Sent inactivity reminder to {chat_id} (attempt {attempt + 1})")
                return True
            except Exception as e:
                err_str = str(e).lower()
                # If it's a fatal error (bot kicked, chat not found, forbidden), don't retry
                if "kicked" in err_str or "chat not found" in err_str or "forbidden" in err_str:
                    logger.warning(f"❌ Bot kicked/blocked in {chat_id}. Removing from monitoring.")
                    await self.chat_activities.delete_one({"chat_id": chat_id})
                    return False

                # For other errors, retry if we have attempts left
                if attempt < max_retries - 1:  # Not the last attempt
                    logger.warning(f"⚠️ Attempt {attempt + 1} failed for chat {chat_id}: {e}. Retrying...")
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff: 1s, 2s, 4s
                else:
                    logger.error(f"❌ Failed to send reminder to {chat_id} after {max_retries} attempts: {e}")

        return False

    async def _check_chats(self, bot: Bot):
        """Проверяет чаты на неактивность."""
        current_time = int(time.time())
        threshold_time = current_time - self._inactivity_threshold

        # Find chats that have been inactive for too long
        inactive_chats_cursor = self.chat_activities.find({
            "last_activity": {"$lt": threshold_time}
        })
        inactive_chats = await inactive_chats_cursor.to_list(length=None)

        for chat_doc in inactive_chats:
            chat_id = chat_doc["chat_id"]
            try:
                # Check chat type to avoid spamming private chats
                chat = await bot.get_chat(chat_id)
                if chat.type not in ("group", "supergroup"):
                    # Remove from monitoring if it's not a group/supergroup
                    await self.chat_activities.delete_one({"chat_id": chat_id})
                    logger.info(f"🗑️ Removed private/channel {chat_id} from active chats monitoring")
                    continue

                # Send reminder with retry logic
                success = await self._send_reminder(bot, chat_id)
                if success:
                    # Update activity time to prevent spamming
                    # We consider sending the bot's reminder as "activity" so the next reminder comes in another hour
                    await self.update_activity(chat_id)

            except Exception as e:
                err_str = str(e).lower()
                if "kicked" in err_str or "chat not found" in err_str or "forbidden" in err_str:
                    logger.warning(f"❌ Bot kicked/blocked in {chat_id}. Removing from monitoring.")
                    await self.chat_activities.delete_one({"chat_id": chat_id})
                    continue

                logger.error(f"❌ Error checking chat {chat_id}: {e}")

    # Additional utility methods for compatibility
    async def get_chat_activity(self, chat_id: int) -> Optional[dict]:
        """Get activity record for a specific chat."""
        return await self.chat_activities.find_one({"chat_id": chat_id})

    async def get_active_chats_count(self) -> int:
        """Get count of chats being monitored (those with activity records)."""
        return await self.chat_activities.count_documents({})

    async def get_all_chat_ids(self) -> set[int]:
        """Get all chat IDs being monitored."""
        cursor = self.chat_activities.find({}, {"chat_id": 1, "_id": 0})
        docs = await cursor.to_list(length=None)
        return {doc["chat_id"] for doc in docs}

    async def remove_chat(self, chat_id: int) -> None:
        """Remove a chat from monitoring."""
        await self.chat_activities.delete_one({"chat_id": chat_id})