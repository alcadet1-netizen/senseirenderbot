"""Deliver a completed upgrade receipt. Never invokes the economy service."""

import asyncio
import logging
import time

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import BufferedInputFile, FSInputFile, Message

from src.widgets.katana import KatanaUpgrade, to_upgrade_gif, to_upgrade_png
from src.widgets.limits import RENDER_SLOTS

logger = logging.getLogger(__name__)


async def render_receipt(renderer, receipt):
    # Bound queue time, not the thread itself: releasing a slot while its thread
    # still renders would defeat the CPU concurrency bound.
    await asyncio.wait_for(RENDER_SLOTS.acquire(), timeout=0.5)
    task = asyncio.create_task(asyncio.to_thread(renderer, receipt))
    # Release on actual completion, including when the request is cancelled.
    task.add_done_callback(lambda _: RENDER_SLOTS.release())
    return await asyncio.shield(task)


async def send_katana_upgrade(
    message: Message, owner: int, name: str, result: dict, *, animate: bool
):
    receipt = KatanaUpgrade.from_result(name, result)
    card = receipt.as_card()
    caption = (
        f"{receipt.name} · {receipt.status}\n"
        f"{receipt.before:.2f} → {receipt.after:.2f} см ({receipt.delta:+.2f} см) · {receipt.cost:,.0f} монет"
    )
    text_receipt = caption + f"\n{dict(card.rows)['Клинок']} · Ранг {dict(card.rows)['Ранг']}"
    if animate:
        try:
            started = time.monotonic()
            payload = await render_receipt(to_upgrade_gif, receipt)
            logger.info("Katana GIF rendered version=reference-v2 seconds=%.3f bytes=%s", time.monotonic()-started, len(payload))
            await message.answer_animation(
                BufferedInputFile(payload, filename="sensei-katana-upgrade.gif"),
                caption=caption,
                parse_mode=None,
            )
            return
        except (TelegramBadRequest, OSError, ValueError, TimeoutError):
            logger.warning("Katana animation unavailable; falling back to PNG", exc_info=True)
    try:
        payload = await render_receipt(to_upgrade_png, receipt)
        await message.answer_photo(
            BufferedInputFile(payload, filename="sensei-katana-upgrade.png"),
            caption=caption,
            parse_mode=None,
        )
    except (TelegramBadRequest, OSError, ValueError, TimeoutError):
        logger.warning("Katana image unavailable; falling back to text", exc_info=True)
        await message.answer(text_receipt, parse_mode=None)


async def send_current_katana(message: Message, length: float):
    from src.widgets.katana_models import model_caption, model_index, model_path
    caption = model_caption(length)
    try:
        await message.answer_photo(
            FSInputFile(model_path(model_index(length))),
            caption=caption, parse_mode=None,
        )
    except TelegramBadRequest:
        await message.answer(caption, parse_mode=None)
