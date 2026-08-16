"""
🛡️ Обработчики админских команд.
"""

import time
import html
import asyncio
from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, MessageOriginChannel
import logging

logger = logging.getLogger(__name__)
from aiogram.fsm.context import FSMContext

from src.bot.filters import AdminFilter
from src.bot.states.govori import GovoriState
from src.core.config import settings
from src.core.container import Container
from src.core.visuals import Visuals
from src.bot.keyboards.broadcast import broadcast_menu_kb
from src.bot.keyboards.inline import VisualsCb
from src.texts.phrases import get_random_ban_phrase

router = Router(name="admin_commands")
router.message.filter(AdminFilter())
router.callback_query.filter(AdminFilter())


def get_admin_help() -> str:
    """🛡️ Справка для админов"""
    w = 28
    lines = [
        Visuals.frame_top_left(w),
        Visuals.frame_line_left("🛡️ АДМИН-ПАНЕЛЬ v2.3", w, "center"),
        Visuals.frame_separator_left(w),
        Visuals.frame_line_left("» СПРАВКА", w),
        Visuals.frame_line_left("◦ /adminhelp", w),
        Visuals.frame_line_left("◦ /health (status)", w),
        Visuals.frame_separator_left(w),
        Visuals.frame_line_left("» КОНТЕНТ", w),
        Visuals.frame_line_left("◦ /addquestion", w),
        Visuals.frame_line_left("◦ /senseiviktorina", w),
        Visuals.frame_line_left("◦ /stopquiz", w),
        Visuals.frame_line_left("◦ /senseiboss [time]", w),
        Visuals.frame_line_left("◦ /killboss", w),
        Visuals.frame_line_left("◦ /bossiks [multiplier]", w),
        Visuals.frame_line_left("◦ /senseivesti", w),
        Visuals.frame_line_left("◦ /senseivestnik", w),
        Visuals.frame_line_left("◦ /senseistat", w),
        Visuals.frame_line_left("◦ /cancel", w),
        Visuals.frame_separator_left(w),
        Visuals.frame_line_left("» СОЗЫВ И РАЗДАЧА", w),
        Visuals.frame_line_left("◦ /senseizov", w),
        Visuals.frame_line_left("◦ /senseinezov", w),
        Visuals.frame_line_left("◦ /+fire [сумма]", w),
        Visuals.frame_line_left("◦ /SENSEISANSARA", w),
        Visuals.frame_separator_left(w),
        Visuals.frame_line_left("» НАГРАДЫ", w),
        Visuals.frame_line_left("◦ /bonussensei", w),
        Visuals.frame_line_left("◦ /addticket (reply)", w),
        Visuals.frame_line_left("◦ /addcoin (reply)", w),
        Visuals.frame_line_left("◦ /addxp (reply)", w),
        Visuals.frame_line_left("◦ /addkatana (reply)", w),
        Visuals.frame_line_left("◦ /ticketburn (reply)", w),
        Visuals.frame_separator_left(w),
        Visuals.frame_line_left("» КОММУНИКАЦИЯ", w),
        Visuals.frame_line_left("◦ /govori (лс)", w),
        Visuals.frame_line_left("◦ /broadcast", w),
        Visuals.frame_separator_left(w),
        Visuals.frame_line_left("» МОДЕРАЦИЯ", w),
        Visuals.frame_line_left("◦ /banlist", w),
        Visuals.frame_line_left("◦ /бан", w),
        Visuals.frame_line_left("◦ /unban @username", w),
        Visuals.frame_line_left("◦ /amnistia", w),
        Visuals.frame_line_left("◦ /senseimuteon", w),
        Visuals.frame_line_left("◦ /senseimuteoff", w),
        Visuals.frame_line_left("◦ /offexit | /onexit", w),
        Visuals.frame_separator_left(w),
        Visuals.frame_line_left("» СИСТЕМА", w),
        Visuals.frame_line_left("◦ /senseichats", w),
        Visuals.frame_line_left("◦ /senseinewSeasons", w),
        Visuals.frame_line_left("◦ /topticket", w),
        Visuals.frame_line_left("◦ /adminstats", w),
        Visuals.frame_line_left("◦ /senseibank", w),
        Visuals.frame_line_left("◦ /sensei work [мин]", w),
        Visuals.frame_line_left("◦ /sensei [fix|deploy]", w),
        Visuals.frame_line_left("◦ /sensei done", w),
        Visuals.frame_separator_left(w),
        Visuals.frame_line_left("⚡ ROOT ACCESS: ENABLED", w, "center"),
        Visuals.frame_bottom_left(w),
    ]
    return "<pre>\n" + "\n".join(lines) + "\n</pre>"


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    """Отмена текущего действия."""
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("ℹ️ Нет активных действий для отмены.")
        return

    await state.clear()
    await message.answer("✅ Действие отменено.", parse_mode="HTML")


@router.message(Command("health", "status"))
async def cmd_health(message: Message, container: Container) -> None:
    """Проверка здоровья системы."""
    start = time.perf_counter()

    # MongoDB Check
    db_status = "❌"
    db_time = 0
    try:
        t0 = time.perf_counter()
        await container.mongo_client.database.command("ping")
        db_time = (time.perf_counter() - t0) * 1000
        db_status = "✅"
    except Exception as e:
        db_status = f"❌ ({str(e)})"

    total_time = (time.perf_counter() - start) * 1000

    msg = (
        f"<b>🏥 System Health</b>\n\n"
        f"🐘 <b>Database:</b> {db_status} <code>{db_time:.2f}ms</code>\n"
        f"⏱ <b>Total Check:</b> <code>{total_time:.2f}ms</code>"
    )
    await message.answer(msg, parse_mode="HTML")


@router.message(Command("senseichats", "chats", "группы"))
async def cmd_admin_chats(message: Message, container: Container):
    """Список групп, где есть бот (из активного мониторинга)."""
    username = message.from_user.username
    mention = f"@{username}" if username else f"<b>{html.escape(message.from_user.full_name)}</b>"

    status_msg = await message.answer("⏳ Собираю информацию о чатах...")

    # Получаем ID чатов из MongoDB через сервис чат-активности
    chat_ids = await container.chat_activity_service.get_all_chat_ids()

    if not chat_ids:
        await status_msg.edit_text(f"{mention}\n\n📂 <b>Список чатов пуст</b>")
        return

    active_chats = []
    error_chats = []

    total = len(chat_ids)
    processed = 0

    for chat_id_bytes in chat_ids:
        processed += 1
        if processed % 10 == 0:
            try:
                await status_msg.edit_text(f"⏳ Обработано {processed}/{total}...")
            except:
                pass

        try:
            chat_id = int(chat_id_bytes)
            chat = await message.bot.get_chat(chat_id)

            invite_link = chat.invite_link or chat.username
            if not invite_link:
                # Попробуем создать или получить ссылку, если есть права (но лучше просто название)
                invite_link = "—"
            else:
                if chat.username:
                    invite_link = f"@{chat.username}"

            chat_title = chat.title or chat.full_name or "Unknown Chat"

            chat_info = {
                "id": chat_id,
                "title": chat_title,
                "type": chat.type,
                "members": await chat.get_member_count(),
                "link": invite_link
            }
            active_chats.append(chat_info)

        except Exception as e:
            err_str = str(e).lower()
            if "kicked" in err_str or "chat not found" in err_str:
                # Автоматически чистим мертвые чаты
                await container.chat_activity_service.remove_chat(chat_id)
                error_chats.append({"id": int(chat_id_bytes), "error": "Kicked/NotFound (Removed)"})
            else:
                error_chats.append({"id": int(chat_id_bytes), "error": str(e)})

    # Формируем отчет
    text = f"📂 <b>АКТИВНЫЕ ГРУППЫ ({len(active_chats)})</b>\n\n"

    for i, chat in enumerate(active_chats, 1):
        link_html = f"<a href='{chat['link']}'>{html.escape(chat['title'])}</a>" if chat['link'] != "—" else html.escape(chat['title'])
        text += f"{i}. {link_html} <code>{chat['id']}</code>\n"
        text += f"    👥 {chat['members']} уч. | {chat['type']}\n"

    if error_chats:
        text += f"\n⚠️ <b>Ошибки доступа ({len(error_chats)}):</b>\n"
        for i, err in enumerate(error_chats[:10], 1):
            text += f"{i}. <code>{err['id']}</code>: {err['error']}\n"
        if len(error_chats) > 10:
            text += f"<i>...и еще {len(error_chats)-10}</i>"

    await status_msg.edit_text(text, parse_mode="HTML", disable_web_page_preview=True)


@router.message(Command("senseiadmin", "adminhelp"))
async def cmd_admin_help(message: Message) -> None:
    """Админ меню."""
    username = message.from_user.username
    user_id = message.from_user.id
    mention = f"@{username}" if username else f"<b>{html.escape(message.from_user.full_name)}</b>"
    logger.info(f"[ADMINHELP] Start processing for user {user_id}")
    try:
        help_text = get_admin_help()
        logger.info(f"[ADMINHELP] Got help text, length={len(help_text)}")
        # First try sending as plain text to avoid HTML issues
        start_send = time.perf_counter()
        await message.answer(f"{mention}\n\n{help_text}")  # plain text
        end_send = time.perf_counter()
        logger.info(f"[ADMINHELP] Sent plain text help successfully in {(end_send - start_send)*1000:.2f} ms")
    except Exception as e:
        logger.error(f"[ADMINHELP] Failed to send admin help message (plain text): {e}")
        try:
            help_text_html = Visuals.escape(help_text)
            start_send_html = time.perf_counter()
            await message.answer(f"{mention}\n\n{help_text_html}", parse_mode="HTML")
            end_send_html = time.perf_counter()
            logger.info(f"[ADMINHELP] Sent HTML help successfully in {(end_send_html - start_send_html)*1000:.2f} ms")
        except Exception as e2:
            logger.error(f"[ADMINHELP] Failed to send admin help message (HTML): {e2}")
            try:
                await message.answer(f"{mention}\n\n/Admin help (error occurred)")
                logger.info(f"[ADMINHELP] Sent fallback message")
            except Exception as e3:
                logger.error(f"[ADMINHELP] Failed to send fallback message: {e3}")


@router.message(Command("adminstats"))
async def cmd_admin_stats(message: Message, container: Container) -> None:
    """Статистика для админа."""
    username = message.from_user.username
    mention = f"@{username}" if username else f"<b>{html.escape(message.from_user.full_name)}</b>"

    stats = await container.stats_service.get_admin_stats()

    text = f"""<pre>
┏━━━━━━━━━━━━━━━━━┓
   📊 СТАТИСТИКА
┗━━━━━━━━━━━━━━━━━┛
</pre>
<b>👥 Пользователи:</b> {stats['users']['total']:,}

<b>🏦 Банк:</b>
• Баланс: {stats['bank']['balance']:,.2f}
• Выдано: {stats['bank']['total_distributed']:,.2f}
• Собрано: {stats['bank']['total_collected']:,.2f}

<b>💰 В обороте:</b> {stats['circulation']:,.2f}
<b>🎫 Активных билетов:</b> {stats['tickets']['active']:,}
<b>💬 Всего сообщений:</b> {stats['messages']['total']:,}"""

    await message.answer(f"{mention}\n\n{text}", parse_mode="HTML")


def _topticket_keyboard(page: int, total: int, page_size: int, owner_id: int) -> InlineKeyboardMarkup:
    buttons = []
    if page > 0:
        buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"topticket:{page-1}:{owner_id}"))
    if (page + 1) * page_size < total:
        buttons.append(InlineKeyboardButton(text="➡️ Далее", callback_data=f"topticket:{page+1}:{owner_id}"))
    if not buttons:
        buttons.append(InlineKeyboardButton(text="↻ Обновить", callback_data=f"topticket:{page}:{owner_id}"))
    return InlineKeyboardMarkup(inline_keyboard=[buttons])


def _render_topticket(items: list[dict], page: int, total: int, page_size: int) -> str:
    if total == 0:
        return "🎫 <b>Нет активных билетов</b>"
    pages = (total + page_size - 1) // page_size
    lines = [f"🎫 <b>Владельцы билетов</b>\nСтраница {page+1}/{pages}\n"]
    start_idx = page * page_size
    for i, it in enumerate(items, start=1):
        num = start_idx + i
        uname = it.get("username") or f"User {it['user_id']}"
        lines.append(f"{num}. {uname} — {it['tickets']}")
    return "\n".join(lines)


@router.message(Command("topticket"))
async def cmd_topticket(message: Message, container: Container):
    page_size = 20
    page = 0
    data = await container.user_service.get_ticket_holders_paginated(page=page, page_size=page_size)
    text = _render_topticket(data["items"], page, data["total"], page_size)
    kb = _topticket_keyboard(page, data["total"], page_size, message.from_user.id)
    await message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data.startswith("topticket:"))
async def cb_topticket(cb: CallbackQuery, container: Container):
    parts = cb.data.split(":")
    if len(parts) < 3:
        try:
            await cb.answer("❌ Ошибка", show_alert=True)
        except TelegramBadRequest:
            pass
        return
    page = int(parts[1])
    owner_id = int(parts[2])
    if cb.from_user.id != owner_id:
        try:
            await cb.answer("⛔ Не для тебя", show_alert=True)
        except TelegramBadRequest:
            pass
        return
    page_size = 20
    data = await container.user_service.get_ticket_holders_paginated(page=page, page_size=page_size)
    text = _render_topticket(data["items"], page, data["total"], page_size)
    kb = _topticket_keyboard(page, data["total"], page_size, owner_id)
    try:
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        await cb.message.answer(text, parse_mode="HTML", reply_markup=kb)

    try:
        await cb.answer()
    except TelegramBadRequest:
        pass


@router.message(Command("addcoin"))
async def cmd_add_coin(message: Message, container: Container):
    """Выдать монеты пользователю."""
    username = message.from_user.username
    mention = f"@{username}" if username else f"<b>{html.escape(message.from_user.full_name)}</b>"

    if not message.reply_to_message or not message.reply_to_message.from_user:
        await message.answer(f"{mention}\n\n⚠️ Ответьте на сообщение пользователя", parse_mode="HTML")
        return

    args = message.text.split()
    if len(args) < 2:
        await message.answer(f"{mention}\n\n⚠️ Укажите количество: /addcoin 100", parse_mode="HTML")
        return

    try:
        amount = float(args[1])
        if amount <= 0:
            raise ValueError()
    except ValueError:
        await message.answer(f"{mention}\n\n⚠️ Укажите корректное число", parse_mode="HTML")
        return

    target_user = message.reply_to_message.from_user

    result = await container.economy_service.admin_add_coins(
        user_id=target_user.id,
        amount=amount,
        admin_id=message.from_user.id
    )

    if result["success"]:
        target_username = target_user.username
        target_mention = f"@{target_username}" if target_username else f"<b>{html.escape(target_user.full_name)}</b>"
        await message.answer(
            f"{mention}\n\n✅ Выдано <b>{amount:,.2f}</b> монет пользователю {target_mention}",
            parse_mode="HTML"
        )
    else:
        await message.answer(f"{mention}\n\n❌ {result.get('error', 'Ошибка')}", parse_mode="HTML")


@router.message(Command("amnistia"))
async def cmd_amnistia(message: Message, container: Container):
    """Амнистия: разбанить всех пользователей."""
    username = message.from_user.username
    mention = f"@{username}" if username else f"<b>{html.escape(message.from_user.full_name)}</b>"

    result = await container.moderation_service.unban_all_users()
    count = result.get("affected", 0)

    await message.answer(
        f"{mention}\n\n✅ Амнистия выполнена\nРазбанено пользователей: <b>{count}</b>",
        parse_mode="HTML"
    )


@router.message(Command("addxp"))
async def cmd_add_xp(message: Message, container: Container):
    """Выдать XP пользователю."""
    username = message.from_user.username
    mention = f"@{username}" if username else f"<b>{html.escape(message.from_user.full_name)}</b>"

    if not message.reply_to_message or not message.reply_to_message.from_user:
        await message.answer(f"{mention}\n\n⚠️ Ответьте на сообщение пользователя", parse_mode="HTML")
        return

    args = message.text.split()
    if len(args) < 2:
        await message.answer(f"{mention}\n\n⚠️ Укажите количество: /addxp 100", parse_mode="HTML")
        return

    try:
        amount = int(args[1])
        if amount <= 0:
            raise ValueError()
    except ValueError:
        await message.answer(f"{mention}\n\n⚠️ Укажите корректное число", parse_mode="HTML")
        return

    target_user = message.reply_to_message.from_user

    result = await container.economy_service.admin_add_xp(
        user_id=target_user.id,
        amount=amount,
        admin_id=message.from_user.id
    )

    if result["success"]:
        target_username = target_user.username
        target_mention = f"@{target_username}" if target_username else f"<b>{target_user.full_name}</b>"
        text = f"✅ Выдано <b>{amount:,}</b> XP пользователю {target_mention}"

        if result.get("level_up"):
            old_level, new_level, level_name = result["level_up"]
            text += f"\n\n⚡ <b>LEVEL UP!</b> → {new_level} ({level_name})"

        await message.answer(f"{mention}\n\n{text}", parse_mode="HTML")
    else:
        await message.answer(f"{mention}\n\n❌ {result.get('error', 'Ошибка')}", parse_mode="HTML")


@router.message(Command("addticket"))
async def cmd_add_ticket(message: Message, container: Container):
    """Выдать билет пользователю."""
    username = message.from_user.username
    mention = f"@{username}" if username else f"<b>{message.from_user.full_name}</b>"

    if not message.reply_to_message or not message.reply_to_message.from_user:
        await message.answer(f"{mention}\n\n⚠️ Ответьте на сообщение пользователя", parse_mode="HTML")
        return

    target_user = message.reply_to_message.from_user

    result = await container.lottery_service.admin_add_ticket(
        user_id=target_user.id,
        admin_id=message.from_user.id
    )

    if result["success"]:
        target_username = target_user.username
        target_mention = f"@{target_username}" if target_username else f"<b>{target_user.full_name}</b>"
        await message.answer(
            f"{mention}\n\n✅ Выдан билет <code>{result['ticket_code']}</code> "
            f"пользователю {target_mention}",
            parse_mode="HTML"
        )
    else:
        await message.answer(f"{mention}\n\n❌ {result.get('error', 'Ошибка')}", parse_mode="HTML")


@router.message(Command("addkatana"))
async def cmd_add_katana(message: Message, container: Container) -> None:
    """Выдать катану пользователю."""
    username = message.from_user.username
    mention = f"@{username}" if username else f"<b>{message.from_user.full_name}</b>"

    if not message.reply_to_message or not message.reply_to_message.from_user:
        await message.answer(f"{mention}\n\n⚠️ Ответьте на сообщение пользователя", parse_mode="HTML")
        return

    args = message.text.split()
    if len(args) < 2:
        await message.answer(f"{mention}\n\n⚠️ Укажите длину катаны (см): /addkatana 25.5", parse_mode="HTML")
        return

    try:
        length = float(args[1])
        if length <= 0:
            raise ValueError()
    except ValueError:
        await message.answer(f"{mention}\n\n⚠️ Укажите корректное число", parse_mode="HTML")
        return

    target_user = message.reply_to_message.from_user

    result = await container.user_service.admin_add_katana(
        user_id=target_user.id,
        length=length,
        admin_id=message.from_user.id
    )

    if result["success"]:
        target_username = target_user.username
        target_mention = f"@{target_username}" if target_username else f"<b>{target_user.full_name}</b>"
        await message.answer(
            f"{mention}\n\n✅ Пользователю {target_mention} выдана катана длиной <b>{length} см</b>",
            parse_mode="HTML"
        )
    else:
        await message.answer(f"{mention}\n\n❌ {result.get('error', 'Ошибка')}", parse_mode="HTML")


@router.message(Command("ticketburn"))
async def cmd_burn_tickets(message: Message, container: Container):
    """Сжечь все билеты пользователя."""
    username = message.from_user.username
    mention = f"@{username}" if username else f"<b>{message.from_user.full_name}</b>"

    if not message.reply_to_message or not message.reply_to_message.from_user:
        await message.answer(f"{mention}\n\n⚠️ Ответьте на сообщение пользователя", parse_mode="HTML")
        return

    target_user = message.reply_to_message.from_user

    result = await container.lottery_service.admin_burn_user_tickets(
        user_id=target_user.id,
        admin_id=message.from_user.id
    )

    if result["success"]:
        target_username = target_user.username
        target_mention = f"@{target_username}" if target_username else f"<b>{target_user.full_name}</b>"
        await message.answer(
            f"{mention}\n\n🔥 Сожжено билетов: <b>{result['burned_count']}</b> "
            f"у пользователя {target_mention}",
            parse_mode="HTML"
        )
    else:
        await message.answer(f"{mention}\n\n❌ {result.get('error', 'Ошибка')}", parse_mode="HTML")


@router.message(Command("bonussensei"))
async def cmd_bonus_sensei(message: Message, container: Container):
    """Розыгрыш билетов."""
    username = message.from_user.username
    mention = f"@{username}" if username else f"<b>{message.from_user.full_name}</b>"

    args = message.text.split()

    winners_count = 1
    if len(args) > 1:
        try:
            winners_count = max(1, min(10, int(args[1])))
        except ValueError:
            pass

    winners = await container.lottery_service.run_lottery(winners_count)

    if not winners:
        await message.answer(f"{mention}\n\n❌ Нет активных билетов для розыгрыша!", parse_mode="HTML")
        return

    text = "<b>🎰 РОЗЫГРЫШ ЗАВЕРШЁН!</b>\n\n<b>Победители:</b>\n"

    for i, winner in enumerate(winners, 1):
        if winner.get("username"):
            mention = f"@{winner['username']}"
        else:
            mention = f"<b>{winner.get('full_name', 'User')}</b>"

        text += f"\n{i}. {mention} — <code>{winner['ticket_code']}</code>"

    text += "\n\n<i>🔥 Билеты сожжены</i>"

    # Отправляем сообщение без удаления
    await message.bot.send_message(message.chat.id, text, parse_mode="HTML")


@router.message(Command("banlist"))
async def cmd_ban_list(message: Message, container: Container):
    """Список забаненных."""
    username = message.from_user.username
    mention = f"@{username}" if username else f"<b>{message.from_user.full_name}</b>"

    banned = await container.moderation_service.get_banned_users()

    if not banned:
        await message.answer(f"{mention}\n\n✅ Нет забаненных пользователей", parse_mode="HTML")
        return

    text = "<b>⛔ Забаненные:</b>\n\n"

    for user in banned[:20]:
        text += f"• <code>{user['user_id']}</code> — {user['username']}\n"
        text += f"  <i>{user['reason']}</i>\n"

    if len(banned) > 20:
        text += f"\n<i>...и ещё {len(banned) - 20}</i>"

    await message.answer(f"{mention}\n\n{text}", parse_mode="HTML")


@router.message(Command("бан", "ban"))
async def cmd_ban(message: Message, container: Container):
    """Забанить пользователя."""
    username = message.from_user.username
    mention = f"@{username}" if username else f"<b>{message.from_user.full_name}</b>"

    args = message.text.split()

    target_user_id = None
    reason = "Нарушение правил"

    # Check reply
    if message.reply_to_message and message.reply_to_message.from_user:
        target_user_id = message.reply_to_message.from_user.id
        if len(args) > 1:
            reason = " ".join(args[1:])
    elif len(args) > 1:
        try:
            target_user_id = int(args[1])
            if len(args) > 2:
                reason = " ".join(args[2:])
        except ValueError:
            pass

    if not target_user_id:
        await message.answer(f"{mention}\n\n⚠️ Ответьте на сообщение или укажите ID: /ban 123456789 причина", parse_mode="HTML")
        return

    result = await container.moderation_service.ban_user(
        user_id=target_user_id,
        reason=reason,
        confiscate_coins=True
    )

    # Try to ban in Telegram chat
    tg_ban_status = ""
    try:
        await message.bot.ban_chat_member(chat_id=message.chat.id, user_id=target_user_id)
        tg_ban_status = "\n🔨 <b>Пользователь исключен из чата</b>"
    except Exception as e:
        logger.warning(f"Failed to kick user {target_user_id}: {e}")
        tg_ban_status = "\n⚠️ <i>Не удалось исключить из чата (нет прав?)</i>"

    if result["success"]:
        target_username = result.get('username')
        target_mention = f"@{target_username}" if target_username else f"<b>User {target_user_id}</b>"

        ban_text = get_random_ban_phrase(target_mention)

        await message.answer(
            f"{mention}\n\n"
            f"⛔ <b>БАН</b>\n\n"
            f"{ban_text}\n"
            f"<i>Причина: {reason}</i>\n"
            f"Конфисковано: {result.get('confiscated', 0):,.2f} монет"
            f"{tg_ban_status}",
            parse_mode="HTML"
        )
    else:
        await message.answer(f"{mention}\n\n❌ {result.get('error', 'Ошибка')}", parse_mode="HTML")


@router.message(Command("разбанить", "unban"))
async def cmd_unban(message: Message, container: Container):
    """Разбанить пользователя."""
    username = message.from_user.username
    mention = f"@{username}" if username else f"<b>{message.from_user.full_name}</b>"

    args = message.text.split()
    user_id = None

    # 1. Reply
    if message.reply_to_message and message.reply_to_message.from_user:
        user_id = message.reply_to_message.from_user.id

    # 2. Argument
    elif len(args) > 1:
        input_value = args[1]

        # Check if username
        if input_value.startswith("@"):
            user_data = await container.user_service.get_user_by_username(input_value)
            if user_data:
                user_id = user_data["id"]
            else:
                await message.answer(f"{mention}\n\n❌ Пользователь {input_value} не найден в базе", parse_mode="HTML")
                return
        else:
            try:
                user_id = int(input_value)
            except ValueError:
                await message.answer(f"{mention}\n\n⚠️ Некорректный ID или username", parse_mode="HTML")
                return

    if not user_id:
        await message.answer(f"{mention}\n\n⚠️ Ответьте на сообщение или укажите ID/username: /unban @user", parse_mode="HTML")
        return

    result = await container.moderation_service.unban_user(user_id)

    # Try to unban in Telegram chat
    tg_unban_status = ""
    try:
        await message.bot.unban_chat_member(chat_id=message.chat.id, user_id=user_id, only_if_banned=True)
        tg_unban_status = "\n🔓 <b>Пользователь разблокирован в чате</b>"
    except Exception as e:
        logger.warning(f"Failed to unban user {user_id} in chat: {e}")
        # If specific error "User is not banned", we can ignore it or show a different message
        # But for now we just don't show success status for TG unban

    if result["success"]:
        await message.answer(f"{mention}\n\n✅ Пользователь разбанен{tg_unban_status}", parse_mode="HTML")
    else:
        await message.answer(f"{mention}\n\n❌ {result.get('error', 'Ошибка')}", parse_mode="HTML")


@router.message(Command("senseimuteon", "addmute", "mute"))
async def cmd_sensei_mute_on(message: Message, container: Container):
    """Замьютить пользователя (по нику или реплаю)."""
    username = message.from_user.username
    mention = f"@{username}" if username else f"<b>{message.from_user.full_name}</b>"

    args = message.text.split()
    hours = 0.0

    # 1. Если реплай
    if message.reply_to_message and message.reply_to_message.from_user:
        target_user = message.reply_to_message.from_user
        target_username_display = target_user.username or target_user.first_name

        # /senseimuteon [часы]
        if len(args) > 1:
            try:
                hours = float(args[1])
            except ValueError:
                pass

        until = None
        if hours > 0:
            until = datetime.utcnow() + timedelta(hours=hours)

        result = await container.moderation_service.mute_user(
            user_id=target_user.id,
            muted_by=message.from_user.id,
            until=until
        )

        if result["success"]:
            duration_text = f"на {hours} часов" if hours > 0 else "<b>навсегда</b>"
            await message.answer(
                f"{mention}\n\n🔇 Пользователь {target_username_display} замьючен {duration_text}.\n"
                f"Все его сообщения будут удаляться.",
                parse_mode="HTML"
            )
        else:
            await message.answer(f"{mention}\n\n❌ {result.get('error', 'Ошибка')}", parse_mode="HTML")

    # 2. Если аргументы: /senseimuteon @username [часы]
    elif len(args) > 1:
        target_username = args[1]

        if len(args) > 2:
            try:
                hours = float(args[2])
            except ValueError:
                await message.answer(f"{mention}\n\n⚠️ Некорректное время", parse_mode="HTML")
                return

        result = await container.moderation_service.mute_user_by_username(target_username, hours=hours)

        if result["success"]:
            duration_text = f"на {hours} часов" if hours > 0 else "<b>навсегда</b>"
            await message.answer(
                f"{mention}\n\n🔇 Пользователь {result['username']} замьючен {duration_text}.\n"
                f"Все его сообщения будут удаляться.",
                parse_mode="HTML"
            )
        else:
            await message.answer(f"{mention}\n\n❌ {result.get('error', 'Ошибка')}", parse_mode="HTML")

    else:
        await message.answer(f"{mention}\n\n⚠️ Использование:\n/senseimuteon (реплай) [часы]\n/senseimuteon @username [часы]", parse_mode="HTML")


@router.message(Command("senseimuteoff", "offmute", "unmute"))
async def cmd_sensei_mute_off(message: Message, container: Container):
    """Снять мьют по нику."""
    username = message.from_user.username
    mention = f"@{username}" if username else f"<b>{message.from_user.full_name}</b>"

    args = message.text.split()
    if len(args) < 2:
        await message.answer(f"{mention}\n\n⚠️ Использование: /senseimuteoff @username", parse_mode="HTML")
        return

    target_username = args[1]

    result = await container.moderation_service.unmute_user_by_username(target_username)

    if result["success"]:
        await message.answer(f"{mention}\n\n🔊 Мьют снят с пользователя {result.get('username', target_username)}", parse_mode="HTML")
    else:
        await message.answer(f"{mention}\n\n❌ {result.get('error', 'Ошибка')}", parse_mode="HTML")


@router.message(Command("senseinewseasons"))
async def cmd_new_season(message: Message, container: Container):
    """Новый сезон."""
    username = message.from_user.username
    mention = f"@{username}" if username else f"<b>{message.from_user.full_name}</b>"

    await message.answer(f"{mention}\n\n⏳ Запуск нового сезона...", parse_mode="HTML")

    result = await container.stats_service.reset_new_season()

    if result["success"]:
        await message.answer(
            f"{mention}\n\n🌸 <b>НОВЫЙ СЕЗОН!</b>\n\n"
            f"Сброшено билетов: {result['tickets_burned']}\n"
            f"Обновлено пользователей: {result['users_reset']}\n\n"
            f"🗡️ Катаны сохранены!",
            parse_mode="HTML"
        )
    else:
        await message.answer(f"{mention}\n\n❌ Ошибка сброса сезона", parse_mode="HTML")


@router.message(Command("senseisansara"))
async def cmd_sansara(message: Message, container: Container):
    """Полный сброс."""
    username = message.from_user.username
    mention = f"@{username}" if username else f"<b>{message.from_user.full_name}</b>"

    await message.answer(f"{mention}\n\n⏳ Запуск полного сброса...", parse_mode="HTML")

    result = await container.stats_service.reset_sansara()

    if result["success"]:
        await message.answer(
            f"{mention}\n\n🔄 <b>САНСАРА ЗАВЕРШЕНА</b>\n\n"
            f"Сброшено билетов: {result['tickets_burned']}\n"
            f"Обновлено пользователей: {result['users_reset']}\n\n"
            f"🗡️ Катаны сохранены!",
            parse_mode="HTML"
        )
    else:
        await message.answer(f"{mention}\n\n❌ Ошибка сброса", parse_mode="HTML")


@router.message(Command("govori"))
async def cmd_govori(message: Message, state: FSMContext):
    """Рассылка сообщения от имени бота."""
    if message.chat.type != "private":
        await message.delete()
        await message.answer("⚠️ Эта команда работает только в личных сообщениях боту.")
        return

    # Собираем список чатов
    chats = set()
    if settings.main_chat_id:
        chats.add(settings.main_chat_id)
    if settings.allowed_chats:
        chats.update(settings.allowed_chats)
    chats.discard(0)

    if not chats:
        await message.answer("❌ Нет настроенных групп для рассылки.")
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[])

    # Кнопка для всех чатов
    keyboard.inline_keyboard.append([
        InlineKeyboardButton(text="📢 Во все чаты", callback_data="govori_select:all")
    ])

    for chat_id in chats:
        try:
            chat_info = await message.bot.get_chat(chat_id)
            title = chat_info.title or f"Chat {chat_id}"
        except Exception:
            title = f"Chat {chat_id}"

        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text=f"💬 {title}", callback_data=f"govori_select:{chat_id}")
        ])

    keyboard.inline_keyboard.append([
        InlineKeyboardButton(text="❌ Отмена", callback_data="govori_select:cancel")
    ])

    await state.set_state(GovoriState.waiting_for_chat_selection)
    await message.answer(
        "📢 <b>Режим вещания</b>\n\n"
        "Выберите чат для отправки сообщения:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.callback_query(GovoriState.waiting_for_chat_selection, F.data.startswith("govori_select:"))
async def process_govori_chat_selection(callback: CallbackQuery, state: FSMContext):
    action = callback.data.split(":")[1]

    if action == "cancel":
        await state.clear()
        await callback.message.edit_text("✅ Вещание отменено.")
        return

    await state.update_data(target_chat_id=action)
    await state.set_state(GovoriState.waiting_for_content)

    target_text = "во все чаты" if action == "all" else "в выбранный чат"

    await callback.message.edit_text(
        f"✍️ <b>Отправка {target_text}</b>\n\n"
        "Отправьте сообщение (текст, фото, видео), и я перешлю его.\n\n"
        "<i>Для отмены введите /cancel</i>",
        parse_mode="HTML"
    )


@router.message(GovoriState.waiting_for_content)
async def process_govori_content(message: Message, state: FSMContext, container: Container):
    """Обработка контента для рассылки."""
    if message.text and (message.text == "❌ Отмена" or message.text.startswith("/cancel")):
        await state.clear()
        await message.answer("✅ Вещание отменено.", reply_markup=None)
        return

    data = await state.get_data()
    target = data.get("target_chat_id", "all")

    # Собираем список чатов
    chats = set()
    if target == "all":
        if settings.main_chat_id:
            chats.add(settings.main_chat_id)
        if settings.allowed_chats:
            chats.update(settings.allowed_chats)
        chats.discard(0)
    else:
        try:
            chats.add(int(target))
        except ValueError:
            pass

    if not chats:
        await message.answer("❌ Нет чатов для отправки.")
        await state.clear()
        return

    await message.answer(f"⏳ Начинаю рассылку в {len(chats)} чатов...", reply_markup=None)

    # Determine if message is a forward from a channel to preserve buttons
    is_channel_forward = False
    src_chat_id = None
    src_message_id = None

    if message.forward_origin and isinstance(message.forward_origin, MessageOriginChannel):
        is_channel_forward = True
        src_chat_id = message.forward_origin.chat.id
        src_message_id = message.forward_origin.message_id

    success = 0
    failed = 0

    for chat_id in chats:
        try:
            sent = False
            # Try to copy from original channel if it's a forward (to keep buttons)
            if is_channel_forward:
                try:
                    await message.bot.copy_message(
                        chat_id=chat_id,
                        from_chat_id=src_chat_id,
                        message_id=src_message_id
                    )
                    sent = True
                except Exception as e:
                    logger.warning(f"Failed to copy from original channel {src_chat_id} to {chat_id}: {e}")

            # Fallback to normal copy if not sent yet
            if not sent:
                await message.copy_to(chat_id)

            success += 1
            # Небольшая задержка чтобы не спамить слишком быстро
            await asyncio.sleep(0.5)
        except Exception as e:
            failed += 1
            # Логируем ошибку
            logger.error(f"❌ Failed to send to {chat_id}: {e}")
            await message.answer(f"⚠️ Ошибка отправки в {chat_id}: {e}")
            pass

    await state.clear()
    await message.answer(
        f"✅ <b>Рассылка завершена!</b>\n\n"
        f"Успешно: {success}\n"
        f"Ошибок: {failed}",
        parse_mode="HTML"
    )


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, container: Container):
    """Рассылка."""
    username = message.from_user.username
    mention = f"@{username}" if username else f"<b>{html.escape(message.from_user.full_name)}</b>"

    cnt = await container.broadcast_service.get_count()
    await message.answer(
        f"{mention}\n\n📢 <b>Рассылка</b>\n\n👥 Получателей: <b>{cnt}</b>",
        reply_markup=broadcast_menu_kb(message.from_user.id),
        parse_mode="HTML"
    )


@router.message(Command("senseivisual"))
async def cmd_sensei_visual(message: Message):
    """Меню настройки визуала."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1. Старый стиль (Рамки)", callback_data=VisualsCb(action="keep", user_id=message.from_user.id).pack())],
        [InlineKeyboardButton(text="2. Новый стиль (Clean)", callback_data=VisualsCb(action="clean", user_id=message.from_user.id).pack())],
        [InlineKeyboardButton(text="3. Crypto Bot (Mobile)", callback_data=VisualsCb(action="crypto", user_id=message.from_user.id).pack())],
    ])

    style_map = {
        "classic": "Старый (С рамками)",
        "clean": "Clean (Без рамок)",
        "crypto": "Crypto Bot (Mobile)"
    }
    current_style = style_map.get(Visuals.STYLE, "Неизвестно")

    await message.answer(
        f"🎨 <b>Настройка визуала</b>\n\n"
        f"Текущий стиль: <b>{current_style}</b>\n\n"
        f"Выберите стиль оформления уведомлений:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.callback_query(VisualsCb.filter())
async def cb_visuals(query: CallbackQuery, callback_data: VisualsCb):
    if query.from_user.id != callback_data.user_id:
        await query.answer("⛔ Это не твое меню!", show_alert=True)
        return

    style_name = ""
    if callback_data.action == "keep":
        Visuals.STYLE = "classic"
        style_name = "Старый (С рамками)"
    elif callback_data.action == "clean":
        Visuals.STYLE = "clean"
        style_name = "Clean (Без рамок)"
    elif callback_data.action == "crypto":
        Visuals.STYLE = "crypto"
        style_name = "Crypto Bot (Mobile)"

    await query.answer(f"✅ Стиль изменен на: {style_name}")

    # Update message
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1. Старый стиль (Рамки)", callback_data=VisualsCb(action="keep", user_id=callback_data.user_id).pack())],
        [InlineKeyboardButton(text="2. Новый стиль (Clean)", callback_data=VisualsCb(action="clean", user_id=callback_data.user_id).pack())],
        [InlineKeyboardButton(text="3. Crypto Bot (Mobile)", callback_data=VisualsCb(action="crypto", user_id=callback_data.user_id).pack())],
    ])

    try:
        await query.message.edit_text(
            f"🎨 <b>Настройка визуала</b>\n\n"
            f"Текущий стиль: <b>{style_name}</b>\n\n"
            f"Выберите стиль оформления уведомлений:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except Exception:
        pass