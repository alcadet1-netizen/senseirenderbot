import sys
import asyncio
from unittest.mock import AsyncMock, MagicMock

try:
    from src.services.crypto_service import CryptoService
    from src.core.config import Settings
except ImportError as e:
    sys.stderr.write(f"ImportError: {e}\n")
    sys.exit(1)
except Exception as e:
    sys.stderr.write(f"Error during import: {e}\n")
    sys.exit(1)

async def test_crypto_calc():
    sys.stderr.write("Testing CryptoService.get_calculator_message...\n")
    
    # Mock settings and redis
    settings = MagicMock(spec=Settings)
    settings.ton_api_key = "dummy"
    redis = AsyncMock()
    
    service = CryptoService(settings, redis)
    
    # Mock API
    service.api = AsyncMock()
    
    # Scenario 1: CoinGecko fails, Binance succeeds
    sys.stderr.write("\nScenario 1: CoinGecko fails, Binance succeeds (TON)\n")
    service.api.get_coingecko_price.return_value = None
    service.api.get_binance_ticker.return_value = {"lastPrice": "5.5", "priceChangePercent": "1.2"}
    
    # Mock USDT/RUB rate
    def side_effect(ids, currencies):
        if ids == "tether":
            return {"tether": {"rub": 95.0}}
        return None
    service.api.get_coingecko_price.side_effect = side_effect
    
    result = await service.get_calculator_message("ton", 100)
    sys.stderr.write("Result:\n")
    sys.stderr.write(result + "\n")
    
    if "52,250.00" in result: # 5.5 * 95 * 100 = 52250
        sys.stderr.write("✅ Success: Calculated using Binance fallback\n")
    else:
        sys.stderr.write("❌ Failed: Expected ~52,250.00 ₽\n")

    # Scenario 2: Both fail
    sys.stderr.write("\nScenario 2: Both fail\n")
    service.api.get_binance_ticker.return_value = None
    service.api.get_coingecko_price.side_effect = None
    service.api.get_coingecko_price.return_value = None
    
    result = await service.get_calculator_message("unknown_coin", 100)
    sys.stderr.write("Result:\n")
    sys.stderr.write(result + "\n")
    
    if "Не удалось найти курс" in result:
        sys.stderr.write("✅ Success: Correctly reported failure\n")
    else:
        sys.stderr.write("❌ Failed: Should report failure\n")

if __name__ == "__main__":
    asyncio.run(test_crypto_calc())
