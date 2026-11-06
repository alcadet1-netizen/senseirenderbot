"""Optional bot-only MTProto transport for native HTMLBubbles, layer 233."""
import asyncio
import logging
import secrets
import traceback
from pathlib import Path

logger = logging.getLogger(__name__)


class MtprotoWidgetError(Exception):
    def __init__(self, message, *, stage=None, category=None):
        self.stage, self.category = stage, category
        self.message = message
        super().__init__(message)


class MtprotoWidgets:
    def __init__(self, client, container, types, functions, utils):
        self.client, self.container = client, container
        self.types, self.functions, self.utils = types, functions, utils
        self._connection_lock = asyncio.Lock()
        self._generation = 0
        self._closed = False
        self.inline_enabled = None

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
            transport.inline_enabled = getattr(me, 'bot_inline_placeholder', None) is not None
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

    CONNECT_TIMEOUT = 5
    RPC_TIMEOUT = 5

    def _connected(self):
        return bool(self.client.is_connected())

    def _background_failure(self):
        error = getattr(self.client, '_updates_error', None)
        if isinstance(error, BaseException):
            # TypeNotFoundError.__str__ contains raw Telegram bytes. Never use it.
            code = getattr(error, 'invalid_constructor_id', None)
            detail = type(error).__name__
            if isinstance(code, int):
                detail += f' constructor=0x{code & 0xffffffff:08x}'
            frames = traceback.extract_tb(error.__traceback__)
            if frames:
                frame = frames[-1]
                detail += f' at={Path(frame.filename).name}:{frame.lineno}:{frame.name}'
            return detail
        task = getattr(self.client, '_updates_handle', None)
        if (isinstance(task, asyncio.Future) and task.done() and self._connected()
                and not self._connection_lock.locked()):
            return 'UpdateTaskStopped'
        return None

    def diagnostic_status(self):
        failure = self._background_failure()
        return (f'MTProto: connected={self._connected()}, closed={self._closed}, '
                f'updates={failure or "no_failure_recorded"}, recovering={self._connection_lock.locked()}, '
                f'reconnect_generation={self._generation}, inline_enabled={self.inline_enabled}')

    def _check_ready(self, stage):
        if self._closed:
            raise MtprotoWidgetError('MTPROTO_CLOSED', stage=stage, category='transport_closed')
        failure = self._background_failure()
        if failure:
            raise MtprotoWidgetError(f'MTPROTO_UPDATES_FAILED: {failure}; layer=233',
                                     stage=stage, category='transport_runtime')

    @staticmethod
    def _failure(exc, stage):
        if isinstance(exc, MtprotoWidgetError):
            return exc
        constructor = getattr(exc, 'invalid_constructor_id', None)
        if isinstance(constructor, int):
            return MtprotoWidgetError(
                f'MTPROTO_DECODE_FAILED: {type(exc).__name__} constructor=0x{constructor & 0xffffffff:08x}; layer=233',
                stage=stage, category='transport_runtime')
        if isinstance(exc, (ConnectionError, OSError, asyncio.TimeoutError)):
            # No exception str: URLs, tokens and payload may be included there.
            return MtprotoWidgetError(f'{type(exc).__name__}; stage={stage}',
                                      stage=stage, category='temporary')
        return MtprotoWidgetError(getattr(exc, 'message', type(exc).__name__), stage=stage)

    async def _ensure_connection(self, stage, *, failed_generation=None):
        self._check_ready(stage)
        if failed_generation is None and self._connected() and not self._connection_lock.locked():
            return
        task = asyncio.create_task(self._recover_locked(stage, failed_generation))
        # disconnect() may cancel Telethon's current event-handler task. Keep
        # recovery alive independently so an answer-path disconnect cannot
        # cancel its own reconnect. Consume errors if the caller is cancelled.
        task.add_done_callback(lambda done: None if done.cancelled() else done.exception())
        await asyncio.shield(task)

    async def _recover_locked(self, stage, failed_generation):
        async with self._connection_lock:
            self._check_ready(stage)
            # Another request has already recovered this connection.
            if self._connected() and (failed_generation is None or failed_generation != self._generation):
                return
            logger.warning('MTProto connection recovery stage=%s generation=%s connected=%s',
                           stage, self._generation, self._connected())
            async def recover():
                await self.client.disconnect()
                await self.client.connect()
                # Authenticated round-trip; never create a user login or rotate
                # bot credentials merely to hide a network interruption.
                await self.client(self.functions.updates.GetStateRequest())
            try:
                await asyncio.wait_for(recover(), timeout=self.CONNECT_TIMEOUT)
                if not self._connected():
                    raise ConnectionError('not connected after recovery')
                self._check_ready(stage)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                raise self._failure(exc, 'reconnect_probe') from None
            self._generation += 1
            logger.info('MTProto connection recovered generation=%s', self._generation)

    async def _request(self, request, stage):
        return await self._network_call(lambda: self.client(request), stage)

    async def _network_call(self, call, stage, *, preserve_value_error=False):
        # Reuse the SAME request/random_id on an ambiguous network failure.
        # Telegram deduplicates sendMedia by random_id; a second ID is unsafe.
        await self._ensure_connection(stage)
        for attempt in range(2):
            generation = self._generation
            try:
                return await asyncio.wait_for(call(), timeout=self.RPC_TIMEOUT)
            except (ConnectionError, OSError, asyncio.TimeoutError) as exc:
                self._check_ready(stage)
                if attempt:
                    raise self._failure(exc, stage) from None
                await self._ensure_connection(stage, failed_generation=generation)
            except ValueError as exc:
                if preserve_value_error:
                    raise
                raise self._failure(exc, stage) from None
            except Exception as exc:
                # Policy/auth/flood/schema RPC errors are never blindly replayed.
                raise self._failure(exc, stage) from None

    async def close(self):
        self._closed = True
        async with self._connection_lock:
            await self.client.disconnect()

    async def send_widget(self, chat_id, html, *, allow_queries=True):
        import zlib
        encoded = html.encode('utf-8')
        if '\x00' in html or len(encoded) > 32768 or len(zlib.compress(encoded, 9)) > 4096:
            raise MtprotoWidgetError('INPUT_MEDIA_WIDGET_HTML_INVALID_OR_TOO_LARGE')
        await self._ensure_connection('resolve_peer')
        # An incoming MTProto update caches the access_hash. Bot API may handle
        # the same command a fraction earlier. Never invent a zero access_hash.
        peer = None
        for attempt in range(5):
            try:
                peer = await self._network_call(lambda: self.client.get_input_entity(chat_id),
                                                'resolve_peer', preserve_value_error=True)
                break
            except ValueError:
                if attempt < 4:
                    await asyncio.sleep(.25)
            except Exception as exc:
                raise self._failure(exc, 'resolve_peer') from None
        if peer is None:
            raise MtprotoWidgetError('PEER_NOT_CACHED: send a new message to the bot in this chat and retry')
        request = self.functions.messages.SendMediaRequest(
            peer=peer, media=self.types.InputMediaWidget(
                width=340, height=0, html=html, allow_queries=allow_queries, shared_widget=False,
            ), message='🦔 Погладь ежа · 7 секунд', random_id=secrets.randbits(63) or 1,
        )
        return await self._request(request, 'send_media')

    async def __call__(self, method):
        # Adapter for the existing authenticated widget-query handler.
        from src.bot.native_widgets import AnswerWidgetQuery
        if not isinstance(method, AnswerWidgetQuery):
            raise TypeError('Only widget-query answers are allowed on this adapter')
        return await self._request(self.functions.messages.SetBotWidgetQueryAnswerRequest(
            query_id=int(method.widget_query_id), result=method.data,
        ), 'answer_query')

    async def answer_inline_hedgehog(self, update):
        """Official via-bot native media; user explicitly selects it in a chat."""
        from src.core.exceptions import DailyAlreadyClaimedError
        from src.services.hedgehog_service import GameError
        from src.services.maintenance_service import MaintenanceService
        from src.widgets.hedgehog import to_hedgehog_html
        from src.widgets.limits import RENDER_SLOTS

        if update.query.strip().casefold() not in {'ежа', 'ёж', 'еж', 'hedgehog'}:
            return
        results = []
        if (not update.offset and not self.container.settings.maintenance_mode
                and not MaintenanceService.is_enabled()):
            try:
                # Existing authenticated profile only. Opening inline search never
                # starts the clock, changes XP/coins or consumes the daily claim.
                game = await self.container.hedgehog_service.issue(update.user_id)
                async with RENDER_SLOTS:
                    html = await asyncio.to_thread(
                        to_hedgehog_html, game['token'],
                        self.container.settings.BASE_DIR / 'src/infra/storage/ega',
                    )
                results.append(self.types.InputBotInlineResult(
                    id='hedgehog_' + game['token'], type='article',
                    title='🦔 Погладь ежа · 7 секунд',
                    description='Нативный виджет в этом чате. Одно поглаживание — +10% монет.',
                    send_message=self.types.InputBotInlineMessageWidget(
                        width=340, height=0, html=html, allow_queries=True,
                        shared_widget=False, message='🦔 Погладь ежа · 7 секунд',
                    ),
                ))
            except (GameError, DailyAlreadyClaimedError):
                pass  # No profile, banned, already claimed: never offer a playable result.
            except (OSError, ValueError):
                logger.error('Native inline hedgehog HTML build failed')
        # Never cache a personal token for other users (or for the next UTC day).
        accepted = await self._request(self.functions.messages.SetInlineBotResultsRequest(
            query_id=update.query_id, results=results, cache_time=0, private=True,
        ), 'answer_inline_hedgehog')
        logger.info('Native inline hedgehog results: accepted=%s count=%d', bool(accepted), len(results))
        return accepted

    async def on_update(self, update):
        if isinstance(update, self.types.UpdateBotInlineQuery):
            self.inline_enabled = True
            from src.bot.widget_diagnostics import WIDGET_TRANSPORT_ERRORS, describe_failure
            try:
                await self.answer_inline_hedgehog(update)
            except WIDGET_TRANSPORT_ERRORS as exc:
                describe_failure(exc)  # Sanitized category/reference; never HTML, token or raw update.
            except Exception:
                logger.error('Native inline hedgehog result failed; no daily reward issued')
            return
        from aiogram.types import Update
        from src.bot.native_widgets import HedgehogWidgetMiddleware
        if not isinstance(update, (self.types.UpdateBotWidgetQuery,
                                   self.types.UpdateInlineBotWidgetQuery,
                                   self.types.UpdateBotWidgetCopyQuery)):
            return
        try:
            # Direct and via-bot originals use authenticated Telegram identity.
            # Forwarded copies and wallet requests are never game actions.
            allowed = (isinstance(update, (self.types.UpdateBotWidgetQuery,
                                           self.types.UpdateInlineBotWidgetQuery))
                       and isinstance(update.query_type, self.types.WidgetQueryTypeData)
                       and not update.query_type.with_wallet
                       and update.wallet_card is None)
            if not allowed:
                await self._request(self.functions.messages.SetBotWidgetQueryAnswerRequest(
                    query_id=update.query_id, result='{"error":"Вызови /senseidaily для своей игры."}',
                ), 'reject_query')
                return
            try:
                value = update.data.decode('utf-8', errors='strict')
            except UnicodeDecodeError:
                value = ''
            # All identity/message coordinates come from authenticated MTProto
            # updates. The HTML supplies only the untrusted 64-byte action.
            query = {'id': str(update.query_id), 'from': {'id': update.user_id}, 'data': value}
            if isinstance(update, self.types.UpdateInlineBotWidgetQuery):
                # Opaque authenticated coordinates, NOT an invented chat/message ID.
                query['inline_message_id'] = bytes(update.inline_message_id).hex()
                query['chat_type'] = update.chat_type
            else:
                query['chat'] = {'id': self.utils.get_peer_id(update.peer), 'type': update.chat_type}
                query['message_id'] = update.msg_id
            event = Update.model_validate({'update_id': 0, 'widget_query': query})
            async def unused_handler(event, data):
                return None
            await HedgehogWidgetMiddleware(self.container)(unused_handler, event, {'bot': self})
        except Exception:
            # Do not dump the raw event, wallet data, credentials or request HTML.
            logger.error('MTProto widget query failed; retry from the original widget')
