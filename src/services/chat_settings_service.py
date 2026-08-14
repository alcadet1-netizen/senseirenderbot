"""
������������������������������������������������������������������������������������������������������ Сервис настроек чата.
"""

from src.infra.mongo.client import MongoClient


class ChatSettingsService:
    """Сервис для хранения настроек чатов с использованием MongoDB."""

    def __init__(self, mongo_client: MongoClient):
        self.mongo_client = mongo_client
        self.db = mongo_client.database
        self.collection = self.db.chat_settings
        # Ensure indexes
        # Compound index on chat_id and key for uniqueness and fast lookups
        self.collection.create_index([("chat_id", 1), ("key", 1)], unique=True)

    async def set_setting(self, chat_id: int, key: str, value: str) -> None:
        """
        Установить настройку для чата.
        """
        await self.collection.update_one(
            {"chat_id": chat_id, "key": key},
            {"$set": {"value": value}, "$currentDate": {"updated_at": True}},
            upsert=True
        )

    async def get_setting(self, chat_id: int, key: str) -> str | None:
        """
        Получить настройку для чата.
        Возвращает значение как строку или None, если настройка не найдена.
        """
        doc = await self.collection.find_one({"chat_id": chat_id, "key": key})
        if doc:
            return doc.get("value")
        return None

    async def delete_setting(self, chat_id: int, key: str) -> None:
        """
        Удалить настройку для чата.
        """
        await self.collection.delete_one({"chat_id": chat_id, "key": key})