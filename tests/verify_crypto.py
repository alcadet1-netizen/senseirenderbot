import asyncio
import sys
import os
from unittest.mock import MagicMock

# Add project root to path
sys.path.append(os.getcwd())

from src.services.crypto_service import CryptoService
from src.core.config import Settings

async def main():
    print("Testing CryptoService.get_top_10_message...")
    
    # Mock Settings
    settings = MagicMock(spec=Settings)
    settings.ton_api_key = "" # Empty key

    service = CryptoService(settings)
    
    # Mock CacheManager.get to return None (async)
    async def mock_get(key):
        return None
    service.cache.get = mock_get
    
    # Mock CacheManager.set (async)
    async def mock_set(key, value, ttl=300):
        pass
    service.cache.set = mock_set

    # Test specific price fetch
    print("Testing specific price fetch for 'toncoin'...")
    price_data = await service.api.get_coingecko_price("toncoin", "usd")
    print(f"Price data for toncoin: {price_data}")

    # Run
    try:
        message = await service.get_top_10_message()
        print("\n--- Result Message ---\n")
        print(message)
        print("\n----------------------\n")
        
        if "🏆 ТОП-10 КРИПТОВАЛЮТ" in message and "TON" in message and "SUI" in message:
             print("✅ Test Passed: Output contains header and expected coins.")
        else:
             print("❌ Test Failed: Output missing required elements.")
             
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
