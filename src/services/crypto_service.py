"""
💰 Сервис криптовалют - упрощенная версия с фокусом на USDT.
"""

import asyncio
import re
from typing import Optional

from src.core.config import Settings
from src.core.visuals import Visuals
from src.api.crypto_api import CryptoAPI


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

    async def get_top_10_message(self) -> str:
        """Получить ТОП-10 криптовалют в USDT."""
        # Получаем топ-10 в USDT
        top_10 = await self.api.get_coingecko_top_10("usdt")

        if not top_10:
            # Fallback to Binance for popular coins if CoinGecko fails
            popular_coins = ["BTC", "ETH", "USDT", "BNB", "SOL", "XRP", "ADA", "DOGE", "TRX", "DOT"]
            lines = []
            width = 32
            lines.append(Visuals.frame_top_left(width))
            lines.append(Visuals.frame_line_left("🏆 ТОП-10 КРИПТОВАЛЮТ (USDT)", width, "center"))
            lines.append(Visuals.frame_separator_left(width))

            for i, symbol in enumerate(popular_coins, 1):
                ticker = await self.api.get_binance_ticker(symbol)
                if ticker:
                    price = float(ticker.get("lastPrice", 0))
                    change = float(ticker.get("priceChangePercent", 0))
                    emoji = "📈" if change >= 0 else "📉"
                    lines.append(Visuals.frame_line_left(f"{i}. {symbol}", width))
                    lines.append(Visuals.frame_line_left(f"💵 ${price:,.4f}", width))
                    lines.append(Visuals.frame_line_left(f"{emoji} {change:+.2f}%", width))
                    if i < len(popular_coins):
                        lines.append(Visuals.frame_separator_left(width))

            lines.append(Visuals.frame_bottom_left(width))
            return f"<pre>{chr(10).join(lines)}</pre>"

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
        return f"<pre>{chr(10).join(lines)}</pre>"

    async def get_price_message(self, symbol: str) -> str:
        """Получить курс валюты в USDT."""
        symbol_lower = symbol.lower()
        coin_id = self.SYMBOL_MAP.get(symbol_lower, symbol_lower)

        # Пробуем CoinGecko для цены в USDT
        data = await self.api.get_coingecko_price(coin_id, "usdt")

        if data and coin_id in data:
            price_usdt = data[coin_id].get("usdt")
            if price_usdt is not None and price_usdt > 0:
                # Attempt to get additional data (change, market cap) from USD pair
                change = 0.0
                market_cap = 0
                try:
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

        # Если CoinGecko не сработал, пробуем Binance
        binance_data = await self.api.get_binance_ticker(symbol)
        if binance_data:
            price_usdt = float(binance_data.get("lastPrice", 0))
            if price_usdt > 0:
                change = float(binance_data.get("priceChangePercent", 0))

                base = Visuals.crypto_price_card(
                    symbol=symbol,
                    usd=price_usdt,  # USDT ≈ USD
                    rub=0,  # Not showing RUB as requested
                    change=change,
                    market_cap=0,  # Binance ticker doesn't provide market cap simply
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

        # Пробуем CoinGecko для цены в USDT
        data = await self.api.get_coingecko_price(coin_id, "usdt")

        price_usdt = 0
        if data and coin_id in data:
            price_usdt = data[coin_id].get("usdt", 0)

        # Если CoinGecko не сработал, пробуем Binance
        if price_usdt == 0:
            binance_data = await self.api.get_binance_ticker(symbol)
            if binance_data:
                price_usdt = float(binance_data.get("lastPrice", 0))

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