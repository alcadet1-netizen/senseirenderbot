"""Persist campaign input before aiogram advances the Telegram polling offset."""
import asyncio
import logging

logger = logging.getLogger(__name__)


def install_campaign_admission(dispatcher, service):
    listen = dispatcher._listen_updates

    async def durable_updates(*args, **kwargs):
        async for update in listen(*args, **kwargs):
            while True:
                try:
                    await service.capture(update)
                    break
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception('Mongo campaign admission failed; Telegram offset held; retrying')
                    await asyncio.sleep(1)
            yield update
            # Only now does the underlying generator resume and advance offset.
    dispatcher._listen_updates = durable_updates
