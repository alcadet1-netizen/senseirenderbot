"""Persist campaign input before aiogram advances the Telegram polling offset."""
import asyncio
import logging

logger = logging.getLogger(__name__)


def install_campaign_admission(dispatcher, service, join_watch=None, *, game_chat_id=None):
    listen = dispatcher._listen_updates

    async def durable_updates(*args, **kwargs):
        async for update in listen(*args, **kwargs):
            while True:
                try:
                    # Only the permitted discussion may admit campaign input.
                    # Source-channel posts remain available when it is linked.
                    if game_chat_id is None or getattr(service, 'discussion_id', None) == game_chat_id:
                        await service.capture(update)
                    if join_watch is not None:
                        request = update.chat_join_request
                        if not request or game_chat_id is None or request.chat.id == game_chat_id:
                            await join_watch.capture(update)
                    break
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception('Mongo update admission failed; Telegram offset held; retrying')
                    await asyncio.sleep(1)
            yield update
            # Only now does the underlying generator resume and advance offset.
    dispatcher._listen_updates = durable_updates
