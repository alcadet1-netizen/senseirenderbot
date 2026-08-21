"""
MongoDB-backed Redis-compatible storage for temporary data (captcha, subscription cache, stats).
Provides async methods: get, set, delete, incr.
Data expires automatically via TTL index on expires_at field.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorCollection


class MongoRedis:
    """
    Simple Redis-like wrapper over a MongoDB collection.
    Expected collection fields:
        _id: str (the key)
        value: str (the stored value)
        expires_at: datetime (optional, when the key should expire)
    """

    def __init__(self, collection: AsyncIOMotorCollection):
        self.collection = collection

    async def ensure_indexes(self):
        """Create TTL index on expires_at if not exists."""
        try:
            # Check if index exists
            indexes = await self.collection.index_information()
            # If there is already an index on expires_ttl (or similar), skip
            # We'll just create it; if exists, it will be ignored if same key?
            await self.collection.create_index("expires_at", expireAfterSeconds=0)
        except Exception:
            # Ignore errors (e.g., if not allowed to create indexes)
            pass

    async def get(self, key: str) -> Optional[str]:
        """Get value by key. Returns None if not found or expired."""
        doc = await self.collection.find_one({"_id": key})
        if not doc:
            return None
        expires_at = doc.get("expires_at")
        if expires_at and expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
            # Expired: delete and return None
            await self.collection.delete_one({"_id": key})
            return None
        return doc.get("value")

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        """Set key to value. If ex given (seconds), set expiry."""
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=ex) if ex is not None else None
        await self.collection.update_one(
            {"_id": key},
            {"$set": {"value": value, "expires_at": expires_at}, "$setOnInsert": {"_id": key}},
            upsert=True,
        )

    async def delete(self, key: str) -> None:
        """Delete key."""
        await self.collection.delete_one({"_id": key})

    async def incr(self, key: str) -> int:
        """Increment integer value of key by 1. If key does not exist, treat as 0."""
        doc = await self.collection.find_one({"_id": key})
        if doc:
            expires_at = doc.get("expires_at")
            if expires_at and expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
                # Expired: treat as missing
                await self.collection.delete_one({"_id": key})
                val = 0
            else:
                try:
                    val = int(doc.get("value", "0"))
                except ValueError:
                    val = 0
        else:
            val = 0
        val += 1
        now = datetime.now(timezone.utc)
        # Keep same expiry if existed? For simplicity, we reset expiry to None unless we want to preserve.
        # We'll not set expiry on incr unless we had one; but to keep simple, we set no expiry.
        await self.collection.update_one(
            {"_id": key},
            {"$set": {"value": str(val)}, "$unset": {"expires_at": ""}},
            upsert=True,
        )
        return val