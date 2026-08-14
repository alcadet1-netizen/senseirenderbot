import asyncio
import os
import sys
import random
from datetime import datetime, timedelta, timezone
from sqlalchemy import update, select
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
from src.infra.database.models import User
from src.core.exceptions import (
    CooldownError,
    InsufficientFundsError,
    NoKatanaError,
    UserNotFoundError
)

async def verify_katana():
    print("🚀 Starting Katana Upgrade Verification...")
    
    redis = None
    try:
        # 1. Initialize dependencies
        redis = await redis_client.connect()
        container = Container(
            settings=settings,
            session_factory=session_factory,
            redis=redis
        )
        
        # 2. Setup Test User
        test_user_id = 888888888
        uow = UnitOfWork(container.session_factory)
        
        print("\n📝 Setting up Test User...")
        async with uow:
            repo = UserRepository(uow.session)
            user, created = await repo.get_or_create(test_user_id, "TestKatana")
            
            # Reset state
            user.has_katana = True
            user.katana_length = 10.0
            user.coins = 1000.0
            user.last_katana_up = None
            
            await uow.commit()
            print(f"✅ User {test_user_id} ready: Coins={user.coins}, Katana={user.has_katana}, Len={user.katana_length}")

        # 3. Test Success Upgrade
        print("\n⚔️ Testing Successful Upgrade...")
        try:
            res = await container.economy_service.upgrade_katana(test_user_id)
            print(f"✅ Upgrade result: {res}")
            print(f"   Growth: {res['growth']}, New Len: {res['new_length']}")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            raise

        # 4. Test Cooldown
        print("\n⏳ Testing Cooldown...")
        try:
            await container.economy_service.upgrade_katana(test_user_id)
            print("❌ Should have raised CooldownError!")
        except CooldownError as e:
            print(f"✅ Correctly raised CooldownError: {e}")
        except Exception as e:
            print(f"❌ Wrong error type: {type(e)} - {e}")

        # 5. Test Manual Reset of Timer (Simulate time pass)
        print("\n🕰️ Simulating time pass (4 hours)...")
        async with uow:
            stmt = select(User).where(User.id == test_user_id)
            res = await uow.session.execute(stmt)
            user = res.scalar_one()
            user.last_katana_up = datetime.now(timezone.utc) - timedelta(hours=4)
            await uow.commit()
        
        # 6. Test Insufficient Funds
        print("\n💰 Testing Insufficient Funds...")
        # Set coins to 0
        async with uow:
            stmt = select(User).where(User.id == test_user_id)
            res = await uow.session.execute(stmt)
            user = res.scalar_one()
            user.coins = 10.0 # Less than 100
            await uow.commit()
            
        try:
            await container.economy_service.upgrade_katana(test_user_id)
            print("❌ Should have raised InsufficientFundsError!")
        except InsufficientFundsError as e:
            print(f"✅ Correctly raised InsufficientFundsError: {e}")

        # 7. Test No Katana
        print("\n🚫 Testing No Katana...")
        async with uow:
            stmt = select(User).where(User.id == test_user_id)
            res = await uow.session.execute(stmt)
            user = res.scalar_one()
            user.has_katana = False
            await uow.commit()
            
        try:
            await container.economy_service.upgrade_katana(test_user_id)
            print("❌ Should have raised NoKatanaError!")
        except NoKatanaError as e:
            print(f"✅ Correctly raised NoKatanaError: {e}")

    except Exception as e:
        print(f"❌ Global Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if redis:
            await redis.aclose()

if __name__ == "__main__":
    asyncio.run(verify_katana())
