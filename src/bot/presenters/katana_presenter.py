"""Deliver a completed upgrade receipt. Never invokes the economy service."""

import asyncio
import logging

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import BufferedInputFile, Message

from src.widgets.katana import KatanaUpgrade, to_upgrade_gif, to_upgrade_png
from src.widgets.limits import RENDER_SLOTS

logger = logging.getLogger(__name__)


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
            async with RENDER_SLOTS:
                payload = await asyncio.to_thread(to_upgrade_gif, receipt)
            await message.answer_animation(
                BufferedInputFile(payload, filename="sensei-katana-upgrade.gif"),
                caption=caption,
                parse_mode=None,
            )
            return
        except (TelegramBadRequest, OSError, ValueError):
            logger.warning("Katana animation unavailable; falling back to PNG", exc_info=True)
    try:
        async with RENDER_SLOTS:
            payload = await asyncio.to_thread(to_upgrade_png, receipt)
        await message.answer_photo(
            BufferedInputFile(payload, filename="sensei-katana-upgrade.png"),
            caption=caption,
            parse_mode=None,
        )
    except (TelegramBadRequest, OSError, ValueError):
        logger.warning("Katana image unavailable; falling back to text", exc_info=True)
        await message.answer(text_receipt, parse_mode=None)
