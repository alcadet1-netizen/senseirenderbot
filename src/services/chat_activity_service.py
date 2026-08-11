"""
💤 Сервис мониторинга активности чатов.
"""

import asyncio
import logging
import time
from typing import Set

from aiogram import Bot
from redis.asyncio import Redis

from src.texts.reminders import get_inactive_reminder

logger = logging.getLogger(__name__)

# Ключ для хранения времени последней активности: chat:{chat_id}:last_activity
# Ключ для хранения множества активных чатов: active_chats

class ChatActivityService:
    """Сервис для отслеживания неактивности в чатах."""

    def __init__(self, redis: Redis):
        self.redis = redis
        self._monitoring_task: asyncio.Task | None = None
        self._active_chats_key = "active_chats"
        self._activity_key_prefix = "chat:{}:last_activity"
        self._inactivity_threshold = 60 * 60  # 60 минут в секундах
        self._check_interval = 60  # Проверка каждую минуту

    async def update_activity(self, chat_id: int):
        """Обновляет время последней активности в чате."""
        current_time = int(time.time())
        # Используем pipeline для атомарности и производительности
        async with self.redis.pipeline(transaction=True) as pipe:
            # Обновляем timestamp
            pipe.set(self._activity_key_prefix.format(chat_id), current_time)
            # Добавляем чат в список активных, если его там нет
            pipe.sadd(self._active_chats_key, chat_id)
            await pipe.execute()

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
                await asyncio.sleep(60)  # Ждем минуту перед повторной попыткой при ошибке

    async def _check_chats(self, bot: Bot):
        """Проверяет чаты на неактивность."""
        current_time = int(time.time())
        
        # Получаем список всех отслеживаемых чатов
        # SMEMBERS может быть дорогим, если чатов миллионы, но для бота это ок.
        # Если чатов будет очень много, лучше использовать SSCAN
        chat_ids = await self.redis.smembers(self._active_chats_key)
        
        if not chat_ids:
            return

        for chat_id_bytes in chat_ids:
            try:
                chat_id = int(chat_id_bytes)
                last_activity = await self.redis.get(self._activity_key_prefix.format(chat_id))
                
                if not last_activity:
                    continue
                
                last_activity = int(last_activity)
                
                if current_time - last_activity >= self._inactivity_threshold:
                    # Прошло больше 60 минут
                    await self._send_reminder(bot, chat_id)
                    
                    # Обновляем время активности, чтобы не спамить
                    # Мы считаем отправку напоминания "активностью" бота, 
                    # чтобы следующее напоминание пришло еще через час
                    await self.update_activity(chat_id)
                    
            except Exception as e:
                logger.error(f"❌ Error checking chat {chat_id_bytes}: {e}")

    async def _send_reminder(self, bot: Bot, chat_id: int):
        """Отправляет напоминание в чат."""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Проверяем тип чата, чтобы не спамить в личку
                chat = await bot.get_chat(chat_id)
                if chat.type not in ("group", "supergroup"):
                    await self.redis.srem(self._active_chats_key, chat_id)
                    logger.info(f"🗑️ Removed private/channel {chat_id} from active chats monitoring")
                    return

                text = get_inactive_reminder()
                await bot.send_message(chat_id, text, parse_mode="HTML")
                logger.info(f"💤 Sent inactivity reminder to {chat_id}")
                return
            except Exception as e:
                err_str = str(e).lower()
                if "kicked" in err_str or "chat not found" in err_str or "forbidden" in err_str:
                    logger.warning(f"❌ Bot kicked/blocked in {chat_id}. Removing from monitoring.")
                    await self.redis.srem(self._active_chats_key, chat_id)
                    return

                if attempt < max_retries - 1:
                    logger.warning(f"⚠️ Failed to send reminder to {chat_id} (attempt {attempt+1}/{max_retries}): {e}. Retrying...")
                    await asyncio.sleep(2)
                    continue
                
                logger.error(f"❌ Failed to send reminder to {chat_id}: {e}")
