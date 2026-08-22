"""
💰 Сервис криптовалют - упрощенная версия с фокусом на USDT.
"""

import asyncio
import re
import time
import logging
from typing import Optional, List, Any

from src.core.config import Settings
from src.core.cache import SimpleCache
from src.core.visuals import Visuals
from src.api.crypto_api import CryptoAPI

logger = logging.getLogger(__name__)


class CryptoService:
    """Сервис для получения курсов криптовалют в USDT."""

    SYMBOL_MAP = {
        "ton": "toncoin",
        "btc": "bitcoin",
        "eth": "ethereum",
        "usdt": "tether",
        "bnb": "binancecoin",
        "sol": "solana",
        "not": "notcoin",
        "dogs": "dogs",
        "hmstr": "hamster-kombat",
        "sui": "sui",
        "doge": "dogecoin",
    }

    def __init__(self, settings: Settings):
        self.settings = settings
        self.api = CryptoAPI(settings.ton_api_key)
        # Cache for prices: key -> (price, expiry_timestamp)
        self._price_cache = SimpleCache()
        self._price_cache_ttl = 10  # seconds

    async def _get_cached_price(self, coin_id: str, vs_currency: str) -> Optional[float]:
        """Get cached price if available and not expired."""
        key = f"{coin_id}:{vs_currency}"
        cached = await self._price_cache.get(key)
        if cached is not None:
            try:
                return float(cached)
            except ValueError:
                pass
        return None

    async def _set_cached_price(self, coin_id: str, vs_currency: str, price: float):
        """Cache price with TTL."""
        key = f"{coin_id}:{vs_currency}"
        await self._price_cache.set(key, str(price), ex=self._price_cache_ttl)

    async def _fetch_price_from_coingecko(self, coin_id: str, vs_currency: str) -> Optional[float]:
        """Fetch price from CoinGecko."""
        try:
            data = await self.api.get_coingecko_price(coin_id, vs_currency)
            if data and coin_id in data:
                price = data[coin_id].get(vs_currency)
                if price is not None:
                    return float(price)
        except Exception:
            pass
        return None

    async def _fetch_price_from_binance(self, symbol: str) -> Optional[float]:
        """Fetch price from Binance ticker."""
        try:
            ticker = await self.api.get_binance_ticker(symbol)
            if ticker:
                price = ticker.get("lastPrice")
                if price is not None:
                    return float(price)
        except Exception:
            pass
        return None

    async def _fetch_price_from_bybit(self, symbol: str) -> Optional[float]:
        """Fetch price from Bybit ticker."""
        try:
            ticker = await self.api.get_bybit_ticker(symbol)
            if ticker:
                # Bybit response: {'result': {'list': [{'lastPrice': '...'}]}}
                result = ticker.get("result", {})
                if isinstance(result, dict):
                    lst = result.get("list", [])
                    if lst and isinstance(lst, list):
                        price = lst[0].get("lastPrice")
                        if price is not None:
                            return float(price)
                elif isinstance(result, list) and result:
                    price = result[0].get("lastPrice")
                    if price is not None:
                        return float(price)
        except Exception:
            pass
        return None

    async def _fetch_price_from_okx(self, symbol: str) -> Optional[float]:
        """Fetch price from OKX ticker."""
        try:
            ticker = await self.api.get_okx_ticker(f"{symbol}-USDT")
            if ticker:
                # OKX response: {'data': [{'last': '...'}]}
                data = ticker.get("data", [])
                if data and isinstance(data, list):
                    price = data[0].get("last")
                    if price is not None:
                        return float(price)
        except Exception:
            pass
        return None

    async def _fetch_price_from_coinmarketcap(self, symbol: str) -> Optional[float]:
        """Fetch price from CoinMarketCap (requires API key)."""
        try:
            if not self.settings.ton_api_key:  # Actually CoinMarketCap uses a different key, but we don't have it in settings.
                # We don't have a CoinMarketCap API key in settings, so skip.
                return None
            quote = await self.api.get_quote(symbol)
            if quote:
                # Quote structure: {'USD': {'price': '...'}}
                usd = quote.get("quote", {}).get("USD", {})
                price = usd.get("price")
                if price is not None:
                    return float(price)
        except Exception:
            pass
        return None

    async def _fetch_price_with_fallback(self, coin_id: str, symbol: str, vs_currency: str = "usdt") -> Optional[float]:
        """
        Fetch price with fallback sources.
        Order: CoinGecko -> Binance -> Bybit -> OKX -> CoinMarketCap (if configured)
        """
        # Try cache first
        cached = await self._get_cached_price(coin_id, vs_currency)
        if cached is not None:
            return cached

        # Try each source in order
        price = None
        # 1. CoinGecko
        price = await self._fetch_price_from_coingecko(coin_id, vs_currency)
        if price is not None and price > 0:
            await self._set_cached_price(coin_id, vs_currency, price)
            return price

        # 2. Binance
        price = await self._fetch_price_from_binance(symbol)
        if price is not None and price > 0:
            await self._set_cached_price(coin_id, vs_currency, price)
            return price

        # 3. Bybit
        price = await self._fetch_price_from_bybit(symbol)
        if price is not None and price > 0:
            await self._set_cached_price(coin_id, vs_currency, price)
            return price

        # 4. OKX
        price = await self._fetch_price_from_okx(symbol)
        if price is not None and price > 0:
            await self._set_cached_price(coin_id, vs_currency, price)
            return price

        # 5. CoinMarketCap (if API key available)
        # Note: We don't have a separate API key for CoinMarketCap in settings.
        # If we wanted to use it, we would need to add a setting.
        # For now, we skip because we don't have the key.
        # price = await self._fetch_price_from_coinmarketcap(symbol)
        # if price is not None and price > 0:
        #     await self._set_cached_price(coin_id, vs_currency, price)
        #     return price

        # If all sources fail, return None
        return None

    async def get_top_10_message(self) -> str:
        """Получить ТОП-10 криптовалют в USDT."""
        # Получаем топ-10 в USDT
        top_10 = await self.api.get_coingecko_top_10("usdt")
        logger.info(f"[CRYPTO_SERVICE] CoinGecko top_10 result: {len(top_10) if top_10 else 0}")

        if not top_10:
            # Fallback to Binance for popular coins if CoinGecko fails
            logger.info("[CRYPTO_SERVICE] CoinGecko returned empty, falling back to Binance")
            popular_coins = ["BTC", "ETH", "USDT", "BNB", "SOL", "XRP", "ADA", "DOGE", "TRX", "DOT"]
            lines = []
            width = 32
            lines.append(Visuals.frame_top_left(width))
            lines.append(Visuals.frame_line_left("🏆 ТОП-10 КРИПТОВАЛЮТ (USDT)", width, "center"))
            lines.append(Visuals.frame_separator_left(width))

            for i, symbol in enumerate(popular_coins, 1):
                ticker = await self.api.get_binance_ticker(symbol)
                if ticker is None:
                    logger.info(f"[CRYPTO_SERVICE] Binance ticker for {symbol} returned None")
                else:
                    logger.info(f"[CRYPTO_SERVICE] Binance ticker for {symbol} OK")
                    price = float(ticker.get("lastPrice", 0))
                    change = float(ticker.get("priceChangePercent", 0))
                    emoji = "📈" if change >= 0 else "📉"
                    lines.append(Visuals.frame_line_left(f"{i}. {symbol}", width))
                    lines.append(Visuals.frame_line_left(f"💵 ${price:,.4f}", width))
                    lines.append(Visuals.frame_line_left(f"{emoji} {change:+.2f}%", width))
                    if i < len(popular_coins):
                        lines.append(Visuals.frame_separator_left(width))

            lines.append(Visuals.frame_bottom_left(width))
            result = f"<pre>{chr(10).join(lines)}</pre>"
            logger.info(f"[CRYPTO_SERVICE] Fallback result length: {len(result)}")
            return result

        width = 32
        lines = []
        lines.append(Visuals.frame_top_left(width))
        lines.append(Visuals.frame_line_left("🏆 ТОП-10 КРИПТОВАЛЮТ (USDT)", width, "center"))
        lines.append(Visuals.frame_separator_left(width))

        for idx, coin in enumerate(top_10, 1):
            symbol = coin.get('symbol', '').upper()
            name = coin.get('name', 'Unknown')
            price = coin.get('current_price', 0)
            change = coin.get('price_change_percentage_24h', 0)
            emoji = "📈" if change >= 0 else "📉"

            lines.append(Visuals.frame_line_left(f"{idx}. {name} ({symbol})", width))
            lines.append(Visuals.frame_line_left(f"💵 ${price:,.4f}", width))
            lines.append(Visuals.frame_line_left(f"{emoji} {change:+.2f}%", width))

            if idx < len(top_10):
                lines.append(Visuals.frame_separator_left(width))

        lines.append(Visuals.frame_bottom_left(width))
        result = f"<pre>{chr(10).join(lines)}</pre>"
        logger.info(f"[CRYPTO_SERVICE] CoinGecko result length: {len(result)}")
        return result

    async def get_price_message(self, symbol: str) -> str:
        """Получить курс валюты в USDT."""
        symbol_lower = symbol.lower()
        coin_id = self.SYMBOL_MAP.get(symbol_lower, symbol_lower)

        # Try to get price with fallback sources
        price_usdt = await self._fetch_price_with_fallback(coin_id, symbol, "usdt")

        if price_usdt is not None and price_usdt > 0:
            # Attempt to get additional data (change, market cap) from USD pair
            change = 0.0
            market_cap = 0
            try:
                # We try to get change and market cap from CoinGecko USD pair
                data_usd = await self.api.get_coingecko_price(coin_id, "usd")
                if data_usd and coin_id in data_usd:
                    coin_data = data_usd[coin_id]
                    usd_24h_change = coin_data.get("usd_24h_change")
                    if usd_24h_change is not None:
                        change = float(usd_24h_change)
                    market_cap = coin_data.get("usd_market_cap", 0) or 0
            except Exception:
                # If we can't get additional data, that's OK - we still have the price
                pass

            base = Visuals.crypto_price_card(
                symbol=symbol,
                usd=price_usdt,  # USDT ≈ USD
                rub=0,  # Not showing RUB as requested
                change=change,
                market_cap=market_cap,
                market_cap_rub=0
            )

            # Remove RUB line from output since we don't want to show it
            base = self._remove_rub_line(base)
            return await self._attach_arbitrage(base, symbol)

        # Если все источники не сработали
        return f"{Visuals.cross()} Не удалось найти курс для {symbol.upper()} в USDT. Пожалуйста, попробуйте позже или используйте другой символ (например, BTC, ETH, TON)."

    def _remove_rub_line(self, text: str) -> str:
        """Remove RUB line from Visuals output to show USDT-only."""
        # Split into lines and filter out the RUB line
        lines = text.split('\n')
        filtered_lines = []
        for line in lines:
            # Skip lines that contain RUB/ruble indicators
            if '₽' in line or 'rub' in line.lower() or '🇷🇺' in line:
                continue
            filtered_lines.append(line)
        return '\n'.join(filtered_lines)

    async def _attach_arbitrage(self, base_message: str, symbol: str) -> str:
        """Добавить информацию об арбитражe если доступно и просто."""
        # Only show arbitrage for a few major coins to keep it simple
        supported = {"TON", "BTC", "ETH", "SOL"}
        sym = symbol.upper()

        if sym not in supported:
            return base_message

        prices = await self.api.get_symbol_usd_orderbooks(sym)
        if not prices:
            return base_message

        # Use only the most reliable exchanges for arbitrage
        arb_exchanges = ["Binance", "Bybit", "OKX"]
        valid = {k: v for k, v in prices.items() if k in arb_exchanges}

        if len(valid) < 2:
            return base_message

        best_buy = min(valid.items(), key=lambda x: x[1]["ask"])
        best_sell = max(valid.items(), key=lambda x: x[1]["bid"])

        buy_ex, buy_data = best_buy
        sell_ex, sell_data = best_sell

        buy_price = buy_data["ask"]
        sell_price = sell_data["bid"]

        if buy_price <= 0 or sell_price <= 0:
            return base_message

        profit = ((sell_price - buy_price) / buy_price) * 100
        profit_emoji = "🟢" if profit > 0 else "🔴"

        w = Visuals.FRAME_W_PROFILE
        lines = [
            Visuals.frame_top_left(w),
            Visuals.frame_line_left(f"💱 {sym}/USDT Арбитраж", w, "center"),
            Visuals.frame_separator_left(w),
            Visuals.frame_line_left(f"📉 Купить: {buy_ex}", w),
            Visuals.frame_line_left(f"   {buy_price:.4f} $", w),
            Visuals.frame_line_left(f"📈 Продать: {sell_ex}", w),
            Visuals.frame_line_left(f"   {sell_price:.4f} $", w),
            Visuals.frame_separator_left(w),
            Visuals.frame_line_left(f"{profit_emoji} Спред: {profit:+.2f}%", w),
            Visuals.frame_bottom_left(w),
        ]

        arb_block = "<pre>\n" + "\n".join(lines) + "\n</pre>"
        return base_message + "\n" + arb_block

    async def get_calculator_message(self, symbol: str, amount: float) -> str:
        """Рассчитать стоимость монет в USDT."""
        symbol_lower = symbol.lower()
        coin_id = self.SYMBOL_MAP.get(symbol_lower, symbol_lower)

        # Try to get price with fallback sources
        price_usdt = await self._fetch_price_with_fallback(coin_id, symbol, "usdt")

        if price_usdt == 0:
            return f"{Visuals.cross()} Не удалось найти курс для {symbol.upper()} в USDT"

        total_usdt = price_usdt * amount

        width = 30
        lines = [
            Visuals.frame_top_left(width),
            Visuals.frame_line_left(f"🧮 {symbol.upper()} Calculator", width, "center"),
            Visuals.frame_separator_left(width),
            Visuals.frame_line_left(f"Кол-во: {amount}", width),
            Visuals.frame_line_left(f"Курс: {price_usdt:,.4f} USDT", width),
            Visuals.frame_separator_left(width),
            Visuals.frame_line_left(f"Итого:", width),
            Visuals.frame_line_left(f"💰 {total_usdt:,.4f} USDT", width),
            Visuals.frame_bottom_left(width)
        ]

        return "<pre>\n" + "\n".join(lines) + "\n</pre>"

    # Legacy method compatibility
    async def format_price_message(self, crypto: str = "TON") -> str:
        return await self.get_price_message(crypto)