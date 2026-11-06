"""Optional bot-only MTProto transport for native HTMLBubbles, layer 233."""
import asyncio
import logging
import secrets

logger = logging.getLogger(__name__)


class MtprotoWidgetError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(message)


class MtprotoWidgets:
    def __init__(self, client, container, types, functions, utils):
        self.client, self.container = client, container
        self.types, self.functions, self.utils = types, functions, utils

    @classmethod
    async def start(cls, container, bot_id):
        settings = container.settings
        if settings.telegram_widget_beta:
            raise RuntimeError('MTProto mode cannot be combined with the Bot API beta/test mode')
        if not settings.telegram_api_id or not settings.telegram_api_hash.get_secret_value():
            raise RuntimeError('MTProto widgets require TELEGRAM_API_ID and TELEGRAM_API_HASH in the server environment')
        from .bootstrap import load_runtime
        await asyncio.to_thread(load_runtime)
        from telethon import TelegramClient, types, functions, utils, events
        from telethon.sessions import MemorySession
        # No user login, phone number, OTP, saved StringSession, or disk auth key.
        client = TelegramClient(MemorySession(), settings.telegram_api_id,
                                settings.telegram_api_hash.get_secret_value(),
                                flood_sleep_threshold=0, request_retries=1)
        transport = cls(client, container, types, functions, utils)
        client.add_event_handler(transport.on_update, events.Raw())
        try:
            await client.connect()
            await client.sign_in(bot_token=settings.bot_token)
            me = await client.get_me()
            if not me.bot or me.id != bot_id:
                raise RuntimeError('MTProto and Bot API identities must be the SAME bot')
        except asyncio.CancelledError:
            await client.disconnect()
            raise
        except Exception:
            await client.disconnect()
            # Do not expose constructor parameters or authorization errors.
            raise RuntimeError('MTProto bot connection failed; check credentials, network and Telegram access') from None
        logger.info('Native widget transport connected: MTProto layer 233, bot-only memory session')
        return transport

    async def close(self):
        await self.client.disconnect()

    async def send_widget(self, chat_id, html, *, allow_queries=True):
        import zlib
        encoded = html.encode('utf-8')
        if '\x00' in html or len(encoded) > 32768 or len(zlib.compress(encoded, 9)) > 4096:
            raise MtprotoWidgetError('INPUT_MEDIA_WIDGET_HTML_INVALID_OR_TOO_LARGE')
        # An incoming MTProto update caches the access_hash. Bot API may handle
        # the same command a fraction earlier. Never invent a zero access_hash.
        peer = None
        for attempt in range(5):
            try:
                peer = await self.client.get_input_entity(chat_id)
                break
            except ValueError:
                if attempt < 4:
                    await asyncio.sleep(.25)
            except Exception as exc:
                raise MtprotoWidgetError(getattr(exc, 'message', type(exc).__name__)) from None
        if peer is None:
            raise MtprotoWidgetError('PEER_NOT_CACHED: send a new message to the bot in this chat and retry')
        request = self.functions.messages.SendMediaRequest(
            peer=peer, media=self.types.InputMediaWidget(
                width=340, height=0, html=html, allow_queries=allow_queries, shared_widget=False,
            ), message='🦔 Погладь ежа · 12 секунд', random_id=secrets.randbits(63) or 1,
        )
        try:
            return await self.client(request)
        except Exception as exc:
            # RPC .message is an error code, not the request repr containing HTML.
            raise MtprotoWidgetError(getattr(exc, 'message', type(exc).__name__)) from None

    async def __call__(self, method):
        # Adapter for the existing authenticated widget-query handler.
        from src.bot.native_widgets import AnswerWidgetQuery
        if not isinstance(method, AnswerWidgetQuery):
            raise TypeError('Only widget-query answers are allowed on this adapter')
        return await self.client(self.functions.messages.SetBotWidgetQueryAnswerRequest(
            query_id=int(method.widget_query_id), result=method.data,
        ))

    async def on_update(self, update):
        from aiogram.types import Update
        from src.bot.native_widgets import HedgehogWidgetMiddleware
        if not isinstance(update, (self.types.UpdateBotWidgetQuery,
                                   self.types.UpdateInlineBotWidgetQuery,
                                   self.types.UpdateBotWidgetCopyQuery)):
            return
        try:
            # We send only original, non-shared widgets. Never process wallet,
            # inline or forwarded-copy requests as game actions.
            allowed = (isinstance(update, self.types.UpdateBotWidgetQuery)
                       and isinstance(update.query_type, self.types.WidgetQueryTypeData)
                       and not update.query_type.with_wallet
                       and update.wallet_card is None)
            if not allowed:
                await self.client(self.functions.messages.SetBotWidgetQueryAnswerRequest(
                    query_id=update.query_id, result='{"error":"Вызови /senseidaily для своей игры."}',
                ))
                return
            try:
                value = update.data.decode('utf-8', errors='strict')
            except UnicodeDecodeError:
                value = ''
            # All identity/message coordinates come from authenticated MTProto
            # updates. The HTML supplies only the untrusted 64-byte action.
            query = {'id': str(update.query_id), 'from': {'id': update.user_id},
                     'chat': {'id': self.utils.get_peer_id(update.peer), 'type': update.chat_type},
                     'message_id': update.msg_id, 'data': value}
            event = Update.model_validate({'update_id': 0, 'widget_query': query})
            async def unused_handler(event, data):
                return None
            await HedgehogWidgetMiddleware(self.container)(unused_handler, event, {'bot': self})
        except Exception:
            # Do not dump the raw event, wallet data, credentials or request HTML.
            logger.error('MTProto widget query failed; retry from the original widget')
