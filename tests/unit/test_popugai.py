from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

import pytest
from aiogram import Bot
from aiogram.types import Message
from aiogram.filters import CommandObject
from src.bot.middlewares.popugai import PopugaiMiddleware
from src.services.popugai_service import PopugaiService
from tests.unit.test_hedgehog_game import Collection


def message(**changes):
    values=dict(message_id=10,date=1,chat=dict(id=-1007,type='supergroup'),
        **{'from':dict(id=7,is_bot=False,first_name='User')},text='hello')
    values.update(changes)
    return Message.model_validate(values).as_(Bot('123456:TEST',session=AsyncMock()))


def service():
    return NS(add_media=AsyncMock(),get_reply_chance=AsyncMock(return_value=1),
              get_random_media=AsyncMock(return_value=('sticker','saved')))


@pytest.mark.asyncio
@pytest.mark.parametrize('kind',['sticker','animation'])
async def test_learns_media_and_replies_without_consuming_handler(kind):
    s=service();s.get_random_media.return_value=('gif' if kind=='animation' else 'sticker','saved')
    media=dict(file_id='file',file_unique_id='unique',width=10,height=10,duration=1)
    if kind=='sticker': media.update(type='regular',is_animated=False,is_video=False)
    msg=message(text=None,**{kind:media});handler=AsyncMock(return_value='handled')
    with patch('src.bot.middlewares.popugai.group_admin_access.allowed',new=AsyncMock(return_value=True)):
        assert await PopugaiMiddleware(NS(popugai_service=s))(handler,msg,{})=='handled'
    s.add_media.assert_awaited_once_with(-1007,'gif' if kind=='animation' else 'sticker','file','unique')
    method=msg.bot.session.call_args.args[1]
    assert method.__api_method__==('sendAnimation' if kind=='animation' else 'sendSticker')
    assert method.reply_parameters.message_id==10
    handler.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize('changes',[
    {'text':'/popugai 100'}, {'chat':dict(id=7,type='private')},
    {'from':dict(id=9,is_bot=True,first_name='Bot')},
    {'sender_chat':dict(id=-1007,type='supergroup')},
    {'text':None},
])
async def test_ignores_commands_private_bots_and_service_messages(changes):
    s=service();handler=AsyncMock();msg=message(**changes)
    await PopugaiMiddleware(NS(popugai_service=s))(handler,msg,{})
    s.get_reply_chance.assert_not_awaited();handler.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize('chance,roll,sends',[(0,0,False),(.01,.02,False),(.01,.001,True),(1,.999,True)])
async def test_probability(chance,roll,sends):
    s=service();s.get_reply_chance.return_value=chance;msg=message()
    with patch('src.bot.middlewares.popugai.group_admin_access.allowed',new=AsyncMock(return_value=True)),patch('src.bot.middlewares.popugai.random.random',return_value=roll):
        await PopugaiMiddleware(NS(popugai_service=s))(AsyncMock(),msg,{})
    assert msg.bot.session.called==sends


@pytest.mark.asyncio
async def test_no_admin_or_outage_never_blocks_other_handlers():
    s=service();msg=message();handler=AsyncMock()
    with patch('src.bot.middlewares.popugai.group_admin_access.allowed',new=AsyncMock(return_value=False)):
        await PopugaiMiddleware(NS(popugai_service=s))(handler,msg,{})
    s.get_reply_chance.assert_not_awaited()
    s.get_reply_chance.side_effect=RuntimeError()
    with patch('src.bot.middlewares.popugai.group_admin_access.allowed',new=AsyncMock(return_value=True)):
        await PopugaiMiddleware(NS(popugai_service=s))(handler,msg,{})
    assert handler.await_count==2


@pytest.mark.asyncio
async def test_mongo_atomic_dedup_refresh_and_chat_isolation():
    db=NS(popugai_chances=Collection(),popugai_media=Collection())
    svc=PopugaiService(NS(database=db))
    await svc.add_media(-1,'gif','old','unique')
    await svc.add_media(-1,'gif','new','unique')
    await svc.add_media(-2,'gif','other','unique')
    assert len(db.popugai_media.docs)==2
    assert {x['file_id'] for x in db.popugai_media.docs.values()}=={'new','other'}
    db.popugai_media.aggregate=lambda pipeline: NS(to_list=AsyncMock(return_value=[{'media_type':'gif','file_id':'new'}]))
    assert await svc.get_random_media(-1)==('gif','new')
    await svc.set_reply_chance(-1,.01)
    assert await svc.get_reply_chance(-1)==.01
    assert await svc.get_reply_chance(-2)==0


@pytest.mark.asyncio
@pytest.mark.parametrize('arg,expected',[('1',.01),('0.5',.005),('100',1),('off',0),('5%',.05)])
async def test_command_uses_percent_not_probability(arg,expected):
    from src.bot.handlers.chat_settings import cmd_popugai
    s=service();s.set_reply_chance=AsyncMock();msg=message(text='/popugai '+arg)
    with patch('src.bot.handlers.chat_settings.is_admin',new=AsyncMock(return_value=True)):
        await cmd_popugai(msg,CommandObject(prefix='/',command='popugai',args=arg),msg.bot,NS(popugai_service=s))
    s.set_reply_chance.assert_awaited_once_with(-1007,expected)
