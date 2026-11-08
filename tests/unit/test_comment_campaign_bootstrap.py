from unittest.mock import AsyncMock
import pytest

from src.bot.middlewares.comment_campaign import CommentCampaignMiddleware
from src.services.comment_campaign_service import CommentCampaignService
from src.infra.comment_campaign_inbox import CampaignInbox
from tests.campaign_support import FakeDB, Harness


@pytest.mark.asyncio
async def test_numeric_ids_pinned_after_initial_username_resolution(tmp_path):
    env=Harness(FakeDB(),tmp_path)
    env.cfg.target_channel_id=0;env.cfg.discussion_chat_id=0
    env.service=CommentCampaignService(env.container,clock=lambda:env.clock[0])
    await env.service.initialize(env.bot)
    env.bot.get_chat.assert_any_await('@SenseiDurova')
    await env.service.stop();env.bot.get_chat.reset_mock()
    env.service=CommentCampaignService(env.container,clock=lambda:env.clock[0])
    await env.service.initialize(env.bot)
    assert all(call.args[0]!='@SenseiDurova' for call in env.bot.get_chat.await_args_list)
    assert env.service.channel_id==-100111 and env.service.discussion_id==-100222
    await env.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('cause',['topology','rights','link'])
async def test_startup_fail_closed_and_does_not_start_worker(tmp_path,cause):
    env=Harness(FakeDB(),tmp_path)
    if cause=='topology': env.db.command=AsyncMock(return_value={})
    if cause=='rights': env.bot.get_chat_member.return_value.status='member'
    if cause=='link': env.cfg.discussion_chat_id=-100333;env.service.discussion_id=-100333
    with pytest.raises(RuntimeError):
        await env.service.start(env.bot)
    assert not env.service.ready and env.service.task is None
    await env.close()


@pytest.mark.asyncio
async def test_capture_durable_before_game_handler_and_worker_stops(tmp_path):
    env=await Harness(FakeDB(),tmp_path).open()
    handler=AsyncMock(return_value='handled')
    middleware=CommentCampaignMiddleware(env.service)
    assert await middleware(handler,env.root(),{})=='handled'
    handler.assert_awaited_once()
    assert await env.service.inbox.pending()
    assert await env.db.comment_campaigns.count_documents({})==0
    await env.service.tick()
    assert await env.db.comment_campaigns.count_documents({})==1
    await env.close()


@pytest.mark.asyncio
async def test_disk_failure_is_not_silently_acknowledged(tmp_path):
    env=await Harness(FakeDB(),tmp_path).open()
    env.service.inbox.put=AsyncMock(side_effect=OSError('disk unavailable'))
    handler=AsyncMock()
    with pytest.raises(OSError): await CommentCampaignMiddleware(env.service)(handler,env.root(),{})
    handler.assert_not_called()
    await env.close()


@pytest.mark.parametrize('path',['',':memory:','  '])
def test_nonpersistent_inbox_path_refused(path):
    with pytest.raises(ValueError): CampaignInbox(path,999)


@pytest.mark.asyncio
async def test_barrier_blocks_other_connection_without_losing_capture(tmp_path):
    import asyncio
    from types import SimpleNamespace
    a=CampaignInbox(str(tmp_path/'shared.sqlite3'),999)
    b=CampaignInbox(str(tmp_path/'shared.sqlite3'),999)
    await a.open();await b.open()
    await b.db.execute('PRAGMA busy_timeout=1')
    event=SimpleNamespace(update_id=123,model_dump_json=lambda **kw:'{}')
    try:
        assert a.identity==b.identity
        async with a.settlement_barrier() as empty:
            assert empty
            pending=asyncio.create_task(b.put(event))
            await asyncio.sleep(.1)
            assert not pending.done()
        await asyncio.wait_for(pending,5)
        assert await a.pending()
    finally:
        await a.close();await b.close()


@pytest.mark.asyncio
async def test_short_notifications_and_escaped_mention(tmp_path):
    from src.services.comment_campaign_service import START_TEXT
    env=await Harness(FakeDB(),tmp_path).open()
    try:
        await env.profile(7);camp=await env.begin();await env.service.ingest(env.comment(101))
        camp=await env.finish()
        text=await env.service.final_text(camp)
        assert len(START_TEXT)<200 and len(text)<200
        assert 'User&lt;7&gt;' in text and '2000 Sensei Coin' in text
        assert 'Спасибо' not in text
    finally:
        await env.close()


@pytest.mark.asyncio
async def test_temporary_startup_timeout_retries_then_announces(tmp_path):
    from unittest.mock import patch
    env=Harness(FakeDB(),tmp_path)
    original=env.bot.get_chat.side_effect
    calls=0
    async def flaky(chat_id):
        nonlocal calls
        calls+=1
        if calls==1: raise TimeoutError('temporary outage')
        return await original(chat_id)
    env.bot.get_chat.side_effect=flaky
    with patch('src.services.comment_campaign_service.asyncio.sleep',new=AsyncMock()):
        await env.service.start(env.bot)
    try:
        assert env.service.health_snapshot()=={'enabled':True,'ready':True,'state':'ready'}
        await env.service.capture(env.root())
        # Stop only the background runner, use its durable queue deterministically.
        env.service.task.cancel()
        import asyncio
        try: await env.service.task
        except asyncio.CancelledError: pass
        await env.service.tick()
        assert env.bot.send_message.await_count==1
    finally: await env.close()


@pytest.mark.asyncio
async def test_exhausted_startup_timeout_refuses_polling(tmp_path):
    from unittest.mock import patch
    env=Harness(FakeDB(),tmp_path)
    env.bot.get_chat.side_effect=TimeoutError('offline')
    with patch('src.services.comment_campaign_service.asyncio.sleep',new=AsyncMock()) as sleep:
        with pytest.raises(TimeoutError): await env.service.start(env.bot)
    assert sleep.await_count==2 and env.bot.get_chat.await_count==3
    assert env.service.health_snapshot()=={'enabled':True,'ready':False,'state':'error'}
    assert env.service.task is None
    await env.close()


@pytest.mark.asyncio
async def test_disabled_feature_is_explicit_in_health_and_logs(tmp_path,caplog):
    env=Harness(FakeDB(),tmp_path);env.cfg.comment_campaigns_enabled=False
    await env.service.start(env.bot)
    assert env.service.health_snapshot()=={'enabled':False,'ready':False,'state':'disabled'}
    assert 'COMMENT_CAMPAIGNS_ENABLED=true' in caplog.text
    env.bot.get_chat.assert_not_called()
    await env.close()


@pytest.mark.asyncio
async def test_startup_grace_does_not_delay_announcement(tmp_path):
    import asyncio
    from datetime import timedelta
    env=await Harness(FakeDB(),tmp_path).open()
    env.service.settlement_not_before=env.clock[0]+timedelta(seconds=30)
    try:
        await env.service.capture(env.root())
        sent=asyncio.Event()
        original=env.bot.send_message.side_effect
        async def announce(**kwargs):
            result=await original(**kwargs);sent.set();return result
        env.bot.send_message.side_effect=announce
        task=asyncio.create_task(env.service.run())
        try: await asyncio.wait_for(sent.wait(),2)
        finally:
            task.cancel()
            try: await task
            except asyncio.CancelledError: pass
        assert env.bot.send_message.await_count==1
    finally: await env.close()


@pytest.mark.asyncio
async def test_restart_grace_still_defers_overdue_settlement(tmp_path):
    from datetime import timedelta
    env=await Harness(FakeDB(),tmp_path).open()
    try:
        await env.begin()
        env.clock[0]+=timedelta(hours=4,seconds=1)
        env.service.settlement_not_before=env.clock[0]+timedelta(seconds=30)
        await env.service.tick()
        row=await env.db.comment_campaigns.find_one({'_id':'-100111:1'})
        assert not row['sealed'] and row['phase']=='wait'
        env.clock[0]+=timedelta(seconds=31)
        await env.service.tick()
        assert (await env.db.comment_campaigns.find_one({'_id':'-100111:1'}))['sealed']
    finally: await env.close()


@pytest.mark.asyncio
async def test_admitted_root_wakes_idle_worker_without_poll_delay(tmp_path):
    import asyncio
    from unittest.mock import patch
    env=await Harness(FakeDB(),tmp_path).open()
    env.cfg.campaign_poll_seconds=60
    idle=asyncio.Event();sent=asyncio.Event()
    original_tick=env.service.tick;original_send=env.bot.send_message.side_effect
    async def tick():
        result=await original_tick();idle.set();return result
    async def send(**kwargs):
        result=await original_send(**kwargs);sent.set();return result
    env.bot.send_message.side_effect=send
    task=None
    try:
        with patch.object(env.service,'tick',side_effect=tick):
            task=asyncio.create_task(env.service.run())
            await asyncio.wait_for(idle.wait(),2)
            await env.service.capture(env.root())
            await asyncio.wait_for(sent.wait(),2)
            assert env.bot.send_message.await_count==1
    finally:
        if task:
            task.cancel()
            try: await task
            except asyncio.CancelledError: pass
        await env.close()
