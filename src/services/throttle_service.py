"""
   Сервис троттлинга.
"""

from src.infra.mongo.client import MongoClient
import time
from pymongo.errors import DuplicateKeyError


class ThrottleService:
    """Сервис для ограничения частоты операций с использованием MongoDB."""

    def __init__(self, mongo_client: MongoClient):
        self.mongo_client = mongo_client
        self.db = mongo_client.database
        self.collection = self.db.throttle
        # Ensure indexes
        # Unique index on _id to prevent duplicate inserts within the same window
        # Note: _id is already unique, so we just ensure the index exists.
        self.collection.create_index([("_id", 1)])
        # TTL index on expiry to automatically remove old records
        self.collection.create_index([("expiry", 1)], expireAfterSeconds=0)

    async def throttle(self, key: str, limit_seconds: int, scope: str = "default") -> bool:
        """
        Проверяет, позволяет ли лимит выполнить операцию.
        Возвращает True если операция разрешена (не троттлится), False если троттлится.

        Использует фиксированное окно: пытается вставить документ с ключом {scope}:{key}
        и сроком жизни limit_seconds. Если вставка успешна — разрешено, если ошибка дублирования ключа — троттлится.
        """
        doc_id = f"{scope}:{key}"
        expiry = int(time.time()) + limit_seconds
        doc = {"_id": doc_id, "expiry": expiry}
        try:
            await self.collection.insert_one(doc)
            return True  # Вставка успешна -> не троттлится
        except DuplicateKeyError:
            return False  # Дублирование ключа -> троттлится
        except Exception as e:
            # В случае любой другой ошибки (например, проблемы с соединением) логируем и разрешаем операцию
            # чтобы не блокировать пользователя из-за технических проблем
            logger.error(f"Error in throttle service for key {doc_id}: {e}")
            return True