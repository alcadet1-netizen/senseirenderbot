from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

import pytest
from aiogram import Bot
from aiogram.methods import GetChatMember, SendMessage
from aiogram.types import Update

from src.bot.chat_scope import GameChatScopeMiddleware, resolve_game_chat
from src.bot.custom_bot import AntiSpamBot
from src.bot.campaign_polling import install_campaign_admission


def settings(**kwargs):
    return NS(main_chat_id=kwargs.get('main_chat_id', 0), allowed_chats_str='',
              comment_campaigns_enabled=kwargs.get('enabled', False),
              discussion_chat_id=kwargs.get('discussion', 0))


@pytest.mark.asyncio
async def test_resolve_pins_id_and_rejects_misconfiguration():
    bot = NS(get_chat=AsyncMock(return_value=NS(id=-10042, type='supergroup')))
    config = settings()
    assert await resolve_game_chat(bot, config) == -10042
    assert (config.main_chat_id, config.allowed_chats_str, bot.game_chat_id) == (-10042, '-10042', -10042)
    with pytest.raises(RuntimeError, match='MAIN_CHAT_ID'):
        await resolve_game_chat(bot, settings(main_chat_id=-10099))
    bot.get_chat.return_value.type = 'channel'
    with pytest.raises(RuntimeError, match='group'):
        await resolve_game_chat(bot, settings())


def message(chat_id, kind='supergroup'):
    return {'message_id': 1, 'date': 1700000000, 'chat': {'id': chat_id, 'type': kind},
            'from': {'id': 7, 'is_bot': False, 'first_name': 'A'}, 'text': '/task_add @example'}


@pytest.mark.asyncio
@pytest.mark.parametrize('payload,allowed', [
    ({'message': message(-10042)}, True),
    ({'message': message(-10043)}, False),
    ({'message': message(7, 'private')}, True),
    ({'edited_message': message(-10043)}, False),
    ({'channel_post': message(-10050, 'channel')}, False),
    ({'callback_query': {'id': 'cb', 'from': {'id': 7, 'is_bot': False, 'first_name': 'A'},
                         'chat_instance': '1', 'message': message(-10043)}}, False),
    ({'callback_query': {'id': 'cb', 'from': {'id': 7, 'is_bot': False, 'first_name': 'A'},
                         'chat_instance': '1', 'inline_message_id': 'abc'}}, False),
    ({'inline_query': {'id': 'q', 'from': {'id': 7, 'is_bot': False, 'first_name': 'A'},
                       'query': 'sc_123', 'offset': ''}}, False),
])
async def test_scope_routes_only_main_group_or_private(payload, allowed):
    event = Update.model_validate({'update_id': 1, **payload})
    handler = AsyncMock(return_value='ok')
    result = await GameChatScopeMiddleware(NS(settings=settings(main_chat_id=-10042)))(handler, event, {})
    assert handler.await_count == int(allowed)
    assert result == ('ok' if allowed else None)


@pytest.mark.asyncio
async def test_outbound_scope_allows_subscription_reads_and_private_messages():
    bot = AntiSpamBot(token='123456:TEST')
    bot.game_chat_id = -10042
    with patch.object(Bot, '__call__', new=AsyncMock(return_value=True)) as send:
        await bot(GetChatMember(chat_id=-10099, user_id=7))
        await bot(SendMessage(chat_id=7, text='ok'))
        await bot(SendMessage(chat_id=-10042, text='ok'))
        with pytest.raises(ValueError, match='blocked'):
            await bot(SendMessage(chat_id=-10099, text='no'))
        with pytest.raises(ValueError, match='blocked'):
            await bot(SendMessage(chat_id='@otherchannel', text='no'))
        assert send.await_count == 3
    await bot.session.close()


@pytest.mark.asyncio
async def test_campaign_and_join_admission_is_scoped():
    foreign = Update.model_validate({'update_id': 1, 'chat_join_request': {
        'chat': {'id': -10099, 'type': 'supergroup', 'title': 'Other'},
        'from': {'id': 7, 'is_bot': False, 'first_name': 'A'}, 'date': 1700000000, 'user_chat_id': 7}})
    async def updates(*args, **kwargs):
        yield foreign
    dispatcher = NS(_listen_updates=updates)
    service = NS(discussion_id=-10099, capture=AsyncMock())
    watch = NS(capture=AsyncMock())
    install_campaign_admission(dispatcher, service, watch, game_chat_id=-10042)
    assert [event async for event in dispatcher._listen_updates()] == [foreign]
    service.capture.assert_not_awaited()
    watch.capture.assert_not_awaited()


@pytest.mark.asyncio
async def test_foreign_pending_join_is_discarded_without_welcome():
    from tests.unit.test_join_request_watch import setup_watch
    watch, collection, bot = setup_watch('member')
    watch.container.settings = settings(main_chat_id=-10042)
    assert await watch.check_one()
    bot.get_chat_member.assert_not_awaited()
    collection.delete_many.assert_awaited_once_with({'_id': 3})


def test_automatic_forwards_and_system_senders_are_not_player_activity():
    from aiogram.types import Message
    from src.bot.middlewares.user_activity import UserActivityMiddleware
    middleware = object.__new__(UserActivityMiddleware)
    base = message(-10042)
    assert middleware._is_valid_event(Message.model_validate(base))
    for changes in (
        {'is_automatic_forward': True},
        {'sender_chat': {'id': -1005, 'type': 'channel', 'title': 'Channel'}},
        {'from': {'id': 777000, 'is_bot': False, 'first_name': 'Telegram'}},
        {'from': {'id': 8, 'is_bot': True, 'first_name': 'Bot'}},
    ):
        assert not middleware._is_valid_event(Message.model_validate({**base, **changes}))


@pytest.mark.asyncio
async def test_foreign_banzai_and_boss_cannot_start_from_private_admin_controls():
    from src.services.banzai_service import BanzaiService
    from src.bot.handlers.boss_commands import launch_boss
    service = object.__new__(BanzaiService)
    service.banzai_games = NS(find_one=AsyncMock())
    bot = NS(game_chat_id=-10042)
    assert not await service.start_game(-10099, bot)
    service.banzai_games.find_one.assert_not_awaited()
    with pytest.raises(ValueError, match='airchatton'):
        await launch_boss(bot, -10099, 'boss', NS())


@pytest.mark.asyncio
async def test_legacy_foreign_duel_invitation_cannot_lock_or_create_game():
    from src.services.dojo_duel import open_invitation
    from src.services.hedgehog_service import GameError
    offers = NS(find_one=AsyncMock(return_value={
        'chat': -10099, 'bet': 300, 'title': 'Old group', 'status': 'open'}),
        update_one=AsyncMock())
    container = NS(bot=NS(game_chat_id=-10042),
                   mongo_client=NS(database=NS(dojo_duel_offers=offers)))
    with pytest.raises(GameError, match='airchatton'):
        await open_invitation(container, 7, 8, 'old', accept=True)
    offers.update_one.assert_not_awaited()
