import asyncio
import os
import sys
import random
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
from src.infra.database.models import DailyClaim
from sqlalchemy import delete

from src.core.exceptions import DailyAlreadyClaimedError

async def verify_daily():
    print("🚀 Starting Daily Bonus Verification...")
    
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
        test_user_id = 777777777
        uow = UnitOfWork(container.session_factory)
        async with uow:
            repo = UserRepository(uow.session)
            await repo.get_or_create(test_user_id, "TestDailyUser")
            # Reset daily claim for test
            await uow.session.execute(
                delete(DailyClaim).where(DailyClaim.user_id == test_user_id)
            )
            await uow.commit()
            print(f"✅ Reset daily claim for user {test_user_id}")

        # 3. Test Service Claim (First Time)
        print("\nTesting claim_daily (1st attempt)...")
        result = await container.daily_service.claim_daily(test_user_id)
        
        if result["success"]:
            print(f"✅ Claim success: +{result['total_xp']} XP, +{result['total_coins']} Coins")
        else:
            print(f"❌ Claim failed: {result}")
            
        # 3.1 Test Service Claim (Second Time - Expect Cooldown)
        print("\nTesting claim_daily (2nd attempt - Cooldown Check)...")
        try:
            await container.daily_service.claim_daily(test_user_id)
            print("❌ Should have raised DailyAlreadyClaimedError!")
        except DailyAlreadyClaimedError as e:
            print(f"✅ Correctly raised error: {e}")
            print(f"Next claim info: {e.next_claim_time}")
            
        # 4. Verify 'ega' folder access (Simulation of handler logic)
        print("\nVerifying 'ega' folder...")
        # Path relative to src/bot/handlers/user_commands.py
        # user_commands.py is in src/bot/handlers
        # We are in tests/
        # Construct path as if we are in user_commands.py
        # os.path.join(os.path.dirname(__file__), "..", "..", "infra", "storage", "ega")
        
        # But here __file__ is tests/verify_daily.py
        # relative to project root:
        # src/infra/storage/ega
        
        base_path = os.path.dirname(os.path.dirname(__file__)) # Project root (c:\Users\bot\Desktop\sensei\GPT\sensei)
        ega_path = os.path.join(base_path, "src", "infra", "storage", "ega")
        
        print(f"Checking path: {ega_path}")
        if os.path.exists(ega_path):
            images = [f for f in os.listdir(ega_path) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif'))]
            print(f"✅ Folder exists. Found {len(images)} images.")
            if images:
                print(f"Sample image: {random.choice(images)}")
            else:
                print("⚠️ No images found!")
        else:
            print("❌ Folder does not exist!")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if redis:
            await redis.aclose()
        # await container.close_resources() # Container doesn't have this method
        # Clean up redis connection if needed or just let it close on exit

if __name__ == "__main__":
    asyncio.run(verify_daily())
