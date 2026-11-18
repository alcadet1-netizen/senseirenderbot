import asyncio

import pytest

from src.main import run_with_widget_startup


@pytest.mark.asyncio
async def test_polling_starts_without_waiting_for_widget_connection():
    polling_started = asyncio.Event()
    release_widgets = asyncio.Event()
    stop_polling = asyncio.Event()
    async def polling():
        polling_started.set()
        await stop_polling.wait()
    async def widgets():
        await release_widgets.wait()
    task = asyncio.create_task(run_with_widget_startup(polling, widgets))
    try:
        await asyncio.wait_for(polling_started.wait(), 1)
        assert not release_widgets.is_set()
        release_widgets.set()
        stop_polling.set()
        await asyncio.wait_for(task, 1)
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_failed_widget_startup_cancels_polling():
    stopped = asyncio.Event()
    async def polling():
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()
    async def widgets():
        await asyncio.sleep(0)
        raise RuntimeError('widget startup failed')
    with pytest.raises(RuntimeError, match='widget startup failed'):
        await run_with_widget_startup(polling, widgets)
    assert stopped.is_set()


@pytest.mark.asyncio
async def test_stopped_polling_cancels_widget_startup():
    stopped = asyncio.Event()
    async def polling():
        await asyncio.sleep(0)
    async def widgets():
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()
    await run_with_widget_startup(polling, widgets)
    assert stopped.is_set()
