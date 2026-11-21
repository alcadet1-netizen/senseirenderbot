from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

import pytest
from aiogram.types import Update, Message

from src.bot.handlers.admin_commands import cmd_sensei_mute_on, cmd_sensei_mute_off
from src.bot.middlewares.moderation import ModerationMiddleware


@pytest.mark.asyncio
@pytest.mark.parametrize('content', [dict(text='привет'), dict(text='🙂'),
    dict(text='🙂', entities=[dict(type='custom_emoji', offset=0, length=2, custom_emoji_id='123')]),
    dict(sticker=dict(file_id='a', file_unique_id='b', type='regular', width=64, height=64, is_animated=False, is_video=False)),
    dict(animation=dict(file_id='a', file_unique_id='b', width=64, height=64, duration=2))])
async def test_mute_deletes_before_routing_then_unmute_passes(content):
    event = Update.model_validate({'update_id': 1, 'message': {'message_id': 3, 'date': 1,
        'chat': {'id': -10, 'type': 'supergroup'}, 'from': {'id': 8, 'first_name': 'User', 'is_bot': False}, **content}})
    container = NS(moderation_service=NS(is_muted=AsyncMock(side_effect=[True, False])))
    middleware = ModerationMiddleware(container)
    handler = AsyncMock()
    with patch.object(Message, 'delete', new_callable=AsyncMock) as delete, patch('src.bot.middlewares.moderation.campaign_message_deleted', new_callable=AsyncMock):
        await middleware(handler, event, {})
        handler.assert_not_awaited()
        await middleware(handler, event, {})
        handler.assert_awaited_once()
        delete.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize('reply', [True, False])
async def test_admin_mute_and_unmute(reply):
    svc = AsyncMock()
    for name in ('mute_user', 'unmute_user', 'mute_user_by_username', 'unmute_user_by_username'):
        getattr(svc, name).return_value = {'success': True}
    msg = NS(from_user=NS(id=7), answer=AsyncMock(), text='/senseimuteon ' + ('' if reply else '@Player ') + '1',
             reply_to_message=NS(from_user=NS(id=8, full_name='User'), sender_chat=None) if reply else None)
    await cmd_sensei_mute_on(msg, NS(moderation_service=svc))
    msg.text = '/senseimuteoff' + ('' if reply else ' @Player')
    await cmd_sensei_mute_off(msg, NS(moderation_service=svc))
    if reply:
        assert svc.mute_user.await_args.kwargs['until'].tzinfo is not None
        svc.unmute_user.assert_awaited_once_with(8)
    else:
        svc.mute_user_by_username.assert_awaited_once_with('@Player', hours=1, muted_by=7)
        svc.unmute_user_by_username.assert_awaited_once_with('@Player')
