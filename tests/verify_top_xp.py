import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.container import Container
from src.core.config import settings
from src.infra.database import session_factory
from src.infra.redis import redis_client

async def verify_top_xp():
    print("🚀 Verifying get_top_by_xp...")
    
    # Initialize redis
    redis = await redis_client.connect()
    
    # Initialize container
    container = Container(
        settings=settings,
        session_factory=session_factory,
        redis=redis
    )
    
    # Try to call get_top_by_xp
    try:
        top_xp = await container.user_service.get_top_by_xp(10)
        print(f"✅ get_top_by_xp called successfully. Result count: {len(top_xp)}")
        for user in top_xp:
            print(f"   - {user.get('username')}: {user.get('xp')} XP (Level {user.get('level')})")
    except AttributeError as e:
        print(f"❌ AttributeError: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        # Close resources if needed (Container might need cleanup if it opens DB pools)
        # For this simple test, we might just let it exit, but properly closing is better if methods exist.
        pass

if __name__ == "__main__":
    asyncio.run(verify_top_xp())
