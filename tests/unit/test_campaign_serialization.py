import json
from unittest.mock import AsyncMock

import pytest
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.types import Update
from pydantic_core import PydanticSerializationError
from src.infra.comment_campaign_inbox import serialize_update, CampaignInbox


def event():
    return Update.model_validate(dict(update_id=10,message=dict(message_id=42,date=123,
        chat=dict(id=-1001,type='supergroup'),**{'from':dict(id=7,is_bot=False,first_name='Test')},
        text='Привет',link_preview_options=dict(is_disabled=False),
        reply_to_message=dict(message_id=41,date=122,chat=dict(id=-1001,type='supergroup'),
                              link_preview_options=dict(url='https://example.com')))))


def test_actual_default_sentinel_roundtrip_in_nested_messages():
    update=event()
    with pytest.raises(PydanticSerializationError): update.model_dump_json(exclude_none=True)
    payload=serialize_update(update);raw=json.loads(payload);restored=Update.model_validate_json(payload)
    assert restored.update_id==10 and restored.message.message_id==42
    assert restored.message.from_user.id==7 and restored.message.from_user.is_bot is False
    assert restored.message.text=='Привет' and restored.message.date.timestamp()==123
    assert raw['message']['link_preview_options']=={'is_disabled':False}
    assert raw['message']['reply_to_message']['link_preview_options']=={'url':'https://example.com'}
    assert restored.message.reply_to_message.message_id==41


def test_outgoing_bot_defaults_are_not_injected_into_incoming_payload():
    update=event().as_(Bot('123456:TEST',default=DefaultBotProperties(link_preview_prefer_large_media=True)))
    assert 'prefer_large_media' not in json.loads(serialize_update(update))['message']['link_preview_options']


@pytest.mark.asyncio
async def test_unknown_object_is_not_stringified_or_persisted():
    from types import SimpleNamespace as NS
    inbox=CampaignInbox(NS(campaign_inbox_updates=NS(),campaign_inbox_deletions=NS()),99,None)
    inbox.mutate=AsyncMock()
    bad=event().model_copy(update={'unknown_payload':object()})
    # model_copy stores unknown keys outside declared fields; inject into extras explicitly.
    bad.__pydantic_extra__={'unknown_payload':object()}
    with pytest.raises(TypeError): await inbox.put(bad)
    inbox.mutate.assert_not_awaited()
