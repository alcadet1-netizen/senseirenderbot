"""Best-effort fallback for confirmed joins received by the bot's MTProto session.

Only the configured discussion group is eligible; a request, promotion, leave,
or a stale update is never sufficient to grant a starter kit.
"""
import logging
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from src.bot.handlers.events import _clear_pending_join, _handle_join
from src.bot.middlewares.group_admin import group_admin_access

logger = logging.getLogger(__name__)


def participant_is_member(participant, types):
    if participant is None:
        return False
    if isinstance(participant, (types.ChannelParticipant, types.ChannelParticipantSelf,
                                types.ChannelParticipantAdmin, types.ChannelParticipantCreator)):
        return True
    return isinstance(participant, types.ChannelParticipantBanned) and not participant.left


async def handle_channel_participant(update, transport):
    types, container = transport.types, transport.container
    chat_id = transport.utils.get_peer_id(types.PeerChannel(update.channel_id))
    if not container.settings.discussion_chat_id or chat_id != container.settings.discussion_chat_id:
        return
    if participant_is_member(update.prev_participant, types) or not participant_is_member(update.new_participant, types):
        return
    stamp = update.date
    if not isinstance(stamp, datetime):
        return
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    if not now - timedelta(minutes=5) <= stamp <= now + timedelta(minutes=1):
        logger.info('MTProto join ignored: stale or future event chat=%s user=%s', chat_id, update.user_id)
        return
    logger.info('MTProto join ingress chat=%s user=%s', chat_id, update.user_id)
    bot = container.bot
    try:
        if not await group_admin_access.allowed(bot, chat_id):
            logger.warning('MTProto join skipped: bot admin not verified chat=%s', chat_id)
            return
        member = await bot.get_chat_member(chat_id, update.user_id)
        present = member.status in ('member', 'administrator', 'creator') or (
            member.status == 'restricted' and getattr(member, 'is_member', False))
        if not present or member.user.is_bot:
            logger.info('MTProto join skipped: membership not confirmed chat=%s user=%s', chat_id, update.user_id)
            return

        async def answer(text, **kwargs):
            return await bot.send_message(chat_id, text, **kwargs)

        event = SimpleNamespace(chat=SimpleNamespace(id=chat_id, type='supergroup'), answer=answer)
        await _handle_join(member.user, container, event)
        await _clear_pending_join(container, chat_id, update.user_id)
    except Exception:
        logger.exception('MTProto join processing failed chat=%s user=%s', chat_id, update.user_id)
