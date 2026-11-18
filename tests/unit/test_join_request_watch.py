from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

import pytest
from aiogram.types import Update

from src.services.join_request_watch import JoinRequestWatch


def setup_watch(status='left', present=True):
    now = datetime.now(timezone.utc)
    collection = NS(create_index=AsyncMock(), update_one=AsyncMock(), delete_many=AsyncMock(),
                    find_one_and_update=AsyncMock(), find_one=AsyncMock(return_value={'_id': 3} if present else None))
    container = NS(mongo_client=NS(database=NS(join_request_watch=collection)))
    bot = NS(get_chat_member=AsyncMock(return_value=NS(status=status, is_member=False)), send_message=AsyncMock())
    watch = JoinRequestWatch(container, bot)
    item = {'_id': 3, 'chat_id': -100, 'chat_type': 'supergroup', 'user_id': 77,
            'user': {'id': 77, 'is_bot': False, 'first_name': 'New'},
            'next_check': now, 'expires_at': now + timedelta(days=1)}
    collection.find_one_and_update.return_value = item
    return watch, collection, bot


def request_update(chat_type='supergroup'):
    return Update.model_validate({'update_id': 3, 'chat_join_request': {
        'chat': {'id': -100, 'type': chat_type, 'title': 'Dojo'},
        'from': {'id': 77, 'is_bot': False, 'first_name': 'New'},
        'date': 1700000000, 'user_chat_id': 1234}})


@pytest.mark.asyncio
async def test_request_only_records_no_registration_or_welcome():
    watch, collection, bot = setup_watch()
    await watch.capture(request_update())
    collection.update_one.assert_awaited_once()
    assert collection.update_one.await_args.kwargs['upsert'] is True
    data = collection.update_one.await_args.args[1]['$setOnInsert']
    assert data['user_id'] == 77 and 'user_chat_id' not in data
    bot.send_message.assert_not_awaited()
    bot.get_chat_member.assert_not_awaited()


@pytest.mark.asyncio
async def test_channel_request_is_ignored():
    watch, collection, _ = setup_watch()
    await watch.capture(request_update('channel'))
    collection.update_one.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('status', ['left', 'kicked', 'restricted'])
async def test_unconfirmed_request_never_welcomes(status):
    watch, collection, bot = setup_watch(status)
    with patch('src.services.join_request_watch.group_admin_access.allowed', new=AsyncMock(return_value=True)), \
         patch('src.services.join_request_watch._handle_join', new_callable=AsyncMock) as welcome:
        assert await watch.check_one()
    welcome.assert_not_awaited()
    collection.delete_many.assert_not_awaited()
    bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_confirmed_member_uses_existing_join_flow_and_clears_pending():
    watch, collection, bot = setup_watch('member')
    with patch('src.services.join_request_watch.group_admin_access.allowed', new=AsyncMock(return_value=True)), \
         patch('src.services.join_request_watch._handle_join', new_callable=AsyncMock) as welcome:
        assert await watch.check_one()
    user, container, event = welcome.await_args.args
    assert user.id == 77 and event.chat.id == -100 and container is watch.container
    await event.answer('hello', parse_mode='HTML')
    bot.send_message.assert_awaited_once_with(-100, 'hello', parse_mode='HTML')
    collection.delete_many.assert_awaited_once_with({'chat_id': -100, 'user_id': 77})


@pytest.mark.asyncio
async def test_normal_join_removing_request_prevents_fallback():
    watch, collection, _ = setup_watch('member', present=False)
    with patch('src.services.join_request_watch.group_admin_access.allowed', new=AsyncMock(return_value=True)), \
         patch('src.services.join_request_watch._handle_join', new_callable=AsyncMock) as welcome:
        await watch.check_one()
    welcome.assert_not_awaited()


@pytest.mark.asyncio
async def test_check_error_keeps_request_for_retry():
    watch, collection, bot = setup_watch()
    bot.get_chat_member.side_effect = OSError('offline')
    with patch('src.services.join_request_watch.group_admin_access.allowed', new=AsyncMock(return_value=True)):
        await watch.check_one()
    collection.delete_many.assert_not_awaited()
