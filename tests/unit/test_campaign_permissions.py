from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest
from tests.campaign_support import Harness, FakeDB


@pytest.mark.asyncio
@pytest.mark.parametrize('post_permission', [False, None, True])
async def test_channel_publish_permission_is_not_required(post_permission, tmp_path):
    h = Harness(FakeDB(), tmp_path)
    h.bot.get_chat_member = AsyncMock(return_value=NS(status='administrator', can_post_messages=post_permission))
    try:
        await h.open()
        assert h.service.ready
        assert h.service.inbox is not None
        h.bot.send_message.assert_not_awaited()
    finally:
        await h.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('denied_chat', [-100111, -100222])
async def test_administrator_access_is_still_required_in_both_chats(denied_chat, tmp_path):
    h = Harness(FakeDB(), tmp_path)
    async def member(chat_id, user_id):
        return NS(status='member' if chat_id == denied_chat else 'administrator', can_post_messages=True)
    h.bot.get_chat_member = AsyncMock(side_effect=member)
    with pytest.raises(RuntimeError, match='Bot must be administrator'):
        await h.open()
    assert not h.service.ready
    assert h.service.inbox is None
