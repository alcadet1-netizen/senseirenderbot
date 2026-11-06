"""Wire/schema tests use the pinned generated client, never Telegram credentials."""
import hashlib
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.infra.mtproto import bootstrap
from src.infra.mtproto.widgets import MtprotoWidgets, MtprotoWidgetError
from src.bot.native_widgets import send_native_widget


@pytest.fixture(scope='module')
def tl():
    if not (bootstrap.RUNTIME / '.ready').exists():
        pytest.skip('Run python -m src.infra.mtproto.bootstrap first (CI does this explicitly)')
    bootstrap.load_runtime()
    from telethon import types, functions, utils
    return SimpleNamespace(types=types, functions=functions, utils=utils)


def test_official_schema_pinned_and_not_guessed():
    assert hashlib.sha256(bootstrap.SCHEMA.read_bytes()).hexdigest() == bootstrap.SCHEMA_SHA256
    text = bootstrap.SCHEMA.read_text()
    assert '// LAYER 233' in text
    assert 'inputMediaWidget#44f6c04e' in text
    assert 'updateBotWidgetQuery#b373fe68' in text
    assert 'messages.setBotWidgetQueryAnswer#f8cdec6a' in text


def test_source_hash_mismatch_fails_closed(tmp_path):
    with pytest.raises(RuntimeError, match='checksum'):
        bootstrap.unpack_source(b'not a pinned archive', tmp_path)


def test_real_tl_serialization_and_response_decoding(tl):
    from telethon.extensions import BinaryReader
    from telethon.tl.alltlobjects import LAYER
    assert LAYER == 233
    media = tl.types.InputMediaWidget(340, 0, '<html></html>', allow_queries=True, shared_widget=False)
    assert media.CONSTRUCTOR_ID == 0x44f6c04e
    with BinaryReader(bytes(media)) as reader:
        decoded = reader.tgread_object()
    assert decoded.html == media.html and decoded.allow_queries
    result = tl.types.MessageMediaWidget(340, 0, b'compressed', public_data='{}', public_data_hash=12)
    with BinaryReader(bytes(result)) as reader:
        decoded = reader.tgread_object()
    assert decoded.payload == b'compressed' and decoded.public_data_hash == 12
    answer = tl.functions.messages.SetBotWidgetQueryAnswerRequest(query_id=42, result='{}')
    assert answer.CONSTRUCTOR_ID == 0xf8cdec6a


@pytest.mark.asyncio
async def test_mtproto_send_uses_sendmedia_and_never_bot_api(tl):
    client = AsyncMock(return_value='updates')
    client.get_input_entity.return_value = tl.types.InputPeerUser(7, 123)
    transport = MtprotoWidgets(client, None, tl.types, tl.functions, tl.utils)
    container = SimpleNamespace(native_widget_transport=transport)
    bot = AsyncMock()
    assert await send_native_widget(bot, container, 7, '<html>OK</html>') == 'updates'
    bot.assert_not_called()
    request = client.call_args.args[0]
    assert isinstance(request, tl.functions.messages.SendMediaRequest)
    assert isinstance(request.media, tl.types.InputMediaWidget)
    assert request.media.allow_queries and not request.media.shared_widget
    assert request.media.html == '<html>OK</html>' and request.random_id
    assert request.allow_paid_floodskip is None and request.allow_paid_stars is None


@pytest.mark.asyncio
async def test_missing_peer_does_not_use_fake_access_hash(tl):
    client = AsyncMock()
    client.get_input_entity.side_effect = ValueError('not cached')
    transport = MtprotoWidgets(client, None, tl.types, tl.functions, tl.utils)
    with patch('src.infra.mtproto.widgets.asyncio.sleep', new_callable=AsyncMock):
        with pytest.raises(MtprotoWidgetError, match='PEER_NOT_CACHED'):
            await transport.send_widget(7, '<html>OK</html>')
    assert client.get_input_entity.call_count == 5
    client.assert_not_called()


@pytest.mark.asyncio
async def test_rpc_denial_preserved_without_request_repr(tl):
    class Denied(Exception):
        message = 'INPUT_MEDIA_WIDGET_NOT_ALLOWED'
    client = AsyncMock(side_effect=Denied('sensitive request repr'))
    client.get_input_entity.return_value = tl.types.InputPeerUser(7, 123)
    transport = MtprotoWidgets(client, None, tl.types, tl.functions, tl.utils)
    with pytest.raises(MtprotoWidgetError, match='INPUT_MEDIA_WIDGET_NOT_ALLOWED') as error:
        await transport.send_widget(7, '<html>SECRET</html>')
    assert 'SECRET' not in str(error.value) and 'sensitive' not in str(error.value)


@pytest.mark.asyncio
async def test_selected_mtproto_never_silently_falls_back():
    container = SimpleNamespace(settings=SimpleNamespace(native_widget_transport='mtproto'))
    bot = AsyncMock()
    with pytest.raises(MtprotoWidgetError, match='NOT_READY'):
        await send_native_widget(bot, container, 7, 'html')
    bot.assert_not_called()


@pytest.mark.asyncio
async def test_rejects_size_before_resolving_peer(tl):
    client = AsyncMock()
    transport = MtprotoWidgets(client, None, tl.types, tl.functions, tl.utils)
    with pytest.raises(MtprotoWidgetError):
        await transport.send_widget(7, '\x00bad')
    client.get_input_entity.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize('won', [True, False])
async def test_authenticated_mtproto_queries_use_existing_economy_once(tl, won):
    from tests.unit.test_hedgehog_game import services
    db, daily, game = services()
    token = (await game.issue(7))['token']
    container = SimpleNamespace(settings=SimpleNamespace(maintenance_mode=False), hedgehog_service=game)
    client = AsyncMock(return_value=True)
    transport = MtprotoWidgets(client, container, tl.types, tl.functions, tl.utils)
    def query(action):
        return tl.types.UpdateBotWidgetQuery(
            query_id=42, query_type=tl.types.WidgetQueryTypeData(), user_id=7,
            peer=tl.types.PeerUser(7), msg_id=55, chat_instance=123, chat_type='private',
            data=f'hg:{action}:{token}'.encode(),
        )
    with patch('src.services.hedgehog_service.time.time', return_value=100), \
         patch('src.services.hedgehog_service.secrets.randbelow', return_value=0 if won else 99):
        await transport.on_update(query('s'))
    assert json.loads(client.call_args.args[0].result)['state'] == 'playing'
    with patch('src.services.hedgehog_service.time.time', return_value=112):
        await transport.on_update(query('f'))
        await transport.on_update(query('f'))
    request = client.call_args.args[0]
    assert isinstance(request, tl.functions.messages.SetBotWidgetQueryAnswerRequest)
    result = json.loads(request.result)['result']
    assert result['success'] is won
    assert len(db.users.writes) == 1
    assert db.users.docs[7]['coins'] == 1000 + result['total_coins']
    assert db.users.docs[7]['xp'] == 500 + result['total_xp']
    if not won:
        assert db.users.docs[7]['daily_streak'] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['copy', 'wallet', 'other_owner', 'invalid_utf8'])
async def test_mtproto_requests_reject_untrusted_or_wallet_actions(tl, kind):
    from tests.unit.test_hedgehog_game import services
    db, daily, game = services()
    token = (await game.issue(7))['token']
    container = SimpleNamespace(settings=SimpleNamespace(maintenance_mode=False), hedgehog_service=game)
    client = AsyncMock()
    transport = MtprotoWidgets(client, container, tl.types, tl.functions, tl.utils)
    common = dict(query_id=42, query_type=tl.types.WidgetQueryTypeData(with_wallet=kind == 'wallet'),
                  user_id=8 if kind == 'other_owner' else 7,
                  data=b'\xff' if kind == 'invalid_utf8' else f'hg:s:{token}'.encode())
    query = (tl.types.UpdateBotWidgetCopyQuery(**common, widget_id=12) if kind == 'copy' else
             tl.types.UpdateBotWidgetQuery(**common, peer=tl.types.PeerUser(7), msg_id=55,
                                           chat_instance=12, chat_type='private'))
    await transport.on_update(query)
    assert 'error' in json.loads(client.call_args.args[0].result)
    assert not db.users.writes
    assert next(iter(db.hedgehog_games.docs.values()))['state'] == 'issued'


@pytest.mark.asyncio
async def test_missing_credentials_or_beta_fails_before_login():
    settings = SimpleNamespace(telegram_widget_beta=False, telegram_api_id=0)
    with pytest.raises(RuntimeError, match='require TELEGRAM_API_ID'):
        await MtprotoWidgets.start(SimpleNamespace(settings=settings), 7)
    settings.telegram_widget_beta = True
    with pytest.raises(RuntimeError, match='cannot be combined'):
        await MtprotoWidgets.start(SimpleNamespace(settings=settings), 7)


@pytest.mark.asyncio
async def test_memory_session_bot_login_identity_check_and_shutdown(tl):
    from pydantic import SecretStr
    settings = SimpleNamespace(telegram_widget_beta=False, telegram_api_id=123,
                               telegram_api_hash=SecretStr('not-a-real-hash'), bot_token='123456:TEST')
    client = AsyncMock()
    client.add_event_handler = lambda *args: None
    client.get_me.return_value = SimpleNamespace(bot=True, id=123456)
    with patch('telethon.TelegramClient', return_value=client) as constructor:
        transport = await MtprotoWidgets.start(SimpleNamespace(settings=settings), 123456)
    from telethon.sessions import MemorySession
    assert isinstance(constructor.call_args.args[0], MemorySession)
    client.sign_in.assert_awaited_once_with(bot_token='123456:TEST')
    await transport.close()
    client.disconnect.assert_awaited_once()
    client.get_me.return_value = SimpleNamespace(bot=True, id=999)
    client.reset_mock()
    with patch('telethon.TelegramClient', return_value=client):
        with pytest.raises(RuntimeError, match='connection failed'):
            await MtprotoWidgets.start(SimpleNamespace(settings=settings), 123456)
    client.disconnect.assert_awaited_once()
