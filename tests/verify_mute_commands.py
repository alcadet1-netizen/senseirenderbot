import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta
from sqlalchemy import select

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.core.container import Container
from src.bot.middlewares.moderation import ModerationMiddleware
from src.infra.database.uow import UnitOfWork
from src.domain.repositories import UserRepository
from src.core.config import settings
from src.infra.database import session_factory, engine
from src.infra.redis import redis_client
from src.infra.database.models import Base
from src.infra.database.models.muted_user import MutedUser

async def verify_mute_commands():
    print("🚀 Starting Mute Commands Verification (New Architecture)...")
    
    redis = None
    try:
        # 0. Ensure tables exist (Drop first to ensure schema update)
        async with engine.begin() as conn:
            await conn.run_sync(MutedUser.__table__.drop, checkfirst=True)
            await conn.run_sync(Base.metadata.create_all)
        print("✅ Database tables ensured (recreated)")

        # 1. Initialize dependencies
        redis = await redis_client.connect()
        
        # 2. Initialize Container
        container = Container(
            settings=settings,
            session_factory=session_factory,
            redis=redis
        )
        
        # Create a test user
        test_user_id = 999999999
        test_username = "TestMuteUser"
        
        uow = UnitOfWork(container.session_factory)
        async with uow:
            repo = UserRepository(uow.session)
            user, created = await repo.get_or_create(test_user_id, test_username)
            await uow.commit()
            print(f"✅ Created/Ensured test user {test_user_id} (@{test_username})")

        # Ensure user is NOT muted initially
        await container.moderation_service.unmute_user(test_user_id)

        # 3. Test Permanent Mute Logic (by ID)
        print("\nTesting Permanent Mute (by ID)...")
        result = await container.moderation_service.mute_user(test_user_id)
        if result["success"]:
            print("✅ mute_user returned success")
        else:
            print(f"❌ mute_user failed: {result}")
            return

        is_muted = await container.moderation_service.is_muted(test_user_id)
        if is_muted:
            print("✅ is_muted returned True")
        else:
            print("❌ is_muted returned False")

        # Unmute
        await container.moderation_service.unmute_user(test_user_id)
        print("✅ Unmuted")

        # 4. Test Temporary Mute Logic (by Username)
        print("\nTesting Temporary Mute (by Username, 1 hour)...")
        result = await container.moderation_service.mute_user_by_username(test_username, hours=1)
        if result["success"]:
            print("✅ mute_user_by_username returned success")
        else:
            print(f"❌ mute_user_by_username failed: {result}")
            return

        is_muted = await container.moderation_service.is_muted(test_user_id)
        if is_muted:
            print("✅ is_muted returned True")
        else:
            print("❌ is_muted returned False")

        # Check expiration (manually check cache or DB)
        # We can't easily fast-forward time, but we can check if 'muted_until' is set in DB
        async with container.session_factory() as session:
            m = await session.execute(select(MutedUser).where(MutedUser.user_id == test_user_id))
            muted_user = m.scalar_one()
            if muted_user.muted_until:
                print(f"✅ muted_until is set: {muted_user.muted_until}")
            else:
                print("❌ muted_until is NOT set")

        # Unmute by username
        result = await container.moderation_service.unmute_user_by_username(test_username)
        if result["success"]:
            print("✅ unmute_user_by_username returned success")
        else:
            print(f"❌ unmute_user_by_username failed: {result}")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if redis:
            await redis.aclose()
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(verify_mute_commands())
