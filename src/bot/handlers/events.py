"""
📡 Обработчики событий чата.
"""

from aiogram import Router, F
import logging
import html
from aiogram.types import ChatMemberUpdated, Message
from aiogram.filters import ChatMemberUpdatedFilter, IS_NOT_MEMBER, IS_MEMBER

from src.core.container import Container
from src.texts.phrases import get_random_ban_phrase, get_random_phrase, get_random_welcome

router = Router(name="events")

async def _answer_join(event, text):
    # Use the bot directly for membership updates: there is no source message
    # to reply to and some aiogram versions lack the event.answer shortcut.
    if isinstance(event, ChatMemberUpdated):
        await event.bot.send_message(event.chat.id, text, parse_mode="HTML")
    else:
        await event.answer(text, parse_mode="HTML")


async def _send_welcome_message(user, container: Container, event):
    """Greet a joined user. Joining never registers and never pays a reward.

    The starter kit belongs to the first message a player writes in the chat
    (see EconomyService.process_message_reward). Creating the profile here
    would reserve and credit the kit for someone who only walked in, so the
    join path is greeting-only.
    """
    if user.is_bot or event.chat.type not in ("group", "supergroup"):
        return

    name = " ".join((user.first_name or f"User {user.id}").split())[:80]
    mention = f'<a href="tg://user?id={user.id}">{html.escape(name)}</a>'
    try:
        # Legacy templates prefix usernames with @; the HTML mention already
        # links to the person, including those without a Telegram username.
        greeting = get_random_welcome(mention).replace(f"@{mention}", mention)
        await _answer_join(event, greeting)
        logging.info("Join welcome sent chat=%s user=%s", event.chat.id, user.id)
    except Exception:
        logging.exception("Unable to send welcome to chat %s for user %s", event.chat.id, user.id)


async def _clear_pending_join(container, chat_id, user_id):
    watch = getattr(container, "__dict__", {}).get("_join_request_watch")
    if watch is not None:
        try:
            await watch.confirmed(chat_id, user_id)
        except Exception:
            logging.exception("Unable to clear pending join chat=%s user=%s", chat_id, user_id)


async def _handle_join(user, container: Container, event):
    if user.is_bot:
        return
    # Telegram may deliver both chat_member and new_chat_members for one join.
    # A short, Mongo-backed window avoids duplicate greetings across workers.
    # This lock is not used for money: profile creation is still the only grant.
    try:
        first = await container.throttle_service.throttle(
            key=f"{event.chat.id}:{user.id}", limit_seconds=15, scope="join_welcome")
        if not first:
            logging.info("Join welcome duplicate suppressed chat=%s user=%s", event.chat.id, user.id)
            return
    except Exception:
        logging.exception("Join deduplication unavailable for chat %s", event.chat.id)

    try:
        unban_result = await container.moderation_service.unban_user(user.id)
        if unban_result.get("success"):
            mention = html.escape(user.full_name or user.first_name or f"User {user.id}")
            try:
                await _answer_join(event, f"🔓 <b>Авто-разбан</b>\n\n<b>{mention}</b> разбанен автоматически при возвращении в чат.")
            except Exception:
                logging.exception("Unable to send auto-unban notice for user %s", user.id)
    except Exception:
        logging.exception("Unable to check auto-unban for user %s", user.id)
    # A confirmed join is enough for a group mention; no private /start needed.
    try:
        await container.chat_activity_service.update_user_activity(event.chat.id, user.id)
    except Exception:
        logging.exception('Could not record joined member chat=%s', event.chat.id)
    await _send_welcome_message(user, container, event)


@router.message(F.new_chat_members)
async def on_new_chat_members(message: Message, container: Container):
    """Handle Telegram service messages for confirmed joins."""
    if message.chat.type not in ("group", "supergroup"):
        return
    for user in message.new_chat_members:
        await _handle_join(user, container, message)
        await _clear_pending_join(container, message.chat.id, user.id)


@router.chat_member(ChatMemberUpdatedFilter(IS_NOT_MEMBER >> IS_MEMBER))
async def on_user_join(event: ChatMemberUpdated, container: Container):
    """Handle confirmed membership changes, including approved join requests."""
    if event.chat.type not in ("group", "supergroup"):
        return
    await _handle_join(event.new_chat_member.user, container, event)
    await _clear_pending_join(container, event.chat.id, event.new_chat_member.user.id)


@router.chat_member(ChatMemberUpdatedFilter(IS_MEMBER >> IS_NOT_MEMBER))
async def on_user_leave(event: ChatMemberUpdated, container: Container):
    """Обработка выхода участника (автобан)."""
    user = event.old_chat_member.user

    if user.is_bot:
        return

    # Автобан и конфискация
    result = await container.moderation_service.handle_user_left(user.id)
    if result.get('success'):
        # The bank tab shows confiscated coins; do not wait up to a minute for
        # the cached admin snapshot to expire.
        stats = getattr(container, 'stats_service', None)
        invalidate = getattr(stats, 'invalidate', None)
        if invalidate is not None:
            invalidate()

    # Проверяем настройки уведомлений (по умолчанию включены)
    key = f"chat:{event.chat.id}:exit_notifications"
    enabled = await container.chat_settings_service.get_setting(event.chat.id, key)
    if enabled == "0":
        return

    # Указываем имя пользователя без тега
    mention = f"<b>{html.escape(user.full_name)}</b>"

    if result.get("success"):
        # Не отправляем сообщения в каналах (спам и часто нет прав)
        if event.chat.type == "channel":
            return

        try:
            ban_text = get_random_ban_phrase(mention)
            phrase = get_random_phrase()
            await event.answer(
                f"⚠️ <b>АВТОБАН</b>\n\n"
                f"{ban_text}\n"
                f"Конфисковано: {result.get('confiscated', 0):,.2f} монет\n\n"
                f"<i>{phrase}</i>",
                parse_mode="HTML"
            )
        except Exception as e:
            logging.error(f"❌ Failed to send autoban message: {e}")
