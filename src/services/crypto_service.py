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
            if key in self._cache:
                del self._cache[key]


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
        """Получить курс валюты в USDT с улучшенной надёжностью."""
        symbol_lower = symbol.lower()
        coin_id = self.SYMBOL_MAP.get(symbol_lower, symbol_lower)

        # Попробуем получить цену в USDT (универсальная и стабильная валюта)
        price_usdt = await self._get_price_with_fallbacks(coin_id, symbol, "usdt")

        if price_usdt is None or price_usdt == 0:
            return f"{Visuals.cross()} Не удалось найти курс для {symbol.upper()}. Пожалуйста, попробуйте позже или используйте другой символ (например, BTC, ETH, TON)."

        # Для обратной совместимости и дополнительной информации получим цену в USD
        # USDT цена почти идентична USD цене (1 USDT ≈ 1 USD)
        price_usd = price_usdt

        # Попробуем получить точную цену в USD для более точных данных об изменении и рыночной капитализации
        price_usd_exact = await self._get_price_with_fallbacks(coin_id, symbol, "usd")
        if price_usd_exact is not None and price_usd_exact > 0:
            price_usd = price_usd_exact

        # Расчёт изменения цены за 24h (попытка получить с основного источника)
        change = 0.0
        try:
            # Попробуем получить изменение с CoinGecko как основной источник
            data = await self.api.get_coingecko_price(coin_id, "usd")
            if data and coin_id in data:
                change = data[coin_id].get("usd_24h_change", 0.0)
                if change is None:
                    change = 0.0
        except Exception:
            pass  # Если не удалось получить изменение, оставляем 0

        # Расчёт рыночной капитализации (если доступна)
        market_cap = 0
        try:
            data = await self.api.get_coingecko_price(coin_id, "usd")
            if data and coin_id in data:
                market_cap = data[coin_id].get("usd_market_cap", 0)
                if market_cap is None:
                    market_cap = 0
        except Exception:
            pass  # Если не удалось получить рыночную капитализацию, оставляем 0

        # Расчёт эквивалента в рублях для справки (опционально)
        price_rub = 0
        try:
            # Получить курс USDT/RUB
            usdt_rub_data = await self.api.get_coingecko_price("tether", "rub")
            if usdt_rub_data and "tether" in usdt_rub_data:
                usdt_rub_rate = usdt_rub_data["tether"].get("rub", 0)
                if usdt_rub_rate > 0:
                    price_rub = price_usdt * usdt_rub_rate
            else:
                # Fallback к историческому курсу
                price_rub = price_usdt * 90.0
        except Exception:
            # Если все попытки не удались, используем fallback курс
            price_rub = price_usdt * 90.0

        base = Visuals.crypto_price_card(
            symbol=symbol,
            usd=price_usd,
            rub=price_rub,
            change=change,
            market_cap=market_cap,
            market_cap_rub=market_cap * (price_rub / price_usd) if price_usd > 0 else 0
        )

        return await self._attach_arbitrage(base, symbol)

    async def get_calculator_message(self, symbol: str, amount: float) -> str:
        """Рассчитать стоимость монет в USDT с улучшенной надёжностью."""
        logging.info(f"[CRYPTO] get_calculator_message called with symbol={symbol}, amount={amount}")
        symbol_lower = symbol.lower()
        coin_id = self.SYMBOL_MAP.get(symbol_lower, symbol_lower)
        logging.info(f"[CRYPTO] symbol_lower={symbol_lower}, coin_id={coin_id}")

        # Попробовать получить цену с множественными источниками и кэшированием
        price_usdt = await self._get_price_with_fallbacks(coin_id, symbol, "usdt")

        if price_usdt is None or price_usdt == 0:
            msg = f"❌ Не удалось найти курс для {symbol.upper()}. Пожалуйста, попробуйте позже или используйте другой символ (например, BTC, ETH, TON)."
            logging.info(f"[CRYPTO] All price sources failed for {symbol}. Returning error message: {msg}")
            return msg

        total_usdt = price_usdt * amount
        logging.info(f"[CRYPTO] total_usdt: {total_usdt}")

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

        result = "<pre>\n" + "\n".join(lines) + "\n</pre>"
        logging.info(f"[CRYPTO] Returning result: {result}")
        return result

    async def _get_price_with_fallbacks(self, coin_id: str, symbol: str, vs_currency: str = "rub") -> Optional[float]:
        """
        Получить цену с множественными источниками с резервными вариантами и повторными попытками.
        Возвращает цену в указанной валюте или None если все источники недоступны.
        """
        # Попробовать получить из кэша сначала (если есть недавние данные)
        cache_key = f"price:{coin_id}:{vs_currency}"
        cached_price = await self.cache.get(cache_key)
        if cached_price is not None and cached_price > 0:
            logging.info(f"[CRYPTO] Using cached price for {coin_id}: {cached_price}")
            return cached_price

        # Список источников для попытки в порядке приоритета
        sources = [
            ("CoinGecko", self._try_coingecko),
            ("Binance", self._try_binance),
            ("Bybit", self._try_bybit),
            ("OKX", self._try_okx),
            ("MEXC", self._try_mexc),
            ("Gate.io", self._try_gateio),
            ("KuCoin", self._try_kucoin),
            ("CoinMarketCap", self._try_coinmarketcap),
        ]

        # Попробовать каждый источник с повторными попытками
        for source_name, source_func in sources:
            logging.info(f"[CRYPTO] Trying {source_name} for {coin_id}")

            # Повторные попытки с экспоненциальной задержкой
            for attempt in range(3):
                try:
                    price = await source_func(coin_id, vs_currency)
                    if price is not None and price > 0:
                        # Сохранить в кэш на 5 минут
                        await self.cache.set(cache_key, price, ttl=300)
                        logging.info(f"[CRYPTO] {source_name} returned price for {coin_id}: {price}")
                        return price
                except Exception as e:
                    logging.warning(f"[CRYPTO] {source_name} attempt {attempt + 1} failed for {coin_id}: {e}")

                # Если это не последняя попытка, подождать перед следующей
                if attempt < 2:  # Не ждать после последней попытки
                    await asyncio.sleep(2 ** attempt)  # 1s, 2s, 4s

            logging.info(f"[CRYPTO] {source_name} failed after 3 attempts for {coin_id}")

        logging.error(f"[CRYPTO] All price sources failed for {coin_id}")
        return None

    async def _try_coingecko(self, coin_id: str, vs_currency: str) -> Optional[float]:
        """Получить цену с CoinGecko."""
        data = await self.api.get_coingecko_price(coin_id, vs_currency)
        if data and coin_id in data:
            price = data[coin_id].get(vs_currency)
            if price is not None and price > 0:
                return float(price)
        return None

    async def _try_binance(self, symbol: str, vs_currency: str) -> Optional[float]:
        """Получить цену с Binance (только для пар с USDT, затем конвертировать)."""
        if vs_currency != "rub":
            # Для простоты, если нужен не RUB, возвращаем None и позволяем другим источникам справиться
            return None

        # Получить цену в USDT
        ticker_data = await self.api.get_binance_ticker(symbol)
        if ticker_data:
            price_usdt = float(ticker_data.get("lastPrice", 0))
            if price_usdt > 0:
                # Конвертировать USDT в RUB через курс USDT/RUB
                try:
                    # Прямой вызов API без использования fallback механизма чтобы избежать рекурсии
                    usdt_rub_data = await self.api.get_coingecko_price("tether", "rub")
                    if usdt_rub_data and "tether" in usdt_rub_data:
                        usdt_rub_rate = usdt_rub_data["tether"].get("rub", 0)
                        if usdt_rub_rate > 0:
                            return price_usdt * usdt_rub_rate
                except Exception:
                    pass

                # Fallback: использовать приблизительный курс 90
                return price_usdt * 90.0
        return None

    async def _try_bybit(self, symbol: str, vs_currency: str) -> Optional[float]:
        """Получить цену с Bybit."""
        if vs_currency != "rub":
            return None

        ticker_data = await self.api.get_bybit_ticker(symbol)
        if ticker_data:
            try:
                item = ticker_data.get("result", {}).get("list", [{}])[0]
                price_usdt = float(item.get("lastPrice", 0))
                if price_usdt > 0:
                    # Конвертировать через USDT/RUB
                    try:
                        # Прямой вызов API без использования fallback механизма чтобы избежать рекурсии
                        usdt_rub_data = await self.api.get_coingecko_price("tether", "rub")
                        if usdt_rub_data and "tether" in usdt_rub_data:
                            usdt_rub_rate = usdt_rub_data["tether"].get("rub", 0)
                            if usdt_rub_rate > 0:
                                return price_usdt * usdt_rub_rate
                    except Exception:
                        pass
                    return price_usdt * 90.0  # Fallback
            except Exception:
                pass
        return None

    async def _try_okx(self, symbol: str, vs_currency: str) -> Optional[float]:
        """Получить цену с OKX."""
        if vs_currency != "rub":
            return None

        ticker_data = await self.api.get_okx_ticker(symbol)
        if ticker_data:
            try:
                item = ticker_data.get("data", [{}])[0]
                price_usdt = float(item.get("last", 0))
                if price_usdt > 0:
                    # Конвертировать через USDT/RUB
                    try:
                        # Прямой вызов API без использования fallback механизма чтобы избежать рекурсии
                        usdt_rub_data = await self.api.get_coingecko_price("tether", "rub")
                        if usdt_rub_data and "tether" in usdt_rub_data:
                            usdt_rub_rate = usdt_rub_data["tether"].get("rub", 0)
                            if usdt_rub_rate > 0:
                                return price_usdt * usdt_rub_rate
                    except Exception:
                        pass
                    return price_usdt * 90.0  # Fallback
            except Exception:
                pass
        return None

    async def _try_mexc(self, symbol: str, vs_currency: str) -> Optional[float]:
        """Получить цену с MEXC."""
        if vs_currency != "rub":
            return None

        ticker_data = await self.api.get_mexc_ticker(symbol)
        if ticker_data:
            try:
                price_usdt = float(ticker_data.get("lastPrice", 0))
                if price_usdt > 0:
                    # Конвертировать через USDT/RUB
                    try:
                        # Прямой вызов API без использования fallback механизма чтобы избежать рекурсии
                        usdt_rub_data = await self.api.get_coingecko_price("tether", "rub")
                        if usdt_rub_data and "tether" in usdt_rub_data:
                            usdt_rub_rate = usdt_rub_data["tether"].get("rub", 0)
                            if usdt_rub_rate > 0:
                                return price_usdt * usdt_rub_rate
                    except Exception:
                        pass
                    return price_usdt * 90.0  # Fallback
            except Exception:
                pass
        return None

    async def _try_gateio(self, symbol: str, vs_currency: str) -> Optional[float]:
        """Получить цену с Gate.io."""
        if vs_currency != "rub":
            return None

        ticker_data = await self.api.get_gateio_ticker(symbol)
        if ticker_data and isinstance(ticker_data, list) and len(ticker_data) > 0:
            try:
                item = ticker_data[0]
                price_usdt = float(item.get("last", 0))
                if price_usdt > 0:
                    # Конвертировать через USDT/RUB
                    try:
                        # Прямой вызов API без использования fallback механизма чтобы избежать рекурсии
                        usdt_rub_data = await self.api.get_coingecko_price("tether", "rub")
                        if usdt_rub_data and "tether" in usdt_rub_data:
                            usdt_rub_rate = usdt_rub_data["tether"].get("rub", 0)
                            if usdt_rub_rate > 0:
                                return price_usdt * usdt_rub_rate
                    except Exception:
                        pass
                    return price_usdt * 90.0  # Fallback
            except Exception:
                pass
        return None

    async def _try_kucoin(self, symbol: str, vs_currency: str) -> Optional[float]:
        """Получить цену с KuCoin."""
        if vs_currency != "rub":
            return None

        ticker_data = await self.api.get_kucoin_ticker(symbol)
        if ticker_data:
            try:
                data = ticker_data.get("data", {})
                price_usdt = float(data.get("last", 0))
                if price_usdt > 0:
                    # Конвертировать через USDT/RUB
                    try:
                        # Прямой вызов API без использования fallback механизма чтобы избежать рекурсии
                        usdt_rub_data = await self.api.get_coingecko_price("tether", "rub")
                        if usdt_rub_data and "tether" in usdt_rub_data:
                            usdt_rub_rate = usdt_rub_data["tether"].get("rub", 0)
                            if usdt_rub_rate > 0:
                                return price_usdt * usdt_rub_rate
                    except Exception:
                        pass
                    return price_usdt * 90.0  # Fallback
            except Exception:
                pass
        return None

    async def _try_coinmarketcap(self, symbol: str, vs_currency: str) -> Optional[float]:
        """Получить цену с CoinMarketCap."""
        if vs_currency != "rub":
            return None

        quote_data = await self.api.get_quote(symbol)
        if quote_data:
            try:
                price_usd = float(quote_data.get("quote", {}).get("USD", {}).get("price", 0))
                if price_usd > 0:
                    # Конвертировать USD в RUB
                    try:
                        usd_rub_data = await self.api.get_coingecko_price("tether", "rub")
                        if usd_rub_data and "tether" in usd_rub_data:
                            usdt_rub_rate = usd_rub_data["tether"].get("rub", 0)  # USDT ~ USD
                            if usdt_rub_rate > 0:
                                return price_usd * usdt_rub_rate
                    except Exception:
                        pass
                    return price_usd * 90.0  # Fallback
            except Exception:
                pass
        return None

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