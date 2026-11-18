from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

import pytest
from aiogram.types import User
from src.infra.mtproto.join_updates import handle_channel_participant
from src.infra.mtproto.widgets import MtprotoWidgets


class Member: pass
class SelfMember: pass
class Admin: pass
class Creator: pass
class Banned:
    def __init__(self, left): self.left = left
class Left: pass
class Update: pass
class PeerChannel:
    def __init__(self, channel_id): self.channel_id = channel_id

types = NS(ChannelParticipant=Member, ChannelParticipantSelf=SelfMember,
           ChannelParticipantAdmin=Admin, ChannelParticipantCreator=Creator,
           ChannelParticipantBanned=Banned, PeerChannel=PeerChannel, UpdateChannelParticipant=Update)


def setup():
    user = User(id=77, is_bot=False, first_name='Alice')
    bot = NS(id=123, get_chat_member=AsyncMock(return_value=NS(status='member', user=user)),
             send_message=AsyncMock())
    container = NS(settings=NS(discussion_chat_id=-1002098194464), bot=bot)
    transport = NS(types=types, container=container,
                   utils=NS(get_peer_id=lambda peer: int('-100'+str(peer.channel_id))))
    event = Update()
    event.channel_id=2098194464; event.user_id=77
    event.prev_participant=Left(); event.new_participant=Member()
    event.date=datetime.now(timezone.utc)
    return transport, event, bot


@pytest.mark.asyncio
async def test_mtproto_confirmed_join_uses_bot_api_and_existing_welcome():
    transport, event, bot = setup()
    with patch('src.infra.mtproto.join_updates.group_admin_access.allowed', new=AsyncMock(return_value=True)), \
         patch('src.infra.mtproto.join_updates._handle_join', new_callable=AsyncMock) as welcome:
        await handle_channel_participant(event, transport)
    user, container, message = welcome.await_args.args
    assert user.id == 77 and container is transport.container and message.chat.id == -1002098194464
    await message.answer('welcome', parse_mode='HTML')
    bot.send_message.assert_awaited_once_with(-1002098194464, 'welcome', parse_mode='HTML')
    bot.get_chat_member.assert_awaited_once_with(-1002098194464, 77)


@pytest.mark.asyncio
@pytest.mark.parametrize('case', ['other_chat', 'promotion', 'leave', 'old', 'future', 'unconfirmed', 'not_admin'])
async def test_non_join_never_awards(case):
    transport, event, bot = setup()
    if case == 'other_chat': event.channel_id=1
    if case == 'promotion': event.prev_participant=Member(); event.new_participant=Admin()
    if case == 'leave': event.prev_participant=Member(); event.new_participant=Left()
    if case == 'old': event.date -= timedelta(minutes=6)
    if case == 'future': event.date += timedelta(minutes=2)
    if case == 'unconfirmed': bot.get_chat_member.return_value.status='left'
    with patch('src.infra.mtproto.join_updates.group_admin_access.allowed', new=AsyncMock(return_value=case != 'not_admin')), \
         patch('src.infra.mtproto.join_updates._handle_join', new_callable=AsyncMock) as welcome:
        await handle_channel_participant(event, transport)
    welcome.assert_not_awaited()


@pytest.mark.asyncio
async def test_raw_dispatch_routes_participant_update():
    transport, event, _ = setup()
    with patch('src.infra.mtproto.join_updates.handle_channel_participant', new_callable=AsyncMock) as handler:
        await MtprotoWidgets.on_update(transport, event)
    handler.assert_awaited_once_with(event, transport)
