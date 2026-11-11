import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from aiogram import Dispatcher
from aiogram.types import Update

from src.bot.campaign_polling import install_campaign_admission


@pytest.mark.asyncio
async def test_actual_aiogram_offset_does_not_advance_until_mongo_commit():
    events=[Update(update_id=10),Update(update_id=11)]
    calls=[];committed=[]
    class Bot:
        id=123
        session=SimpleNamespace(timeout=30)
        async def __call__(self,request,**kwargs):
            calls.append(request.offset)
            if len(calls)==1: return events
            raise asyncio.CancelledError
    failed=asyncio.Event();release=asyncio.Event()
    async def capture(event):
        if event.update_id==11 and not release.is_set():
            failed.set()
            raise OSError('Mongo offline')
        committed.append(event.update_id)
    dp=Dispatcher();install_campaign_admission(dp,SimpleNamespace(capture=capture))
    stream=dp._listen_updates(Bot())
    first=await anext(stream)
    assert first.update_id==10 and committed==[10]
    async def pause(_): await release.wait()
    with patch('src.bot.campaign_polling.asyncio.sleep',side_effect=pause):
        second=asyncio.create_task(anext(stream))
        await asyncio.wait_for(failed.wait(),2)
        assert calls==[None] and not second.done() and committed==[10]
        release.set()
        assert (await second).update_id==11
    assert committed==[10,11]
    with pytest.raises(asyncio.CancelledError): await anext(stream)
    assert calls==[None,12]


@pytest.mark.asyncio
async def test_cancel_during_failed_admission_does_not_ack():
    advanced=[]
    async def listen(*args,**kwargs):
        yield Update(update_id=1)
        advanced.append(True)
    entered=asyncio.Event()
    async def fail(event):
        entered.set()
        raise OSError('offline')
    dp=SimpleNamespace(_listen_updates=listen)
    install_campaign_admission(dp,SimpleNamespace(capture=fail))
    stream=dp._listen_updates()
    task=asyncio.create_task(anext(stream))
    await entered.wait();task.cancel()
    with pytest.raises(asyncio.CancelledError): await task
    assert not advanced


@pytest.mark.asyncio
async def test_default_preview_persists_before_real_polling_offset_advances(tmp_path):
    from aiogram.types import LinkPreviewOptions
    from tests.campaign_support import Harness, FakeDB
    env=await Harness(FakeDB(),tmp_path).open()
    try:
        root=env.root()
        root=root.model_copy(update={'message':root.message.model_copy(update={'link_preview_options':LinkPreviewOptions()})})
        events=[root,env.comment(101)]
        offsets=[]
        class Bot:
            id=999
            session=SimpleNamespace(timeout=30)
            async def __call__(self,request,**kwargs):
                offsets.append(request.offset)
                if len(offsets)==1:return events
                raise asyncio.CancelledError
        dp=Dispatcher();install_campaign_admission(dp,env.service)
        stream=dp._listen_updates(Bot())
        assert (await anext(stream)).update_id==100
        assert [row[0] for row in await env.service.inbox.batch(10)]==[100]
        assert (await anext(stream)).update_id==101
        assert [row[0] for row in await env.service.inbox.batch(10)]==[100,101]
        with pytest.raises(asyncio.CancelledError):await anext(stream)
        assert offsets==[None,102]
    finally:
        await env.close()
