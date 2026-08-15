"""
 Сервис управления капчей.
"""

import time
from typing import Optional
from src.infra.mongo.client import MongoClient


class CaptchaService:
    """Сервис для хранения состояния капчи с использованием MongoDB."""

    def __init__(self, mongo_client: MongoClient):
        self.mongo_client = mongo_client
        self.db = mongo_client.database
        # Collections
        self.locks = self.db.captcha_locks
        self.solved = self.db.captcha_solved
        # Ensure TTL indexes (run once)
        # Note: In production, you might want to run this during migrations.
        # For simplicity, we create indexes if they don't exist.
        # We'll use create_index with expireAfterSeconds.
        # We do it in __init__ but it's safe to call multiple times.
        try:
            # Locks TTL index: expire after expiry date
            self.locks.create_index("expiry", expireAfterSeconds=0)
        except Exception:
            pass
        try:
            # Solved TTL index
            self.solved.create_index("expiry", expireAfterSeconds=0)
        except Exception:
            pass

    async def set_lock(self, chat_id: int, user_id: int, ex: int) -> bool:
        """
        Установить блокировку для предотвращения двойного запуска капчи.
        Возвращает True если блокировка установлена (ключ не существовал), False иначе.
        """
        expiry = int(time.time()) + ex
        doc = {"chat_id": chat_id, "user_id": user_id, "expiry": expiry}
        try:
            await self.locks.insert_one(doc)
            return True
        except Exception as e:
            # Duplicate key error (unique index on chat_id, user_id)
            if "E11000" in str(e):
                return False
            # Re-raise other errors
            raise

    async def get_solved(self, user_id: int) -> bool:
        """
        Проверить, решена ли капча для пользователя récemment.
        """
        now = int(time.time())
        doc = await self.solved.find_one({"user_id": user_id, "expiry": {"$gt": now}})
        return doc is not None

    async def set_solved(self, user_id: int, ex: int) -> None:
        """
        Отметить капчу как решённую для пользователя с истечением срока ex секунд.
        """
        expiry = int(time.time()) + ex
        await self.solved.update_one(
            {"user_id": user_id},
            {"$set": {"expiry": expiry}},
            upsert=True
        )