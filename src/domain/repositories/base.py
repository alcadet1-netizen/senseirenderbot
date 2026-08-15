"""
 Базовый репозиторий.
"""

from abc import ABC
from typing import Generic, List, Optional, TypeVar, Type

from motor.motor_asyncio import AsyncIOMotorCollection

T = TypeVar("T")
ID = TypeVar("ID")


class BaseRepository(ABC, Generic[T, ID]):
    """Базовый репозиторий с реализацией CRUD для MongoDB."""

    def __init__(self, collection: AsyncIOMotorCollection):
        self.collection = collection

    async def get_by_id(self, id: ID) -> Optional[dict]:
        """Получить сущность по ID."""
        # Предполагаем, что у документа есть поле _id
        result = await self.collection.find_one({"_id": id})
        return result

    async def get_all(self, limit: int = 100, offset: int = 0) -> List[dict]:
        """Получить все сущности."""
        cursor = self.collection.find().skip(offset).limit(limit)
        return await cursor.to_list(length=limit)

    async def add(self, entity: dict) -> str:
        """Добавить сущность."""
        result = await self.collection.insert_one(entity)
        return str(result.inserted_id)

    async def update(self, entity: dict) -> bool:
        """Обновить сущность."""
        # Предполагаем, что у entity есть поле _id
        if "_id" not in entity:
            raise ValueError("Entity must have _id field for update")

        entity_id = entity.pop("_id")
        result = await self.collection.update_one(
            {"_id": entity_id},
            {"$set": entity}
        )
        # Put the _id back for consistency
        entity["_id"] = entity_id
        return result.modified_count > 0

    async def delete(self, id: ID) -> bool:
        """Удалить сущность."""
        result = await self.collection.delete_one({"_id": id})
        return result.deleted_count > 0