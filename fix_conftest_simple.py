# Fix the conftest.py file by replacing corrupted characters

# Just write the expected content directly
expected_content = '''"""
Pytest fixtures.
"""

import asyncio
from typing import AsyncGenerator
import pytest
import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from src.core.config import settings
from src.infra.database import db
from main import container


@pytest.fixture
async def mongo_client() -> AsyncGenerator[AsyncIOMotorClient, None]:
    """
    Create a test MongoDB client.
    """
    # Use the provided MongoDB URI for testing
    provided_uri = "mongodb+srv://Sensei01:9876543210Sens!@sens01.qb2e9gc.mongodb.net/?appName=Sens01"
    client = AsyncIOMotorClient(provided_uri)

    # Extract the database name and create a test database
    db_name = settings.MONGO_DB_NAME + "_test"
    test_db = client[db_name]

    yield client

    # Clean up: drop the test database
    await client.drop_database(db_name)


@pytest.fixture
async def database() -> AsyncGenerator[AsyncIOMotorDatabase, None]:
    """
    Get the test database.
    """
    async for client in mongo_client():
        db_name = settings.MONGO_DB_NAME + "_test"
        yield client[db_name]


# Override the container's database dependencies for testing
@pytest.fixture(autouse=True)
def override_container_database(mongo_client: AsyncIOMotorClient):
    """
    Override the container's mongo_client and database dependencies.
    """
    db_name = settings.MONGO_DB_NAME + "_test"
    test_database = mongo_client[db_name]

    # Override the dependencies
    container.mongo_client.override(mongo_client)
    container.database.override(test_database)

    yield

    # Clean up overrides
    container.mongo_client.reset()
    container.database.reset()
'''

# Write the fixed file
with open(r'C:\sensei\tests\conftest.py', 'w', encoding='utf-8') as f:
    f.write(expected_content)

print("Fixed conftest.py file written successfully")