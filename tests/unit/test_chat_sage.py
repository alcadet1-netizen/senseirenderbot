from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
import pytest
from src.services.digest_service import DigestService


@pytest.mark.asyncio
@pytest.mark.parametrize('raw,expected',[
    ('{"reply":"А что хочется улучшить?"}','А что хочется улучшить?'),
    ('{"reply":null}',None), ('❌ Error: provider body',None),
    ('{"reply":"https://example.com"}',None), ('not json',None),
    ('{"reply":"'+'a'*241+'"}',None), ('[]',None), ('{"reply":""}',None)])
async def test_only_short_valid_json_can_be_sent(raw,expected):
    svc=DigestService.__new__(DigestService)
    svc.ai_factory=NS(get_provider=lambda name:NS(api_key='dummy'),generate_text=AsyncMock(return_value=raw))
    assert await svc.chat_sage_reply('Интересно как устроен новый виджет')==expected
    args=svc.ai_factory.generate_text.call_args
    assert args.kwargs['provider_name']=='groq'
    assert args.kwargs['max_tokens']==220
    assert 'message' in args.args[1]


@pytest.mark.asyncio
async def test_no_key_means_no_api_call():
    svc=DigestService.__new__(DigestService)
    svc.ai_factory=NS(get_provider=lambda name:NS(api_key=''),generate_text=AsyncMock())
    assert await svc.chat_sage_reply('text') is None
    svc.ai_factory.generate_text.assert_not_awaited()


@pytest.mark.asyncio
async def test_silent_model_consumes_reservation_and_never_sends_fallback():
    from unittest.mock import patch
    from tests.unit.test_fly import fixture, message
    from src.bot.handlers.fly import FlyReactionMiddleware
    db,svc,_=fixture()
    svc.container.digest_service=NS(chat_sage_reply=AsyncMock(return_value=None))
    middleware=FlyReactionMiddleware(svc.container);middleware.service=svc
    await db.fly_settings.update_one({'_id':-100222},{'$set':{'enabled':True}},upsert=True)
    msg=message();event=NS(**{k:getattr(msg,k) for k in ('text','from_user','sender_chat','is_automatic_forward','chat','message_id')},
                          bot=NS(),answer=AsyncMock())
    handler=AsyncMock(return_value='ok')
    with patch('src.bot.handlers.fly.group_admin_access.allowed',new=AsyncMock(return_value=True)):
        assert await middleware(handler,event,{})=='ok'
        await middleware(handler,event,{})
    svc.container.digest_service.chat_sage_reply.assert_awaited_once_with(event.text)
    event.answer.assert_not_awaited()
    assert (await db.fly_decisions.find_one({'_id':'-100222:1'}))['status']=='ai_silent_or_unavailable'
