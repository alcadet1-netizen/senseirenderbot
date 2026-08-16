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

    # Initialize Service
    service = CryptoService(settings)
    
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

    # Mock binance ticker
    service.api.get_binance_ticker = AsyncMock(return_value={
        "lastPrice": "5.55",
        "priceChangePercent": "1.23"
    })

    # Test
    try:
        result = await service.get_top_10_message()
    except Exception as e:
        print(f"❌ Exception occurred: {e}")
        return

    # Simple verification without printing Unicode to console
    # Just check if the function executed without error and return a success indicator
    if result and len(result) > 100:  # Basic check that we got some meaningful output
        print("[OK] Function executed and returned substantial result")

        # Let's check specifically for TON section
        if "TON Coin" in result:
            print("[OK] Found 'TON Coin' in result")

            # Check for the specific format being generated
            if "💵 5.55 $" in result and "💴 555.55  ₽" in result:
                print("[OK] Found TON with correct price format")
            else:
                print("[INFO] Checking for TON price format...")
                # Look for variations of the price format
                if "5.55" in result and "$" in result:
                    print("[INFO] Found 5.55 and $ in result")
                if "555.55" in result and "₽" in result:
                    print("[INFO] Found 555.55 and ₽ in result")

                # Show a snippet around TON for debugging
                ton_index = result.find("TON Coin")
                if ton_index >= 0:
                    debug_slice = result[max(0, ton_index-20):min(len(result), ton_index+100)]
                    print(f"[DEBUG] TON section context: {repr(debug_slice)}")
        else:
            print("[FAIL] Did not find 'TON Coin' in result")
            # Let's see what favorites sections we do have
            if "💎 ИЗБРАННОЕ" in result:
                print("[INFO] Found favorites section")
                # Extract a portion around the favorites section for debugging
                fav_index = result.find("💎 ИЗБРАННОЕ")
                if fav_index >= 0:
                    debug_slice = result[max(0, fav_index-50):min(len(result), fav_index+200)]
                    print(f"[DEBUG] Favorites section context: {repr(debug_slice)}")
            else:
                print("[INFO] No favorites section found")
    else:
        print("[FAIL] Function returned empty or too short result")

    # Verification
    if "Bitcoin" in result and "95,123" in result and "9,123,456" in result:
        print("[OK] Bitcoin data present")
    else:
        print("[FAIL] Bitcoin data missing or incorrect")

    if "Ethereum" in result and "3,568" in result and "345,678" in result: # 3567.89 -> $3,568 (rounded > 1000)
        print("[OK] Ethereum data present")
    else:
        print("[FAIL] Ethereum data missing or incorrect")

    if "TON Coin" in result and "💵 5.55 $" in result and "💴 555.55  ₽" in result:
        print("[OK] TON banner present")
    else:
        print("[FAIL] TON banner missing or incorrect")

    if "┏" in result and "┃" in result and "┗" in result:
        print("[OK] Frame characters present")
    else:
        print("[FAIL] Frame characters missing")

if __name__ == "__main__":
    asyncio.run(main())
