import asyncio
from unittest.mock import MagicMock
from src.core.config import Settings
from src.services.crypto_service import CryptoService

async def main():
    settings = Settings(
        bot_token="test",
        admin_ids=[],
        openai_api_key="test",
        ton_api_key="test",  # Not actually used by CoinGecko/Binance logic directly in the snippet seen, but passed to CryptoAPI
        database_url="sqlite+aiosqlite:///:memory:",
        redis_url="redis://localhost"
    )
    
    # Mock Redis to avoid needing a real Redis server
    redis_mock = MagicMock()
    redis_mock.get.return_value = asyncio.Future()
    redis_mock.get.return_value.set_result(None) # Cache miss
    redis_mock.set.return_value = asyncio.Future()
    redis_mock.set.return_value.set_result(None)
    
    service = CryptoService(settings, redis_mock)
    
    # Since we can't easily mock aiohttp without complex setup or external calls, 
    # let's try to actually CALL the external APIs if possible to see if they work.
    # If network is restricted, we will fail.
    
    print("Fetching Top 10...")
    try:
        message = await service.get_top_10_message()
        print("Result:")
        print(message)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
