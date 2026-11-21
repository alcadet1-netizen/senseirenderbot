"""
Pytest fixtures for MongoDB testing.
"""

import asyncio
from typing import AsyncGenerator
from urllib.parse import urlsplit, urlunsplit

import pytest
import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from src.core.config import settings


def _test_db_name() -> str:
    return f"{settings.mongo_db or 'sensei'}_test"


def _test_uri() -> str:
    """URI with the database name swapped for the dedicated *_test database."""
    parts = urlsplit(settings.mongo_uri)
    new_path = "/" + _test_db_name()
    return urlunsplit((parts.scheme, parts.netloc, new_path, parts.query, parts.fragment))


@pytest.fixture
async def mongo_client() -> AsyncGenerator[AsyncIOMotorClient, None]:
    """
    Create a test MongoDB client against a dedicated _test database.
    """
    client = AsyncIOMotorClient(_test_uri())

    yield client

    # Clean up: drop the test database
    await client.drop_database(_test_db_name())
    client.close()


@pytest.fixture
async def database() -> AsyncGenerator[AsyncIOMotorDatabase, None]:
    """
    Get the test database.
    """
    gen = mongo_client()
    client = await gen.__anext__()
    try:
        yield client[_test_db_name()]
    finally:
        await gen.aclose()
