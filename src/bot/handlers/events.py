"""
📡 Обработчики событий чата.
"""

from aiogram import Router, F
import logging
import html
import asyncio
from aiogram.types import ChatMemberUpdated, Message, ChatPermissions, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import ChatMemberUpdatedFilter, IS_NOT_MEMBER, IS_MEMBER

from src.core.container import Container
from src.core.visuals import Visuals
from src.texts.phrases import get_random_welcome, get_random_ban_phrase, get_random_phrase

router = Router(name="events")

async def _send_welcome_message(user, container: Container, event):
    """Отправляет приветствие (бывшая _welcome_user). Вызывается ПОСЛЕ капчи."""
    if user.is_bot:
        return
    
    try:
        chat_type = getattr(event, "chat", None).type if hasattr(event, "chat") else None
        if chat_type == "channel":
            return
    except Exception:
        pass

    # Создаём пользователя
    await container.user_service.get_or_create(
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

async def _wait_for_captcha(bot, chat_id, user_id, message_id, container):
    """Фоновая задача ожидания капчи."""
    try:
        await asyncio.sleep(20) # 20 секунд на решение
        
        # Проверяем, решена ли капча
        is_solved = await container.captcha_service.get_solved(user_id)
        if is_solved:
            return
            
        # Не решена - Кик и удаление сообщения
        logging.info(f"🚫 Captcha timeout for user {user_id}. Kicking.")
        try:
            # Сначала пробуем удалить сообщение с капчей
            try:
                await bot.delete_message(chat_id, message_id)
            except Exception:
                pass

            # Баним и разбаниваем (кик)
            await bot.ban_chat_member(chat_id, user_id)
            await bot.unban_chat_member(chat_id, user_id)
            
        except Exception as e:
            logging.error(f"❌ Failed to kick user {user_id} (captcha timeout): {e}")
            
    except Exception as e:
        logging.error(f"Error in captcha wait task: {e}")

async def _initiate_captcha(user, container: Container, event):
    """Инициирует процесс капчи: мьют, сообщение, таймер."""
    if user.is_bot:
        return

    # Проверка блокировки (чтобы не запускать дважды для одного входа)
    lock_key = f"captcha:lock:{event.chat.id}:{user.id}"
    # Используем captcha service для атомарной проверки
    if not await container.captcha_service.set_lock(event.chat.id, user.id, 30):
        return

    logging.info(f"🔒 Initiating captcha for {user.id} in {event.chat.id}")

    # 1. Мьют (Restrict)
    try:
        await event.chat.restrict(
            user.id,
            permissions=ChatPermissions(
                can_send_messages=False,
                can_send_media_messages=False,
                can_send_other_messages=False,
                can_add_web_page_previews=False
            )
        )
    except Exception as e:
        logging.warning(f"⚠️ Could not mute user {user.id}: {e}")
        # Если не смогли замьютить (например, админ зашел или нет прав), 
        # все равно показываем капчу, но кик сработает если что.

    # 2. Отправка сообщения с кнопкой
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤖 Я не робот", callback_data=f"captcha:{user.id}")]
    ])
    
    # Формируем текст
    mention = f"<a href='tg://user?id={user.id}'>{html.escape(user.first_name or 'User')}</a>"
    text = (
        f"👋 Привет, {mention}!\n\n"
        f"🛡 <b>Проверка на бота</b>\n"
        f"Нажмите кнопку ниже в течение <b>20 секунд</b>, чтобы получить доступ к чату.\n"
        f"<i>Иначе вы будете исключены.</i>"
    )
    
    try:
        # Используем event.answer, который работает и для Message и для ChatMemberUpdated (если контекст позволяет)
        # Для ChatMemberUpdated event.answer отправляет сообщение в чат события.
        msg = await event.answer(text, reply_markup=kb, parse_mode="HTML")
        
        # 3. Запуск таймера
        # Важно передать bot явно, так как event.bot доступен
        asyncio.create_task(_wait_for_captcha(event.bot, event.chat.id, user.id, msg.message_id, container))
        
    except Exception as e:
        logging.error(f"❌ Failed to send captcha message: {e}")

@router.message(F.new_chat_members)
async def on_new_chat_members(message: Message, container: Container):
    """Обработка входа новых участников (через сообщение)."""
    logging.info(f"📨 New chat members message: {[u.id for u in message.new_chat_members]}")
    for user in message.new_chat_members:
        await _initiate_captcha(user, container, message)

@router.chat_member(ChatMemberUpdatedFilter(IS_NOT_MEMBER >> IS_MEMBER))
async def on_user_join(event: ChatMemberUpdated, container: Container):
    """Обработка входа нового участника (через обновление статуса)."""
    logging.info(f"👤 User join event: {event.new_chat_member.user.id} ({event.new_chat_member.user.username})")
    
    user = event.new_chat_member.user
    
    # ⚠️ КОСТЫЛЬ: Aiogram 3.x иногда не прокидывает container в chat_member handler
    await _initiate_captcha(user, container, event)

@router.callback_query(F.data.startswith("captcha:"))
async def on_captcha_solve(query: CallbackQuery, container: Container):
    """Обработка нажатия кнопки капчи."""
    try:
        target_user_id = int(query.data.split(":")[1])
    except (ValueError, IndexError):
        await query.answer("Ошибка данных", show_alert=True)
        return

    if query.from_user.id != target_user_id:
        await query.answer("⛔ Эту кнопку может нажать только тот, кого проверяют!", show_alert=True)
        return

    # 1. Помечаем как решенную
    await container.captcha_service.set_solved(target_user_id, 300)
    
    # 2. Разблокируем (Unmute) - возвращаем стандартные права
    try:
        await query.message.chat.restrict(
            target_user_id,
            permissions=ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
                can_send_polls=True,
                can_invite_users=True,
                can_pin_messages=False,
                can_change_info=False,
            )
        )
    except Exception as e:
        logging.warning(f"⚠️ Failed to unmute user {target_user_id}: {e}")

    # 3. Удаляем сообщение с капчей
    try:
        await query.message.delete()
    except Exception:
        pass

    # 4. Отправляем приветствие
    # Используем query.message для ответа, но user берем из query.from_user
    await _send_welcome_message(query.from_user, container, query.message)
    
    # Отвечаем на колбэк, чтобы убрать часики (хотя сообщение удалено, но на всякий случай)
    try:
        await query.answer("✅ Вы прошли проверку!")
    except Exception:
        pass

@router.chat_member(ChatMemberUpdatedFilter(IS_MEMBER >> IS_NOT_MEMBER))
async def on_user_leave(event: ChatMemberUpdated, container: Container):
    """Обработка выхода участника (автобан)."""
    user = event.old_chat_member.user

    if user.is_bot:
        return

    # Автобан и конфискация
    result = await container.moderation_service.handle_user_left(user.id)

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
