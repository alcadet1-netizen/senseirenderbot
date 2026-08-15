"""
MongoDB client wrapper using Motor.
"""
import os
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from src.core.config import settings


class MongoClient:
    """Wrapper for Motor async MongoDB client."""

    def __init__(self):
        self._client: Optional[AsyncIOMotorClient] = None
        self._db: Optional[AsyncIOMotorDatabase] = None

    async def connect(self):
        """Connect to MongoDB."""
        if self._client is None:
            self._client = AsyncIOMotorClient(settings.mongo_uri)
            if settings.mongo_db:
                self._db = self._client[settings.mongo_db]
            else:
                # Fallback to database name from URI if available, otherwise raise error
                # Parse database name from URI if present (mongodb://host:port/dbname)
                from urllib.parse import urlparse
                parsed = urlparse(settings.mongo_uri)
                db_name = parsed.path.lstrip('/')
                if db_name:
                    self._db = self._client[db_name]
                else:
                    self._db = self._client.get_default_database()
            # Optionally ping to verify connection
            await self._db.command("ping")

    async def close(self):
        """Close MongoDB connection."""
        if self._client:
            self._client.close()
            self._client = None
            self._db = None

    @property
    def database(self) -> AsyncIOMotorDatabase:
        """Get the default database."""
        if self._db is None:
            raise RuntimeError("MongoDB not connected. Call connect() first.")
        return self._db

    def get_collection(self, name: str):
        """Get a collection by name."""
        return self.database[name]