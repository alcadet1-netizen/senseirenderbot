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
