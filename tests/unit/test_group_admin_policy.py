from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

import pytest
from aiogram.types import Update
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import SendMessage

from src.bot.middlewares.group_admin import GroupAdminMiddleware, group_admin_access
from src.services.chat_activity_service import ChatActivityService


@pytest.fixture(autouse=True)
def clear_cache():
    group_admin_access.cache.clear()
    yield
    group_admin_access.cache.clear()


def bot(status):
    return NS(id=123,get_chat_member=AsyncMock(return_value=NS(status=status)),send_message=AsyncMock())


def update(kind='message',private=False):
    msg=dict(message_id=1,date=1,chat=dict(id=7 if private else -100222,type='private' if private else 'supergroup'),
        text='Ежа',**{'from':dict(id=7,is_bot=False,first_name='User')})
    if kind=='callback_query':
        return Update.model_validate(dict(update_id=1,callback_query=dict(id='q',chat_instance='x',data='petbuy:offer',
            message=msg,**{'from':msg['from']})))
    return Update.model_validate(dict(update_id=1,message=msg))


@pytest.mark.asyncio
@pytest.mark.parametrize('status',['left','kicked','member','restricted'])
@pytest.mark.parametrize('kind',['message','callback_query'])
async def test_non_admin_groups_have_no_handlers_or_rewards(status,kind):
    handler=AsyncMock();b=bot(status)
    await GroupAdminMiddleware()(handler,update(kind),{'bot':b})
    handler.assert_not_awaited()
    b.send_message.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('status,private',[('administrator',False),('creator',False),('member',True)])
async def test_admin_groups_and_private_chat_work(status,private):
    handler=AsyncMock(return_value='ok');b=bot(status)
    assert await GroupAdminMiddleware()(handler,update(private=private),{'bot':b})=='ok'
    handler.assert_awaited_once()
    if private: b.get_chat_member.assert_not_awaited()


@pytest.mark.asyncio
async def test_reminder_permission_denial_no_retries_or_error_spam(caplog):
    service=ChatActivityService(NS(database=NS(chat_activities=AsyncMock(),chat_user_activities=AsyncMock())))
    b=bot('administrator')
    b.send_message.side_effect=TelegramBadRequest(method=SendMessage(chat_id=-100222,text='x'),
        message='not enough rights to send text messages to the chat')
    with patch('src.services.chat_activity_service.asyncio.sleep',new=AsyncMock()) as sleep:
        assert not await service._send_reminder(b,-100222)
        assert not await service._send_reminder(b,-100222)
    b.send_message.assert_awaited_once()
    sleep.assert_not_awaited()
    assert not caplog.records


@pytest.mark.asyncio
async def test_removed_bot_no_reminder_request():
    service=ChatActivityService(NS(database=NS(chat_activities=AsyncMock(),chat_user_activities=AsyncMock())))
    b=bot('left')
    assert not await service._send_reminder(b,-100222)
    b.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_membership_update_invalidates_denial_and_restores_admin_access():
    b=bot('member');handler=AsyncMock()
    middleware=GroupAdminMiddleware()
    await middleware(handler,update(),{'bot':b})
    handler.assert_not_awaited()
    b.get_chat_member.return_value=NS(status='administrator')
    membership=Update.model_validate(dict(update_id=2,my_chat_member=dict(
        chat=dict(id=-100222,type='supergroup'),date=1,
        **{'from':dict(id=7,is_bot=False,first_name='Admin')},
        old_chat_member=dict(status='left',user=dict(id=123,is_bot=True,first_name='Bot')),
        new_chat_member=dict(status='member',user=dict(id=123,is_bot=True,first_name='Bot')))))
    await middleware(handler,membership,{'bot':b})
    handler.reset_mock()
    await middleware(handler,update(),{'bot':b})
    handler.assert_awaited_once()


@pytest.mark.asyncio
async def test_forbidden_membership_lookup_cached_without_reaction():
    from aiogram.exceptions import TelegramForbiddenError
    from aiogram.methods import GetChatMember
    b=bot('administrator')
    b.get_chat_member.side_effect=TelegramForbiddenError(method=GetChatMember(chat_id=-100222,user_id=123),message='bot was kicked')
    handler=AsyncMock()
    for _ in range(3): await GroupAdminMiddleware()(handler,update(),{'bot':b})
    handler.assert_not_awaited()
    b.get_chat_member.assert_awaited_once()
