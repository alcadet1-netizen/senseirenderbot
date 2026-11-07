"""Native via-bot group route: real TL objects, authenticated queries and receipts."""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.infra.mtproto.widgets import MtprotoWidgets, MtprotoWidgetError
from tests.unit.test_mtproto_widgets import tl, connected_client
from tests.unit.test_hedgehog_game import services


def setup(tl):
    db, daily, game = services()
    game.reward_mode = 'pet_once'
    container = SimpleNamespace(
        settings=SimpleNamespace(maintenance_mode=False, BASE_DIR=Path(__file__).resolve().parents[2]),
        hedgehog_service=game)
    client = connected_client(return_value=True)
    transport = MtprotoWidgets(client, container, tl.types, tl.functions, tl.utils)
    # Historical protocol tests retain the retired builder explicitly. Production clears inline results.
    transport.answer_inline_hedgehog = transport.answer_legacy_inline_hedgehog
    return db, game, container, client, transport


def search(tl, query='ежа', offset='', user_id=7):
    return tl.types.UpdateBotInlineQuery(query_id=123, user_id=user_id, query=query, offset=offset,
                                        peer_type=tl.types.InlineQueryPeerTypeMegagroup())


@pytest.mark.asyncio
async def test_native_inline_search_builds_real_tl_media_without_starting_game(tl):
    from telethon.extensions import BinaryReader
    db, game, container, client, transport = setup(tl)
    await transport.on_update(search(tl))
    request = client.call_args.args[0]
    assert isinstance(request, tl.functions.messages.SetInlineBotResultsRequest)
    assert request.private and request.cache_time == 0 and request.query_id == 123
    assert len(request.results) == 1
    result = request.results[0]
    assert result.type == 'article'  # Matches upstream native-widget inline conformance bot.
    assert isinstance(result.send_message, tl.types.InputBotInlineMessageWidget)
    assert result.send_message.allow_queries and not result.send_message.shared_widget
    assert 'TelegramWidget.request' in result.send_message.html
    assert 'WebApp' not in result.send_message.html
    with BinaryReader(bytes(request)) as reader:
        decoded = reader.tgread_object()
    assert decoded.results[0].send_message.html == result.send_message.html
    assert not db.users.writes
    invitation = next(iter(db.hedgehog_games.docs.values()))
    assert invitation['state'] == 'issued' and 'started_at' not in invitation
    await transport.on_update(search(tl))
    assert len(db.hedgehog_games.docs) == 1
    assert client.call_args.args[0].results[0].id == result.id
    client.get_input_entity.assert_not_called()  # No direct send/guessed destination peer.


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['banned', 'no_profile', 'claimed', 'maintenance', 'offset'])
async def test_unavailable_inline_game_has_no_playable_result_or_reward(tl, kind):
    from src.services.hedgehog_service import utc_day
    db, game, container, client, transport = setup(tl)
    if kind == 'banned':
        db.users.docs[7]['is_banned'] = True
    elif kind == 'no_profile':
        db.users.docs.clear()
    elif kind == 'claimed':
        db.users.docs[7]['hedgehog_day'] = utc_day()
    elif kind == 'maintenance':
        container.settings.maintenance_mode = True
    await transport.on_update(search(tl, offset='next' if kind == 'offset' else ''))
    assert client.call_args.args[0].results == []
    assert not db.users.writes and not db.hedgehog_games.docs


@pytest.mark.asyncio
async def test_other_inline_searches_are_not_hijacked(tl):
    db, game, container, client, transport = setup(tl)
    await transport.on_update(search(tl, query='other command'))
    client.assert_not_called()
    assert not db.hedgehog_games.docs


def widget_query(tl, token, action, user_id=7, wallet=False, data=None):
    return tl.types.UpdateInlineBotWidgetQuery(
        query_id=42, query_type=tl.types.WidgetQueryTypeData(with_wallet=wallet),
        user_id=user_id, inline_message_id=tl.types.InputBotInlineMessageID64(2, 7, 55, 123),
        chat_instance=123, chat_type='supergroup',
        data=data if data is not None else f'hg:{action}:{token}'.encode())


@pytest.mark.asyncio
@pytest.mark.parametrize('petted', [False, True])
async def test_authenticated_inline_group_game_pays_once_with_same_rules(tl, petted):
    db, game, container, client, transport = setup(tl)
    token = (await game.issue(7))['token']
    with patch('src.services.hedgehog_service.time.time', return_value=100):
        await transport.on_update(widget_query(tl, token, 's'))
        assert json.loads(client.call_args.args[0].result)['remaining_ms'] == 7000
        if petted:
            await transport.on_update(widget_query(tl, token, 't1'))
            await transport.on_update(widget_query(tl, token, 't2'))
            assert json.loads(client.call_args.args[0].result)['taps'] == 1
    with patch('src.services.hedgehog_service.time.time', return_value=107):
        await transport.on_update(widget_query(tl, token, 'f'))
        first = json.loads(client.call_args.args[0].result)
        await transport.on_update(widget_query(tl, token, 'f'))
    assert json.loads(client.call_args.args[0].result) == first
    assert first['result']['success']
    assert first['result']['tap_count'] == int(petted)
    assert (first['result']['tap_bonus_coins'] > 0) is petted
    assert len(db.users.writes) == 1
    assert db.users.docs[7]['coins'] == 1000 + first['result']['total_coins']


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['other_owner', 'wallet', 'invalid_utf8'])
async def test_inline_wallet_foreign_owner_and_malformed_actions_rejected(tl, kind):
    db, game, container, client, transport = setup(tl)
    token = (await game.issue(7))['token']
    await transport.on_update(widget_query(tl, token, 's', user_id=8 if kind == 'other_owner' else 7,
                                          wallet=kind == 'wallet', data=b'\xff' if kind == 'invalid_utf8' else None))
    assert 'error' in json.loads(client.call_args.args[0].result)
    assert not db.users.writes
    assert next(iter(db.hedgehog_games.docs.values()))['state'] == 'issued'


@pytest.mark.asyncio
async def test_group_policy_rejection_offers_native_inline_not_private_or_webapp(tl):
    from src.bot.presenters.hedgehog_presenter import launch_legacy_hedgehog as launch_hedgehog
    db, game, container, client, transport = setup(tl)
    container.native_widget_transport = transport
    container.user_service = SimpleNamespace(get_or_create=AsyncMock())
    client.get_input_entity.return_value = tl.types.InputPeerChannel(123, 456)
    # The rejection is not retried; another RPC is only possible after explicit inline selection.
    client.side_effect = MtprotoWidgetError('INPUT_MEDIA_WIDGET_NOT_ALLOWED')
    bot = AsyncMock()
    bot.get_chat_member.return_value = SimpleNamespace(status='administrator')
    bot.get_chat.return_value = SimpleNamespace(permissions=None)
    message = SimpleNamespace(chat=SimpleNamespace(id=-100123, type='supergroup'), bot=bot, answer=AsyncMock())
    user = SimpleNamespace(id=7, username=None, first_name='Ёж', last_name=None, is_bot=False)
    await launch_hedgehog(message, user, container)
    button = message.answer.call_args.kwargs['reply_markup'].inline_keyboard[0][0]
    assert button.switch_inline_query_current_chat == 'ежа'
    assert button.url is None and button.web_app is None
    assert client.call_count == 1
    assert not db.users.writes
    assert next(iter(db.hedgehog_games.docs.values()))['state'] == 'issued'


@pytest.mark.asyncio
async def test_inline_rpc_policy_failure_is_logged_safely_without_retry(tl, caplog):
    db, game, container, client, transport = setup(tl)
    client.side_effect = MtprotoWidgetError('INPUT_MEDIA_WIDGET_NOT_ALLOWED')
    await transport.on_update(search(tl))
    assert client.call_count == 1
    assert 'widget_policy' in caplog.text and 'INPUT_MEDIA_WIDGET_NOT_ALLOWED' in caplog.text
    assert not db.users.writes
    token = next(iter(db.hedgehog_games.docs.values()))['token']
    assert token not in caplog.text


@pytest.mark.asyncio
async def test_inline_build_failure_answers_empty_without_starting_game(tl):
    db, game, container, client, transport = setup(tl)
    with patch('src.widgets.hedgehog.to_hedgehog_html', side_effect=ValueError('too large')):
        await transport.on_update(search(tl))
    assert client.call_args.args[0].results == []
    assert not db.users.writes
    assert next(iter(db.hedgehog_games.docs.values()))['state'] == 'issued'


@pytest.mark.asyncio
async def test_inline_and_direct_copies_share_one_financial_receipt(tl):
    db, game, container, client, transport = setup(tl)
    token = (await game.issue(7))['token']
    with patch('src.services.hedgehog_service.time.time', return_value=100):
        await transport.on_update(widget_query(tl, token, 's'))
        await transport.on_update(widget_query(tl, token, 't1'))
    with patch('src.services.hedgehog_service.time.time', return_value=107):
        direct = tl.types.UpdateBotWidgetQuery(
            query_id=43, query_type=tl.types.WidgetQueryTypeData(), user_id=7,
            peer=tl.types.PeerUser(7), msg_id=2, chat_instance=456, chat_type='private',
            data=f'hg:f:{token}'.encode())
        await transport.on_update(direct)
        direct_result = json.loads(client.call_args.args[0].result)
        await transport.on_update(widget_query(tl, token, 'f'))
    assert json.loads(client.call_args.args[0].result) == direct_result
    assert len(db.users.writes) == 1
