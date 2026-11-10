from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
from datetime import datetime

import pytest
from pymongo.errors import DuplicateKeyError
from aiogram.types import Message
from src.services.throttle_service import ThrottleService
from src.bot.middlewares.chat_activity import ChatActivityMiddleware
from src.bot.middlewares.digest import DigestMiddleware


@pytest.mark.asyncio
async def test_throttle_explicit_expiry_predicate_date_storage_and_error_policy():
    collection=NS(find_one_and_update=AsyncMock())
    svc=ThrottleService(NS(database=NS(throttle=collection)))
    assert await svc.throttle('u',2)
    args=collection.find_one_and_update.call_args.args
    assert '$or' in args[0] and isinstance(args[1]['$set']['expiry'],datetime)
    collection.find_one_and_update.side_effect=DuplicateKeyError('active')
    assert not await svc.throttle('u',2)
    collection.find_one_and_update.side_effect=RuntimeError('outage')
    assert await svc.throttle('u',2)  # existing fail-open policy preserved
    collection.find_one_and_update.reset_mock()
    assert await svc.throttle('u',0)
    collection.find_one_and_update.assert_not_called()


@pytest.mark.asyncio
async def test_anonymous_group_message_does_not_crash_activity_or_digest():
    msg=Message.model_validate(dict(message_id=1,date=1,chat=dict(id=-1001,type='supergroup'),
        sender_chat=dict(id=-1001,type='supergroup'),text='anonymous'))
    container=NS(chat_activity_service=NS(update_activity=AsyncMock()),banzai_service=NS(update_user_activity=AsyncMock()))
    handler=AsyncMock(return_value='handled')
    assert await ChatActivityMiddleware()(handler,msg,{'container':container})=='handled'
    container.chat_activity_service.update_activity.assert_awaited_once_with(-1001)
    container.banzai_service.update_user_activity.assert_not_awaited()
    assert await DigestMiddleware(container)(handler,msg,{})=='handled'
