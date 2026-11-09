"""Permission checks through real aiogram routers; never contact Telegram or Mongo."""
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

import pytest
from aiogram.types import CallbackQuery, Message


@pytest.mark.asyncio
@pytest.mark.parametrize('module', ['broadcast', 'boss_editor'])
@pytest.mark.parametrize('kind', ['message', 'callback_query'])
async def test_privileged_router_root_gate(module, kind):
    import importlib
    router = importlib.import_module('src.bot.handlers.' + module).router
    user = dict(id=7, is_bot=False, first_name='Test')
    msg = Message.model_validate(dict(message_id=1,date=1,chat=dict(id=7,type='private'),
                                      **{'from':user}, text='content'))
    event = msg if kind == 'message' else CallbackQuery.model_validate(dict(
        id='q', chat_instance='c', **{'from':user},message=msg,
        data='admin:broadcast' if module=='broadcast' else 'boss_edit:choose_boss'))
    bot = AsyncMock()
    # A container with no services: reaching any handler would fail this test.
    with patch('src.bot.filters.admin.settings', NS(admin_ids=[],admin_ids_str='')):
        await router.propagate_event(kind,event,bot=bot,container=NS())
    bot.assert_not_awaited()
    with patch('src.bot.filters.admin.settings', NS(admin_ids=[7],admin_ids_str='7')):
        allowed, _ = await router.observers[kind].check_root_filters(event,bot=bot)
    assert allowed


@pytest.mark.asyncio
@pytest.mark.parametrize('module', ['admin_commands','maintenance','zov'])
@pytest.mark.parametrize('command', ['/adminhelp','/sensei done','/broadcast','/addcoin 100','/senseizov'])
async def test_admin_only_message_routers_deny_regular_users(module,command):
    import importlib
    router=importlib.import_module('src.bot.handlers.'+module).router
    bot=AsyncMock()
    msg=Message.model_validate(dict(message_id=1,date=1,chat=dict(id=7,type='private'),
        **{'from':dict(id=7,is_bot=False,first_name='User')},text=command)).as_(bot)
    with patch('src.bot.filters.admin.settings', NS(admin_ids=[],admin_ids_str='')):
        await router.propagate_event('message',msg,bot=bot,container=NS())
    bot.assert_not_awaited()


def test_broadcast_bad_request_exception_is_bound():
    from src.bot.handlers import broadcast
    from aiogram.exceptions import TelegramBadRequest
    assert broadcast.TelegramBadRequest is TelegramBadRequest
