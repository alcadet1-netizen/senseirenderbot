import asyncio
import sys
import os
from unittest.mock import AsyncMock, MagicMock

# Add project root to path
sys.path.append(os.getcwd())

from src.services.crypto_service import CryptoService
from src.core.config import Settings

async def main():
    print("Testing CryptoService.get_top_10_message...")
    
    # Mock Settings
    settings = MagicMock(spec=Settings)
    settings.ton_api_key = "fake_key"

    # Mock Redis
    redis = AsyncMock()
    redis.get.return_value = None  # No cache

    # Initialize Service
    service = CryptoService(settings, redis)
    
    # Mock API
    service.api = AsyncMock()
    
    # Mock data
    # Note: side_effect iterates through calls. 
    # Logic calls get_coingecko_top_10("usd") then get_coingecko_top_10("rub") in parallel (gather).
    # The order of execution in gather is not strictly guaranteed for side_effect if they were sequential, 
    # but gather starts them. However, since we mock the method, we can check arguments or just return based on call.
    # Easier: side_effect function.
    
    async def get_top_side_effect(vs_currency="usd"):
        if vs_currency == "usd":
            return [
                {"id": "bitcoin", "symbol": "btc", "name": "Bitcoin", "current_price": 95123.45, "price_change_percentage_24h": 5.23},
                {"id": "ethereum", "symbol": "eth", "name": "Ethereum", "current_price": 3567.89, "price_change_percentage_24h": -2.15},
                # Add enough items if needed, but loop handles any length
            ]
        elif vs_currency == "rub":
            return [
                {"id": "bitcoin", "current_price": 9123456.0},
                {"id": "ethereum", "current_price": 345678.0},
            ]
        return []

    service.api.get_coingecko_top_10.side_effect = get_top_side_effect
    
    service.api.get_coingecko_price.return_value = {
        "toncoin": {"usd": 5.55, "rub": 555.55, "usd_24h_change": 1.23}
    }

    # Test
    result = await service.get_top_10_message()
    print("\n--- Result Start ---")
    print(result)
    print("--- Result End ---\n")

    # Verification
    if "Bitcoin" in result and "95,123" in result and "9,123,456" in result:
        print("✅ Bitcoin data present")
    else:
        print("❌ Bitcoin data missing or incorrect")

    if "Ethereum" in result and "3,568" in result and "345,678" in result: # 3567.89 -> $3,568 (rounded > 1000)
        print("✅ Ethereum data present")
    else:
        print("❌ Ethereum data missing or incorrect")

    if "THE OPEN NETWORK" in result and "5.55 $" in result and "555.55 ₽" in result:
        print("✅ TON banner present")
    else:
        print("❌ TON banner missing or incorrect")
        
    if "┏" in result and "┃" in result and "┗" in result:
        print("✅ Frame characters present")
    else:
        print("❌ Frame characters missing")

if __name__ == "__main__":
    asyncio.run(main())
