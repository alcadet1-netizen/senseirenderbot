import asyncio
import sys
import os

# Add project root to python path
sys.path.append(os.getcwd())

from src.infra.database.session import session_factory
from src.domain.repositories.user_repository import UserRepository
from src.infra.database.models import User

async def verify_fix():
    print("Verifying UserRepository.get_or_create fix...")
    async with session_factory() as session:
        repo = UserRepository(session)
        
        # Test ID
        test_id = 999999
        
        # Clean up if exists
        user = await repo.get_by_id(test_id)
        if user:
            await session.delete(user)
            await session.flush()
        
        try:
            # Try calling get_or_create with is_bot
            print("Calling get_or_create with is_bot=True...")
            user, created = await repo.get_or_create(
                user_id=test_id,
                username="TestBotUser",
                first_name="Test Bot",
                is_bot=True
            )
            
            print(f"Result: created={created}, user.is_bot={user.is_bot}")
            
            if user.is_bot is True:
                print("SUCCESS: User created with is_bot=True")
            else:
                print("FAILURE: User created but is_bot is not True")
                
            # Test update
            print("Testing update (changing is_bot to False)...")
            user, created = await repo.get_or_create(
                user_id=test_id,
                username="TestBotUser",
                first_name="Test Bot",
                is_bot=False
            )
            print(f"Result: created={created}, user.is_bot={user.is_bot}")
            
            if user.is_bot is False:
                print("SUCCESS: User updated with is_bot=False")
            else:
                print("FAILURE: User not updated correctly")

            # Cleanup
            await session.delete(user)
            await session.commit()
            
        except TypeError as e:
            print(f"FAILURE: TypeError caught: {e}")
        except Exception as e:
            print(f"FAILURE: Unexpected exception: {e}")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(verify_fix())
