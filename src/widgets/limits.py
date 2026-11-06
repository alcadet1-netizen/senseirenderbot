"""One shared bound for CPU-heavy Pillow rendering in bot handlers."""
import asyncio

RENDER_SLOTS = asyncio.Semaphore(2)
