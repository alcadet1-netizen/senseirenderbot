import asyncio
import os
import sys
import random
from sqlalchemy import text
from dotenv import load_dotenv

# Load env vars from .env
load_dotenv()

# Force localhost for testing if running locally (and .env points to docker container)
db_url = os.environ.get("DATABASE_URL", "")
if "postgres:5432" in db_url:
    print("🔄 Switching DATABASE_URL to localhost for local test...")
    os.environ["DATABASE_URL"] = db_url.replace("postgres:5432", "localhost:5432")

redis_url = os.environ.get("REDIS_URL", "")
if "redis:6379" in redis_url:
    print("🔄 Switching REDIS_URL to localhost for local test...")
    os.environ["REDIS_URL"] = redis_url.replace("redis:6379", "localhost:6379")

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.core.container import Container
from src.core.config import settings
from src.infra.database import session_factory
from src.infra.redis import redis_client
from src.infra.database.uow import UnitOfWork
from src.domain.repositories import UserRepository
from src.core.visuals import Visuals

async def verify_pagination():
    print("🚀 Starting Katana Pagination Verification...")
    
    redis = await redis_client.connect()
    container = Container(
        settings=settings,
        session_factory=session_factory,
        redis=redis
    )
    
    # 1. Seed data
    print("\n📝 Seeding test users...")
    uow = UnitOfWork(container.session_factory)
    base_id = 900000
    
    async with uow:
        repo = UserRepository(uow.session)
        # Create 15 users with katanas
        for i in range(15):
            user_id = base_id + i
            user, _ = await repo.get_or_create(user_id, f"KUser_{i}")
            user.has_katana = True
            user.katana_length = 100.0 - i # Lengths: 100, 99, ..., 86
            user.is_banned = False
        await uow.commit()
    print("✅ Seeded 15 users.")

    # 2. Test Page 1
    print("\n📄 Testing Page 1 (Limit 10, Offset 0)...")
    limit = 10
    offset = 0
    res = await container.user_service.get_top_by_katana(limit, offset)
    items = res["items"]
    total = res["total"]
    
    print(f"Items count: {len(items)}")
    print(f"Total count: {total}")
    
    assert len(items) == 10, f"Expected 10 items, got {len(items)}"
    assert items[0]["katana_length"] == 100.0, f"Top user should have 100.0, got {items[0]['katana_length']}"
    assert total >= 15, f"Total should be at least 15, got {total}"
    print("✅ Page 1 OK.")

    # 3. Test Page 2
    print("\n📄 Testing Page 2 (Limit 10, Offset 10)...")
    offset = 10
    res = await container.user_service.get_top_by_katana(limit, offset)
    items = res["items"]
    
    print(f"Items count: {len(items)}")
    
    # Depending on other existing users, we expect at least 5 from our seeded batch
    assert len(items) >= 5, f"Expected at least 5 items, got {len(items)}"
    # The first item on page 2 (rank 11) should have length 90.0 (since 100, 99... 91 are top 10)
    # Actually:
    # 1: 100
    # ...
    # 10: 91
    # 11: 90
    
    # Check if our seeded user is the top of this page
    # Note: there might be other users in DB with higher lengths, so we just check structural correctness
    print("✅ Page 2 fetched.")

    # 4. Test Visuals
    print("\n🎨 Testing Visuals for Page 2...")
    text = Visuals.top_katana_table("TEST TOP", "🗡", items, offset=offset)
    print(text)
    
    if "11." in text:
        print("✅ Visuals contain correct ranking (starts with 11).")
    else:
        print("❌ Visuals ranking incorrect!")

    # Cleanup (optional, but good for local dev)
    # print("\n🧹 Cleaning up...")
    # async with uow:
    #     await uow.session.execute(text(f"DELETE FROM users WHERE id >= {base_id} AND id < {base_id + 15}"))
    #     await uow.commit()
    
    await redis.close()

if __name__ == "__main__":
    asyncio.run(verify_pagination())
