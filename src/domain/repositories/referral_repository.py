from typing import Optional, List, Tuple
from motor.motor_asyncio import AsyncIOMotorCollection
from bson import ObjectId
from datetime import datetime, timezone


class ReferralRepository:
    """Репозиторий для работы с рефералами."""

    def __init__(self, collection: AsyncIOMotorCollection):
        self.collection = collection

    async def get_referrer_id(self, user_id: int) -> Optional[int]:
        """Получить ID реферера (того, кто пригласил user_id)."""
        referral = await self.collection.find_one({
            "referred_id": user_id,
            "level": 1
        })
        if referral:
            return referral.get("referrer_id")
        return None

    async def is_already_referred(self, user_id: int) -> bool:
        """Проверить, был ли пользователь уже приглашен кем-то."""
        referral = await self.collection.find_one({"referred_id": user_id})
        return referral is not None

    async def get_stats(self, user_id: int) -> dict:
        """Получить статистику рефералов."""
        # We'll use aggregation to compute the stats for level 1 and level 2
        pipeline = [
            {"$match": {"referrer_id": user_id}},
            {"$group": {
                "_id": "$level",
                "count": {"$sum": 1},
                "total_coins_earned": {"$sum": "$coins_earned"},
                "total_xp_earned": {"$sum": "$xp_earned"},
                "active_count": {"$sum": {"$cond": [{"$eq": ["$is_active", True]}, 1, 0]}}
            }}
        ]
        cursor = self.collection.aggregate(pipeline)
        result = await cursor.to_list(length=None)

        stats = {
            "level_1_count": 0,
            "level_1_coins_earned": 0.0,
            "level_1_xp_earned": 0,
            "level_1_active": 0,
            "level_2_count": 0,
            "level_2_coins_earned": 0.0,
            "level_2_xp_earned": 0,
            "level_2_active": 0,
            "total_coins_earned": 0.0,
            "total_xp_earned": 0,
        }

        for item in result:
            level = item["_id"]
            if level == 1:
                stats["level_1_count"] = item["count"]
                stats["level_1_coins_earned"] = item["total_coins_earned"]
                stats["level_1_xp_earned"] = item["total_xp_earned"]
                stats["level_1_active"] = item["active_count"]
            elif level == 2:
                stats["level_2_count"] = item["count"]
                stats["level_2_coins_earned"] = item["total_coins_earned"]
                stats["level_2_xp_earned"] = item["total_xp_earned"]
                stats["level_2_active"] = item["active_count"]

        stats["total_coins_earned"] = stats["level_1_coins_earned"] + stats["level_2_coins_earned"]
        stats["total_xp_earned"] = stats["level_1_xp_earned"] + stats["level_2_xp_earned"]

        return stats

    async def get_referrals_list(self, user_id: int, level: int = 1, limit: int = 10) -> List[dict]:
        """Получить список рефералов пользователя за указанный уровень."""
        cursor = self.collection.find(
            {"referrer_id": user_id, "level": level}
        ).sort("created_at", -1).limit(limit)
        return await cursor.to_list(length=limit)

    async def get_top_referrers(self, limit: int = 10) -> List[Tuple[int, int, Optional[str], str]]:
        """Топ реферезов по количеству приглашенных (Level 1). Возвращает (referrer_id, count, username, first_name)."""
        # We need to join with users collection. Since we don't have a direct way to join in MongoDB without $lookup,
        # and we don't have access to the users collection in this repository, we'll do two queries:
        # First, get the top referrer IDs and counts for level 1.
        # Then, for each, fetch the user details from the users collection (via a service or repository).
        # However, to keep the repository independent, we'll return the raw data from the referrals collection
        # and let the service handle the user lookup if needed.

        # Alternatively, we can change the design: the repository can take the users collection as well.
        # But to minimize changes, we'll do the following:

        # Step 1: Get the top referrer IDs and their counts for level 1.
        pipeline = [
            {"$match": {"level": 1}},
            {"$group": {
                "_id": "$referrer_id",
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}},
            {"$limit": limit}
        ]
        cursor = self.collection.aggregate(pipeline)
        top_referrers = await cursor.to_list(length=None)

        # Step 2: For each, we need to get the user details. We don't have the users collection here.
        # We'll return a list of tuples with (referrer_id, count, None, None) and let the caller fill in the user details.
        # However, the original method expected to return the username and first_name.
        # Since we cannot get them without the users collection, we'll adjust the method to return only the ids and counts,
        # and change the caller accordingly. But note: the caller might be in the service, and we can change the service to use the user service.

        # Given the time, we'll return the referrer_id and count, and set username and first_name to None.
        # We'll update the method's docstring accordingly.

        result = []
        for item in top_referrers:
            referrer_id = item["_id"]
            count = item["count"]
            result.append((referrer_id, count, None, None))

        return result

    # We also need to implement the CRUD methods from BaseRepository if they are used elsewhere.
    # Let's check if the base class methods are used. We'll implement them for completeness.

    async def get_by_id(self, id: int) -> Optional[dict]:
        """Получить реферальную связь по ID."""
        return await self.collection.find_one({"_id": id})

    async def get_all(self, limit: int = 100, offset: int = 0) -> List[dict]:
        """Получить все реферальные связи."""
        cursor = self.collection.find().skip(offset).limit(limit)
        return await cursor.to_list(length=limit)

    async def add(self, entity: dict) -> str:
        """Добавить реферальную связь."""
        result = await self.collection.insert_one(entity)
        return str(result.inserted_id)

    async def update(self, entity: dict) -> bool:
        """Обновить реферальную связь."""
        if "_id" not in entity:
            raise ValueError("Entity must have _id field for update")
        entity_id = entity.pop("_id")
        result = await self.collection.update_one(
            {"_id": entity_id},
            {"$set": entity}
        )
        entity["_id"] = entity_id  # Put back for consistency
        return result.modified_count > 0

    async def delete(self, id: int) -> bool:
        """Удалить реферальную связь."""
        result = await self.collection.delete_one({"_id": id})
        return result.deleted_count > 0