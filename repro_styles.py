
import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from src.core.visuals import Visuals

async def main():
    print("--- Bitcoin Style (Left Only) ---")
    print(Visuals.crypto_price_card(
        symbol="BTC",
        usd=95000.0,
        rub=9000000.0,
        change=5.0,
        market_cap=1000000000.0,
        market_cap_rub=90000000000.0
    ))
    
    print("\n--- Top 10 Mock (Left Only) ---")
    width = 34
    lines = []
    lines.append(Visuals.frame_top_left(width))
    lines.append(Visuals.frame_line_left("🏆 ТОП-10 КРИПТОВАЛЮТ", width, "center"))
    lines.append(Visuals.frame_separator_left(width))
    lines.append(Visuals.frame_line_left("1. Bitcoin (BTC)", width))
    lines.append(Visuals.frame_line_left("$95,000 | ₽9,000,000", width))
    lines.append(Visuals.frame_bottom_left(width))
    print("\n".join(lines))

if __name__ == "__main__":
    asyncio.run(main())
