"""
💰 Сервис криптовалют.
"""

import asyncio
import time
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from src.core.config import Settings
from src.core.visuals import Visuals
from src.api.crypto_api import CryptoAPI
import logging

logger = logging.getLogger(__name__)


class SimpleCache:
    """Simple in-memory cache with TTL."""
    def __init__(self, default_ttl: int = 300):
        self._cache: Dict[str, tuple[Any, float]] = {}  # key -> (value, expiry_timestamp)
        self._default_ttl = default_ttl
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            now = time.time()
            if key in self._cache:
                value, expiry = self._cache[key]
                if now < expiry:
                    return value
                else:
                    del self._cache[key]
            return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None):
        ttl = ttl or self._default_ttl
        expiry = time.time() + ttl
        async with self._lock:
            self._cache[key] = (value, expiry)

    async def delete(self, key: str):
        async with self._lock:
            self._cache.pop(key, None)


class CryptoService:
    """Сервис для получения курсов криптовалют."""

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
        self.cache = SimpleCache(default_ttl=300)  # 5 minutes
        self.api = CryptoAPI(settings.ton_api_key)

    async def get_top_10_message(self) -> str:
        """Получить ТОП-10 криптовалют + избранное (TON, SUI и др)."""
        cache_key = "crypto:top10_framed_v2"
        cached = await self.cache.get(cache_key)
        if cached:
            return cached

        # Получаем данные параллельно
        # Топ-10
        top_10_usd, top_10_rub = await asyncio.gather(
            self.api.get_coingecko_top_10("usd"),
            self.api.get_coingecko_top_10("rub")
        )

        if not top_10_usd:
            top_10_usd = []

        # Мапа для быстрого поиска цены в рублях для топ-10
        rub_map = {c['id']: c for c in (top_10_rub or [])}

        # Список избранного, который нужно отобразить дополнительно
        # TON, BTC, USDT, DOGE, SOL, SUI, BNB
        favorites_ids = ["toncoin", "bitcoin", "tether", "dogecoin", "solana", "sui", "binancecoin"]

        # Получаем цены для избранного (на случай если кого-то нет в топ-10)
        favorites_data_usd = await self.api.get_coingecko_price(",".join(favorites_ids), "usd")
        favorites_data_rub = await self.api.get_coingecko_price(",".join(favorites_ids), "rub")

        width = 34
        lines = []

        # Заголовок
        lines.append(Visuals.frame_top_left(width))
        lines.append(Visuals.frame_line_left("🏆 ТОП-10 КРИПТОВАЛЮТ", width, "center"))
        lines.append(Visuals.frame_separator_left(width))

        # Множество ID, которые уже выведены (чтобы не дублировать в избранном)
        displayed_ids = set()

        # Список монет Топ-10
        for idx, coin_usd in enumerate(top_10_usd, 1):
            coin_id = coin_usd.get('id')
            displayed_ids.add(coin_id)

            coin_rub = rub_map.get(coin_id, {})

            name = coin_usd.get('name', 'Unknown')
            symbol = coin_usd.get('symbol', '').upper()
            price_usd = coin_usd.get('current_price', 0)
            change = coin_usd.get('price_change_percentage_24h', 0)
            price_rub = coin_rub.get('current_price', 0)

            emoji = "📈" if change >= 0 else "📉"

            # Название
            lines.append(Visuals.frame_line_left(f"{idx}. {name} ({symbol})", width))

            # Цены (форматирование)
            usd_str = f"${price_usd:,.2f}" if price_usd < 1000 else f"${price_usd:,.0f}"
            rub_str = f"₽{price_rub:,.0f}"

            lines.append(Visuals.frame_line_left(f"{usd_str} | {rub_str}", width))
            lines.append(Visuals.frame_line_left(f"{emoji} {change:+.2f}%", width))

            if idx < len(top_10_usd):
                lines.append(Visuals.frame_separator_left(width))

        # Секция избранного (только то, что не попало в топ-10)
        missing_favorites = [fid for fid in favorites_ids if fid not in displayed_ids]

        if missing_favorites:
            lines.append(Visuals.frame_separator_left(width))
            lines.append(Visuals.frame_line_left("💎 ИЗБРАННОЕ", width, "center"))
            lines.append(Visuals.frame_separator_left(width))

            # Маппинги
            name_map = {
                "toncoin": "TON Coin",
                "bitcoin": "Bitcoin",
                "tether": "Tether",
                "dogecoin": "Dogecoin",
                "solana": "Solana",
                "sui": "Sui",
                "binancecoin": "BNB"
            }
            symbol_map = {
                "toncoin": "TON",
                "bitcoin": "BTC",
                "tether": "USDT",
                "dogecoin": "DOGE",
                "solana": "SOL",
                "sui": "SUI",
                "binancecoin": "BNB"
            }

            for i, coin_id in enumerate(missing_favorites):
                usd_data = favorites_data_usd.get(coin_id, {}) if favorites_data_usd else {}
                rub_data = favorites_data_rub.get(coin_id, {}) if favorites_data_rub else {}

                price_usd = usd_data.get("usd", 0)
                price_rub = rub_data.get("rub", 0)
                change = usd_data.get("usd_24h_change", 0)

                # Если данных нет (например TON часто отваливается в CoinGecko), пробуем Binance
                if price_usd == 0:
                    symbol = symbol_map.get(coin_id, "").upper()
                    if symbol:
                        binance_data = await self.api.get_binance_ticker(symbol)
                        if binance_data:
                            price_usd = float(binance_data.get("lastPrice", 0))
                            change = float(binance_data.get("priceChangePercent", 0))
                            # Приближенно считаем рубль через USDT (если есть в кеше или по курсу 90)
                            # Лучше взять курс USDT из топ-10 если есть
                            usdt_rub = 90.0
                            if rub_map and "tether" in rub_map:
                                usdt_rub = rub_map["tether"].get("current_price", 90.0)
                            price_rub = price_usd * usdt_rub

                if price_usd == 0:
                    continue

                name = name_map.get(coin_id, coin_id.capitalize())
                symbol = symbol_map.get(coin_id, "").upper()

                emoji = "🚀" if change >= 0 else "🔻"

                lines.append(Visuals.frame_line_left(f"{name} ({symbol})", width))
                lines.append(Visuals.frame_line_left(f"💵 {price_usd:,.2f} $", width))
                lines.append(Visuals.frame_line_left(f"💴 {price_rub:,.2f}  ₽", width))
                lines.append(Visuals.frame_line_left(f"{emoji} 24h: {change:+.2f}%", width))

                if i < len(missing_favorites) - 1:
                    lines.append(Visuals.frame_separator_left(width))

        lines.append(Visuals.frame_bottom_left(width))

        result = f"<pre>{chr(10).join(lines)}</pre>"
        await self.cache.set(cache_key, result, ttl=300)
        return result

    async def get_price_message(self, symbol: str) -> str:
        """Получить курс валюты в RUB и USDT."""
        symbol_lower = symbol.lower()
        coin_id = self.SYMBOL_MAP.get(symbol_lower, symbol_lower)

        # Пробуем CoinGecko
        data = await self.api.get_coingecko_price(coin_id, "usd,rub")

        if not data or coin_id not in data:
            # Если не нашли в CoinGecko, пробуем Binance (только USDT)
            binance_data = await self.api.get_binance_ticker(symbol)
            if binance_data:
                price = float(binance_data.get("lastPrice", 0))
                change = float(binance_data.get("priceChangePercent", 0))

                # Пытаемся получить курс USDT/RUB для конвертации
                rub_rate = 0
                try:
                    usdt_data = await self.api.get_coingecko_price("tether", "rub")
                    if usdt_data and "tether" in usdt_data:
                        rub_rate = usdt_data["tether"].get("rub", 0)
                except Exception:
                    pass

                price_rub = price * rub_rate

                base = Visuals.crypto_price_card(
                    symbol=symbol,
                    usd=price,
                    rub=price_rub,
                    change=change,
                    market_cap=None
                )
                return await self._attach_arbitrage(base, symbol)
            return f"{Visuals.cross()} Не удалось найти курс для {symbol.upper()}"

        # CoinGecko результат
        coin = data[coin_id]
        usd = coin.get("usd", 0)
        rub = coin.get("rub", 0)
        change = coin.get("usd_24h_change", 0)
        market_cap = coin.get("usd_market_cap", 0)

        market_cap_rub = market_cap * (rub / usd) if usd > 0 else 0

        base = Visuals.crypto_price_card(
            symbol=symbol,
            usd=usd,
            rub=rub,
            change=change,
            market_cap=market_cap,
            market_cap_rub=market_cap_rub
        )

        return await self._attach_arbitrage(base, symbol)

    async def get_calculator_message(self, symbol: str, amount: float) -> str:
        """Рассчитать стоимость монет в рублях."""
        logging.info(f"[CRYPTO] get_calculator_message called with symbol={symbol}, amount={amount}")
        symbol_lower = symbol.lower()
        coin_id = self.SYMBOL_MAP.get(symbol_lower, symbol_lower)
        logging.info(f"[CRYPTO] symbol_lower={symbol_lower}, coin_id={coin_id}")

        data = await self.api.get_coingecko_price(coin_id, "rub")
        logging.info(f"[CRYPTO] CoinGecko response for {coin_id}: {data}")

        price_rub = 0

        if data and coin_id in data:
            price_rub = data[coin_id].get("rub", 0)
            logging.info(f"[CRYPTO] Found price_rub from CoinGecko: {price_rub}")
        else:
            logging.info(f"[CRYPTO] Not found in CoinGecko, trying Binance for symbol={symbol}")
            # Если не нашли в CoinGecko, пробуем Binance (только USDT)
            binance_data = await self.api.get_binance_ticker(symbol)
            logging.info(f"[CRYPTO] Binance response: {binance_data}")
            if binance_data:
                price_usd = float(binance_data.get("lastPrice", 0))
                logging.info(f"[CRYPTO] Binance price_usd: {price_usd}")

                # Пытаемся получить курс USDT/RUB для конвертации
                rub_rate = 90.0 # Fallback
                try:
                    usdt_data = await self.api.get_coingecko_price("tether", "rub")
                    logging.info(f"[CRYPTO] USDT/RUB data: {usdt_data}")
                    if usdt_data and "tether" in usdt_data:
                        rub_rate = usdt_data["tether"].get("rub", 90.0)
                except Exception as e:
                    logging.error(f"[CRYPTO] Error fetching USDT/RUB: {e}")

                price_rub = price_usd * rub_rate
                logging.info(f"[CRYPTO] Calculated price_rub from Binance: {price_rub}")

        if price_rub == 0:
            msg = f"❌ Не удалось найти курс для {symbol.upper()}"
            logging.info(f"[CRYPTO] Returning error message: {msg}")
            return msg

        total_rub = price_rub * amount
        logging.info(f"[CRYPTO] total_rub: {total_rub}")

        width = 30
        lines = [
            Visuals.frame_top_left(width),
            Visuals.frame_line_left(f"🧮 {symbol.upper()} Calculator", width, "center"),
            Visuals.frame_separator_left(width),
            Visuals.frame_line_left(f"Кол-во: {amount}", width),
            Visuals.frame_line_left(f"Курс: {price_rub:,.2f}  ₽", width),
            Visuals.frame_separator_left(width),
            Visuals.frame_line_left(f"Итого:", width),
            Visuals.frame_line_left(f"💰 {total_rub:,.2f}  ₽", width),
            Visuals.frame_bottom_left(width)
        ]

        result = "<pre>\n" + "\n".join(lines) + "\n</pre>"
        logging.info(f"[CRYPTO] Returning result: {result}")
        return result

    async def _attach_arbitrage(self, base_message: str, symbol: str) -> str:
        supported = {"TON", "BTC", "ETH", "DOGE", "TRX", "SUI", "TRUMP", "SOL", "XRP"}
        sym = symbol.upper()

        if sym not in supported:
            return base_message

        prices = await self.api.get_symbol_usd_orderbooks(sym)
        if not prices:
            return base_message

        arb_exchanges = ["Binance", "Bybit", "OKX", "MEXC", "Gate.io", "KuCoin"]
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

    # Legacy method compatibility (if needed by other parts of the code, though I think I can remove it if I update usage)
    async def format_price_message(self, crypto: str = "TON") -> str:
        return await self.get_price_message(crypto)