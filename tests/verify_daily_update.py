import asyncio
import os
import sys
from datetime import date
from unittest.mock import MagicMock, AsyncMock

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from aiogram.types import FSInputFile
from src.core.container import Container
from src.bot.handlers.user_commands import cmd_daily
from src.infra.database.uow import UnitOfWork
from src.domain.repositories import UserRepository
from src.infra.database.models import DailyClaim
from sqlalchemy import delete
from src.core.config import settings
from src.infra.database import session_factory
from src.infra.redis import redis_client

async def verify_daily_update():
    print("🚀 Starting Daily Command Verification...")
    
    redis = None
    try:
        # 1. Initialize dependencies
        redis = await redis_client.connect()
        
        # 2. Initialize Container
        container = Container(
            settings=settings,
            session_factory=session_factory,
            redis=redis
        )
        
        test_user_id = 123456789
        
        # 3. Reset Daily Claim for Test User
        print("\nResetting daily claim...")
        uow = UnitOfWork(container.session_factory)
        async with uow:
            # Delete today's claim
            await uow.session.execute(
                delete(DailyClaim)
                .where(DailyClaim.user_id == test_user_id)
                .where(DailyClaim.claim_date == date.today())
            )
            
            # Create user if not exists
            repo = UserRepository(uow.session)
            await repo.get_or_create(test_user_id, "TestDailyUser")
            
            await uow.commit()
            print("✅ Daily claim reset.")

        # 4. Mock Message
        message = AsyncMock()
        message.from_user = MagicMock()
        message.from_user.id = test_user_id
        message.from_user.username = "TestDailyUser"
        message.from_user.first_name = "Tester"
        message.from_user.last_name = None
        
        # Mock answer_photo and answer
        message.answer_photo = AsyncMock()
        message.answer = AsyncMock()

        # 5. Call Handler
        print("\nCalling cmd_daily...")
        await cmd_daily(message, container)
        
        # 6. Verify Results
        if message.answer_photo.called:
            print("✅ answer_photo called!")
            
            # Check arguments
            args, kwargs = message.answer_photo.call_args
            photo = args[0]
            caption = kwargs.get('caption')
            
            print(f"   Photo type: {type(photo)}")
            if isinstance(photo, FSInputFile):
                print(f"   Photo path: {photo.path}")
            
            if caption and "Ты погладил ежа" in caption:
                print("✅ Caption contains 'Ты погладил ежа'")
            else:
                print(f"❌ Caption missing expected text. Got: {caption[:50]}...")
                
        elif message.answer.called:
            # Maybe photo failed or folder empty (unlikely as we checked)
            # Or already claimed (but we reset it)
            args, kwargs = message.answer.call_args
            text = args[0]
            print(f"⚠️ answer called instead of answer_photo. Text: {text[:50]}...")
            if "Ты погладил ежа" in text:
                 print("✅ Text contains 'Ты погладил ежа'")
        else:
            print("❌ No response sent!")

    except Exception as e:
        print(f"❌ Error during verification: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if redis:
            await redis.close()

if __name__ == "__main__":
    asyncio.run(verify_daily_update())
