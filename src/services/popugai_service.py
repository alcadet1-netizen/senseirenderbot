"""
🦜 Сервис для режима 'Попугай' (автоответы стикерами/гифками).
"""

from src.infra.mongo.client import MongoClient
import random
from typing import Optional, Tuple


class PopugaiService:
    """Сервис для хранения настроек попугая и медиа с использованием MongoDB."""

    def __init__(self, mongo_client: MongoClient):
        self.mongo_client = mongo_client
        self.db = mongo_client.database
        # Collections
        self.chances = self.db.popugai_chances
        self.media = self.db.popugai_media
        # Ensure indexes
        self._ensure_indexes()

    def _ensure_indexes(self):
        """Ensure necessary indexes exist."""
        # Index on chat_id for chances collection
        self.chances.create_index("chat_id", unique=True)
        # Compound index for media collection: chat_id + media_type for efficient queries
        self.media.create_index([("chat_id", 1), ("media_type", 1)])
        # Index on file_id for potential deduplication (optional)
        self.media.create_index("file_id")

    async def get_reply_chance(self, chat_id: int) -> float:
        """Получить шанс ответа для чата (0.0 - 1.0)."""
        doc = await self.chances.find_one({"chat_id": chat_id})
        if doc:
            return doc.get("chance", 0.0)
        return 0.0

    async def set_reply_chance(self, chat_id: int, chance: float) -> None:
        """Установить шанс ответа для чата (0.0 - 1.0)."""
        # Clamp chance between 0.0 and 1.0
        chance = max(0.0, min(1.0, chance))

        if chance <= 0:
            # Remove the document if chance is 0 or negative
            await self.chances.delete_one({"chat_id": chat_id})
        else:
            # Upsert the document
            await self.chances.update_one(
                {"chat_id": chat_id},
                {"$set": {"chance": chance}},
                upsert=True
            )

    async def add_media(self, chat_id: int, media_type: str, file_id: str) -> None:
        """Сохранить медиа (sticker/gif) для чата."""
        if media_type not in ("sticker", "gif"):
            return

        # Check if this exact file_id already exists for this chat and media_type to avoid duplicates
        existing = await self.media.find_one({
            "chat_id": chat_id,
            "media_type": media_type,
            "file_id": file_id
        })

        if not existing:
            await self.media.insert_one({
                "chat_id": chat_id,
                "media_type": media_type,
                "file_id": file_id
            })

    async def get_random_media(self, chat_id: int) -> Optional[Tuple[str, str]]:
        """
        Получить случайное медиа для ответа.
        Возвращает (media_type, file_id) или None.
        """
        # Get all media for this chat
        cursor = self.media.find({"chat_id": chat_id})
        media_list = await cursor.to_list(length=None)  # Get all media

        if not media_list:
            return None

        # Choose a random media item
        media_item = random.choice(media_list)
        return (media_item["media_type"], media_item["file_id"])