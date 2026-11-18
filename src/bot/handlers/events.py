"""
📡 Обработчики событий чата.
"""

from aiogram import Router, F
import logging
import html
from aiogram.types import ChatMemberUpdated, Message
from aiogram.filters import ChatMemberUpdatedFilter, IS_NOT_MEMBER, IS_MEMBER

from src.core.container import Container
from src.core.visuals import Visuals
from src.texts.phrases import get_random_welcome, get_random_ban_phrase, get_random_phrase

router = Router(name="events")

async def _send_welcome_message(user, container: Container, event):
    """Приветствует нового участника без проверки и ограничения прав."""
    if user.is_bot:
        return
    
    try:
        chat_type = getattr(event, "chat", None).type if hasattr(event, "chat") else None
        if chat_type == "channel":
            return
    except Exception:
        pass

    # Создаём пользователя
    registration = await container.user_service.get_or_create(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name or "",
        last_name=user.last_name
    )

    # Приветствие
    username = user.username or user.first_name or f"User {user.id}"
    welcome_text = Visuals.welcome_message(
        name=username,
        phrase=get_random_welcome(username)
    )

    try:
        await event.answer(welcome_text, parse_mode="HTML")
    except Exception as e:
        logging.error(f"❌ Failed to send welcome message: {e}")

    # Existing profiles and rejoins never receive a second starter kit.
    if not registration.get('created'):
        return
    # Отправляем сообщение о стартовых бонусах
    try:
        bonus_text = Visuals.welcome_bonus_message(name=username, coins=registration["user"]["coins"])
        await event.answer(bonus_text, parse_mode="HTML")
    except Exception as e:
        logging.error(f"❌ Failed to send welcome bonus message: {e}")

@router.message(F.new_chat_members)
async def on_new_chat_members(message: Message, container: Container):
    """Обработка входа новых участников (через сообщение)."""
    if message.chat.type not in ("group", "supergroup"):
        return
    logging.info(f"📨 New chat members message: {[u.id for u in message.new_chat_members]}")
    for user in message.new_chat_members:
        # Разбаниваем в боте, если пользователь вернулся в чат (был забанен при выходе)
        unban_result = await container.moderation_service.unban_user(user.id)
        if unban_result["success"]:
            logging.info(f"🔓 User {user.id} auto-unbanned on rejoin (was banned in DB)")
            try:
                mention = f"<b>{html.escape(user.full_name)}</b>"
                await message.answer(
                    f"🔓 <b>Авто-разбан</b>\n\n"
                    f"{mention} разбанен автоматически при возвращении в чат.",
                    parse_mode="HTML"
                )
            except Exception as e:
                logging.error(f"❌ Failed to send auto-unban message: {e}")

        await _send_welcome_message(user, container, message)

@router.chat_member(ChatMemberUpdatedFilter(IS_NOT_MEMBER >> IS_MEMBER))
async def on_user_join(event: ChatMemberUpdated, container: Container):
    """Обработка входа нового участника (через обновление статуса)."""
    if event.chat.type not in ("group", "supergroup"):
        return
    logging.info(f"👤 User join event: {event.new_chat_member.user.id} ({event.new_chat_member.user.username})")

    user = event.new_chat_member.user

    # Разбаниваем в боте, если пользователь вернулся в чат (был забанен при выходе)
    unban_result = await container.moderation_service.unban_user(user.id)
    if unban_result["success"]:
        logging.info(f"🔓 User {user.id} auto-unbanned on rejoin (was banned in DB)")
        try:
            mention = f"<b>{html.escape(user.full_name)}</b>"
            await event.answer(
                f"🔓 <b>Авто-разбан</b>\n\n"
                f"{mention} разбанен автоматически при возвращении в чат.",
                parse_mode="HTML"
            )
        except Exception as e:
            logging.error(f"❌ Failed to send auto-unban message: {e}")

    await _send_welcome_message(user, container, event)

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
