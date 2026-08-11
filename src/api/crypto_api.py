"""
💰 API для криптовалют.
"""

import aiohttp
from typing import Optional, Dict, Any


class CryptoAPI:
    """Клиент для работы с криптовалютными API."""
    
    CMC_BASE_URL = "https://pro-api.coinmarketcap.com/v1"
    
    def __init__(self, api_key: str):
        self.api_key = api_key
    
    async def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Получить котировку криптовалюты (CoinMarketCap)."""
        if not self.api_key:
            return None
        
        url = f"{self.CMC_BASE_URL}/cryptocurrency/quotes/latest"
        headers = {
            "X-CMC_PRO_API_KEY": self.api_key,
            "Accept": "application/json",
        }
        params = {"symbol": symbol.upper(), "convert": "USD"}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers=headers,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("data", {}).get(symbol.upper())
        except Exception:
            pass
        
        return None

    async def get_binance_ticker(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Получить данные о тикере с Binance."""
        url = "https://api.binance.com/api/v3/ticker/24hr"
        params = {"symbol": f"{symbol.upper()}USDT"}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        return await response.json()
        except Exception:
            pass
        return None

    async def get_coingecko_price(self, coin_ids: str, vs_currencies: str = "usd,rub") -> Optional[Dict[str, Any]]:
        """Получить цену с CoinGecko."""
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {
            "ids": coin_ids,
            "vs_currencies": vs_currencies,
            "include_24hr_change": "true",
            "include_market_cap": "true"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        return await response.json()
        except Exception:
            pass
        return None

    async def get_coingecko_top_10(self, vs_currency: str = "usd") -> Optional[list]:
        """Получить топ-10 криптовалют с CoinGecko."""
        url = "https://api.coingecko.com/api/v3/coins/markets"
        params = {
            "vs_currency": vs_currency,
            "order": "market_cap_desc",
            "per_page": "10",
            "page": "1",
            "sparkline": "false"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        return await response.json()
        except Exception:
            pass
        return None