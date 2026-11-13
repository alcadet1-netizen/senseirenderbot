"""Restart-safe deadline checks and serialized latest-state card refresh."""
import asyncio
import logging
import time
from contextlib import suppress
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter, TelegramForbiddenError, TelegramNetworkError
from src.bot.presenters.boss_presenter import BossPresenter
from src.services.boss_settlement_service import settle_boss

logger = logging.getLogger(__name__)


async def refresh_boss(bot, container, force=False):
    service = container.boss_service
    async with service._card_lock:
        # Re-read INSIDE the display lock. Do not publish a stale attack snapshot.
        async with service._lock:
            state = await service.get_state()
            if not state:
                return
            due = state.get('deadline') and state['deadline'] <= time.time()
            if state.get('settlement_kind') or (due and not state.get('is_dead') and not state.get('is_expired')):
                state = await settle_boss(container.mongo_client)
        terminal = state.get('is_dead') or state.get('is_expired')
        if not state.get('chat_id') or not state.get('message_id') or state.get('card_missing'):
            return
        if terminal and state.get('card_synced'):
            return
        now = time.monotonic()
        if now < getattr(service, '_card_retry_at', 0):
            return
        if not force and not terminal and now-service._last_card_edit < 1:
            return
        # Keyboard import is deferred to avoid renderer/handler import cycles.
        from src.bot.handlers.boss_commands import get_boss_keyboard
        kwargs = dict(chat_id=state['chat_id'], message_id=state['message_id'],
                      parse_mode='HTML', reply_markup=None if terminal else get_boss_keyboard())
        caption = BossPresenter.render_boss_caption(state)
        identity = (state['start_time'], state['message_id'], caption, bool(terminal))
        if getattr(service, '_last_card_identity', None) == identity:
            return
        try:
            if state.get('has_photo'):
                await bot.edit_message_caption(**kwargs, caption=caption)
            else:
                await bot.edit_message_text(**kwargs, text=caption)
        except TelegramRetryAfter as exc:
            service._card_retry_at = time.monotonic() + max(1, exc.retry_after)
            logger.warning('Boss card rate limited; refresh deferred')
            return
        except TelegramBadRequest as exc:
            message = exc.message.lower()
            if 'message is not modified' not in message:
                if 'message to edit not found' in message:
                    await service.boss_state.update_one(
                        {'_id':'boss_state','start_time':state['start_time']}, {'$set':{'card_missing':True}})
                logger.warning('Boss card edit rejected error_type=%s', type(exc).__name__)
                return
        except (TelegramForbiddenError, TelegramNetworkError):
            logger.warning('Boss card delivery unavailable; no fallback message sent')
            return
        service._last_card_edit = time.monotonic()
        service._last_card_identity = identity
        if terminal:
            await service.boss_state.update_one(
                {'_id':'boss_state','start_time':state['start_time']}, {'$set':{'card_synced':True}})


async def _loop(bot, container):
    while True:
        try:
            await refresh_boss(bot, container)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception('Boss deadline/settlement refresh failed; retained for retry')
        await asyncio.sleep(5)


async def start_boss_monitor(bot, container):
    if getattr(container.boss_service, '_monitor_task', None) is None:
        container.boss_service._monitor_task = asyncio.create_task(_loop(bot, container), name='boss-deadline-monitor')


async def stop_boss_monitor(container):
    service = getattr(container, '_boss_service', None)
    task = getattr(service, '_monitor_task', None)
    if task is not None:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        service._monitor_task = None
