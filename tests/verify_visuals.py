import sys
import os
import random
import asyncio

# Add project root to path
sys.path.append(os.getcwd())

from src.core.visuals import Visuals, CompactTheme

async def test_trade(f):
    f.write("--- TRADING VISUALS ---\n")
    frames = Visuals.get_trade_animation(username="Tester")
    f.write(f"Generated {len(frames)} frames.\n")
    for i, frame in enumerate(frames):
        f.write(f"Frame {i}:\n")
        f.write(frame + "\n")
        f.write("-" * 20 + "\n")
    
    res = Visuals.get_trade_result(
        direction="long",
        is_win=True,
        profit=100,
        remaining_coins=5000,
        username="Tester",
        bet=50,
        fee=5
    )
    f.write("Result WIN:\n")
    f.write(res + "\n")
    
    res_loss = Visuals.get_trade_result(
        direction="short",
        is_win=False,
        profit=-50,
        remaining_coins=4950,
        username="Tester",
        bet=50,
        fee=5
    )
    f.write("Result LOSS:\n")
    f.write(res_loss + "\n")

async def test_slots(f):
    f.write("\n--- SLOTS VISUALS ---\n")
    # Mock symbols
    symbols = ["🍒", "🍒", "🍒"]
    frames = Visuals.get_slots_animation(
        username="Tester",
        balance=5000,
        bet=100,
        fee=10,
        final_symbols=symbols,
        spins=3
    )
    f.write(f"Generated {len(frames)} frames.\n")
    for i, frame in enumerate(frames):
        f.write(f"Frame {i}:\n")
        f.write(frame + "\n")
        f.write("-" * 20 + "\n")
        
    res = Visuals.get_slots_result(
        result_symbols=symbols,
        is_win=True,
        prize=500,
        username="Tester",
        remaining_coins=5500,
        bet=100,
        fee=10
    )
    f.write("Result WIN:\n")
    f.write(res + "\n")

async def main():
    with open("visuals_output.txt", "w", encoding="utf-8") as f:
        await test_trade(f)
        await test_slots(f)

if __name__ == "__main__":
    asyncio.run(main())
