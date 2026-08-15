"""
        .
"""

from typing import List, Optional, Dict, Any

from src.domain.repositories.base import BaseRepository


class TransactionRepository(BaseRepository):
    """Репозиторий для работы с транзакциями."""

    def __init__(self, collection):
        super().__init__(collection)

    async def get_by_id(self, transaction_id: int) -> Optional[Dict[Any, Any]]:
        """Получить транзакцию по ID."""
        return await self.collection.find_one({"id": transaction_id})

    async def get_all(self, limit: int = 100, offset: int = 0) -> List[Dict[Any, Any]]:
        """Получить все транзакции."""
        cursor = self.collection.find().skip(offset).limit(limit)
        return await cursor.to_list(length=limit)

    async def add(self, transaction: Dict[Any, Any]) -> str:
        """Добавить транзакцию."""
        # Ensure we have a timestamp
        if "created_at" not in transaction:
            from datetime import datetime, timezone
            transaction["created_at"] = datetime.now(timezone.utc)

        result = await self.collection.insert_one(transaction)
        return str(result.inserted_id)

    async def update(self, transaction: Dict[Any, Any]) -> bool:
        """Обновить транзакцию."""
        if "_id" not in transaction and "id" not in transaction:
            raise ValueError("Transaction must have _id or id field for update")

        # Use id field if _id not present
        transaction_id = transaction.get("_id") or transaction.get("id")
        if transaction_id is None:
            raise ValueError("Transaction must have _id or id field for update")

        # Remove id fields from update data
        update_data = {k: v for k, v in transaction.items() if k not in ["_id", "id"]}

        result = await self.collection.update_one(
            {"id": transaction_id},
            {"$set": update_data}
        )
        return result.modified_count > 0

    async def delete(self, transaction_id: int) -> bool:
        """Удалить транзакцию."""
        result = await self.collection.delete_one({"id": transaction_id})
        return result.deleted_count > 0

    async def create(
        self,
        user_id: int,
        tx_type: str,
        xp_change: int = 0,
        coins_change: float = 0.0,
        description: Optional[str] = None
    ) -> str:
        """Создать транзакцию."""
        from datetime import datetime, timezone
        transaction = {
            "user_id": user_id,
            "tx_type": tx_type,
            "xp_change": xp_change,
            "coins_change": coins_change,
            "description": description,
            "created_at": datetime.now(timezone.utc)
        }
        return await self.add(transaction)

    async def get_user_transactions(
        self,
        user_id: int,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[Any, Any]]:
        """Получить транзакции пользователя."""
        cursor = self.collection.find(
            {"user_id": user_id}
        ).sort("created_at", -1).limit(limit).skip(offset)
        return await cursor.to_list(length=limit)

    async def get_by_type(self, tx_type: str, limit: int = 50) -> List[Dict[Any, Any]]:
        """Получить транзакции по типу."""
        cursor = self.collection.find(
            {"tx_type": tx_type}
        ).sort("created_at", -1).limit(limit)
        return await cursor.to_list(length=limit)

    async def get_total_coins_distributed(self) -> float:
        """Получить общее количество распределённых монет."""
        pipeline = [
            {"$match": {"coins_change": {"$gt": 0}}},
            {"$group": {"_id": None, "total": {"$sum": "$coins_change"}}}
        ]
        cursor = self.collection.aggregate(pipeline)
        result = await cursor.to_list(length=1)
        return result[0]["total"] if result else 0.0

    async def get_total_coins_in_circulation(self) -> float:
        """Получить общее количество монет в обороте."""
        # This should come from the user service, but we'll implement a basic version
        # that sums all user coins from the users collection
        # For now, we'll return 0 as this should be called from user service
        return 0.0

    async def get_stats_by_type(self) -> Dict[str, Any]:
        """Статистика по типам транзакций."""
        pipeline = [
            {"$group": {
                "_id": "$tx_type",
                "count": {"$sum": 1},
                "total_coins": {"$sum": "$coins_change"}
            }},
            {"$sort": {"count": -1}}
        ]
        cursor = self.collection.aggregate(pipeline)
        results = await cursor.to_list(length=None)
        return {
            item["_id"]: {"count": item["count"], "total_coins": item["total_coins"]}
            for item in results
        }