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

    async def get_binance_orderbook(self, symbol: str = "TONUSDT") -> Optional[Dict[str, Any]]:
        """Получить стакан с Binance (bid/ask)."""
        url = f"https://api.binance.com/api/v3/ticker/bookTicker?symbol={symbol.upper()}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if response.status == 200:
                        return await response.json()
        except Exception:
            pass
        return None

    async def get_bybit_ticker(self, symbol: str = "TONUSDT") -> Optional[Dict[str, Any]]:
        """Получить тикер с Bybit."""
        url = f"https://api.bybit.com/v5/market/tickers?category=spot&symbol={symbol.upper()}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if response.status == 200:
                        return await response.json()
        except Exception:
            pass
        return None

    async def get_okx_ticker(self, inst_id: str = "TON-USDT") -> Optional[Dict[str, Any]]:
        """Получить тикер с OKX."""
        url = f"https://www.okx.com/api/v5/market/ticker?instId={inst_id.upper()}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if response.status == 200:
                        return await response.json()
        except Exception:
            pass
        return None

    async def get_mexc_ticker(self, symbol: str = "TONUSDT") -> Optional[Dict[str, Any]]:
        """Получить тикер с MEXC."""
        url = f"https://api.mexc.com/api/v3/ticker/bookTicker?symbol={symbol.upper()}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if response.status == 200:
                        return await response.json()
        except Exception:
            pass
        return None

    async def get_gateio_ticker(self, pair: str = "TON_USDT") -> Optional[Dict[str, Any]]:
        """Получить тикер с Gate.io."""
        url = f"https://api.gateio.ws/api/v4/spot/tickers?currency_pair={pair.upper()}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if response.status == 200:
                        return await response.json()
        except Exception:
            pass
        return None

    async def get_kucoin_ticker(self, symbol: str = "TON-USDT") -> Optional[Dict[str, Any]]:
        """Получить тикер с KuCoin."""
        url = f"https://api.kucoin.com/api/v1/market/orderbook/level1?symbol={symbol.upper()}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if response.status == 200:
                        return await response.json()
        except Exception:
            pass
        return None

    async def get_tonapi_price(self) -> Optional[float]:
        """Получить цену с TonApi."""
        url = "https://tonapi.io/v2/rates?tokens=ton&currencies=usd"
        headers = {}
        if self.ton_api_key:
             headers["Authorization"] = f"Bearer {self.ton_api_key}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("rates", {}).get("TON", {}).get("prices", {}).get("USD")
        except Exception:
            pass
        return None

    async def get_ton_usd_prices(self) -> Dict[str, Dict[str, float]]:
        """
        Получить цены TON с разных бирж в формате:
        {
            'source_name': {'bid': float, 'ask': float},
            ...
        }
        """
        results: Dict[str, Dict[str, float]] = {}

        tasks = {
            "CoinGecko": self.get_coingecko_price("toncoin", "usd"),
            "Binance": self.get_binance_orderbook(), # Используем orderbook endpoint
            "CoinMarketCap": self.get_quote("TONCOIN"),
            "TonApi": self.get_tonapi_price(),
            "Bybit": self.get_bybit_ticker(),
            "OKX": self.get_okx_ticker(),
            "MEXC": self.get_mexc_ticker(),
            "Gate.io": self.get_gateio_ticker(),
            "KuCoin": self.get_kucoin_ticker(),
        }

        # Запускаем все задачи
        responses = await asyncio.gather(*tasks.values(), return_exceptions=True)

        for name, response in zip(tasks.keys(), responses):
            if isinstance(response, Exception) or not response:
                continue

            try:
                bid, ask = 0.0, 0.0

                if name == "CoinGecko":
                    # response is dict
                    price = float(response.get("toncoin", {}).get("usd", 0) or 0)
                    bid = ask = price

                elif name == "Binance":
                    # response is {'symbol': 'TONUSDT', 'bidPrice': '...', 'askPrice': '...'}
                    bid = float(response.get("bidPrice", 0))
                    ask = float(response.get("askPrice", 0))

                elif name == "CoinMarketCap":
                    # response is quote dict
                    price = float(response.get("quote", {}).get("USD", {}).get("price", 0) or 0)
                    bid = ask = price

                elif name == "TonApi":
                    # response is float (price)
                    price = float(response)
                    bid = ask = price

                elif name == "Bybit":
                    # {'result': {'list': [{'bid1Price': '...', 'ask1Price': '...'}]}}
                    item = response.get("result", {}).get("list", [{}])[0]
                    bid = float(item.get("bid1Price", 0))
                    ask = float(item.get("ask1Price", 0))

                elif name == "OKX":
                    # {'data': [{'bidPx': '...', 'askPx': '...'}]}
                    item = response.get("data", [{}])[0]
                    bid = float(item.get("bidPx", 0))
                    ask = float(item.get("askPx", 0))

                elif name == "MEXC":
                    # {'bidPrice': '...', 'askPrice': '...'}
                    bid = float(response.get("bidPrice", 0))
                    ask = float(response.get("askPrice", 0))

                elif name == "Gate.io":
                    # [{'highest_bid': '...', 'lowest_ask': '...'}] (list of 1)
                    if isinstance(response, list) and len(response) > 0:
                        item = response[0]
                        bid = float(item.get("highest_bid", 0))
                        ask = float(item.get("lowest_ask", 0))

                elif name == "KuCoin":
                    # {'data': {'bestBid': '...', 'bestAsk': '...'}}
                    data = response.get("data", {})
                    bid = float(data.get("bestBid", 0))
                    ask = float(data.get("bestAsk", 0))

                if bid > 0 and ask > 0:
                    results[name] = {"bid": bid, "ask": ask}

            except Exception:
                pass

        return results

    async def get_symbol_usd_orderbooks(self, base_symbol: str) -> Dict[str, Dict[str, float]]:
        results: Dict[str, Dict[str, float]] = {}
        sym = base_symbol.upper()

        tasks = {
            "Binance": self.get_binance_orderbook(f"{sym}USDT"),
            "Bybit": self.get_bybit_ticker(f"{sym}USDT"),
            "OKX": self.get_okx_ticker(f"{sym}-USDT"),
            "MEXC": self.get_mexc_ticker(f"{sym}USDT"),
            "Gate.io": self.get_gateio_ticker(f"{sym}_USDT"),
            "KuCoin": self.get_kucoin_ticker(f"{sym}-USDT"),
        }

        responses = await asyncio.gather(*tasks.values(), return_exceptions=True)

        for name, response in zip(tasks.keys(), responses):
            if isinstance(response, Exception) or not response:
                continue

            try:
                bid, ask = 0.0, 0.0

                if name == "Binance":
                    bid = float(response.get("bidPrice", 0))
                    ask = float(response.get("askPrice", 0))
                elif name == "Bybit":
                    item = response.get("result", {}).get("list", [{}])[0]
                    bid = float(item.get("bid1Price", 0))
                    ask = float(item.get("ask1Price", 0))
                elif name == "OKX":
                    item = response.get("data", [{}])[0]
                    bid = float(item.get("bidPx", 0))
                    ask = float(item.get("askPx", 0))
                elif name == "MEXC":
                    bid = float(response.get("bidPrice", 0))
                    ask = float(response.get("askPrice", 0))
                elif name == "Gate.io":
                    if isinstance(response, list) and len(response) > 0:
                        item = response[0]
                        bid = float(item.get("highest_bid", 0))
                        ask = float(item.get("lowest_ask", 0))
                elif name == "KuCoin":
                    data = response.get("data", {})
                    bid = float(data.get("bestBid", 0))
                    ask = float(data.get("bestAsk", 0))

                if bid > 0 and ask > 0:
                    results[name] = {"bid": bid, "ask": ask}
            except Exception:
                pass

        return results