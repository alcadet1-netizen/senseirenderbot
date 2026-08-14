import asyncio
import os
import sys
from unittest.mock import MagicMock, AsyncMock

# Add project root to path
sys.path.append(os.getcwd())

from src.core.config import Settings
from src.services.crypto_service import CryptoService
from src.infra.redis.cache import CacheManager

async def main():
    print("Testing CryptoService.get_top_10_message...")
    
    # Reload settings to pick up .env changes
    from src.core import config
    settings = config.get_settings()
    
    # Mock Settings (already loaded from .env)
    # No need to mock redis as CryptoService doesn't use it directly

    service = CryptoService(settings)
    
    # Bypass cache
    service.cache.get = AsyncMock(return_value=None)
    service.cache.set = AsyncMock()
    
    # Run
    try:
        result = await service.get_top_10_message()
        print("\nResult:")
        print(result)
        
        # Check if favorites are present
        favorites = ["TON", "BTC", "USDT", "DOGE", "SOL", "SUI", "BNB"]
        missing = []
        for fav in favorites:
            if fav not in result:
                missing.append(fav)
        
        if missing:
            print(f"\n❌ Missing favorites: {missing}")
        else:
            print("\n✅ All favorites present.")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
