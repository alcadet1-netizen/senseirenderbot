"""
Pytest fixtures for MongoDB testing.
"""

import asyncio
from typing import AsyncGenerator
import pytest
import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from src.core.config import settings


@pytest.fixture
async def mongo_client() -> AsyncGenerator[AsyncIOMotorClient, None]:
    """
    Create a test MongoDB client.
    """
    # Use a test database name to avoid interfering with production data
    test_uri = settings.mongo_uri.replace(
        settings.MONGO_DB_NAME,
        f"{settings.MONGO_DB_NAME}_test"
    )
    client = AsyncIOMotorClient(test_uri)

    yield client

    # Clean up: drop the test database
    await client.drop_database(f"{settings.MONGO_DB_NAME}_test")


@pytest.fixture
async def database() -> AsyncGenerator[AsyncIOMotorDatabase, None]:
    """
    Get the test database.
    """
    async for client in mongo_client():
        yield client[f"{settings.MONGO_DB_NAME}_test"]