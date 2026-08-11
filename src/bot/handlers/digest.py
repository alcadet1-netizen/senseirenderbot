import asyncio
import html
from datetime import datetime, timedelta

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.enums import ParseMode

from src.core.container import Container
from src.core.config import settings
from src.core.visuals import Visuals
from src.bot.keyboards.inline import DigestCb
from src.bot.utils import check_owner

router = Router(name="digest")

async def do_generate_digest(chat_id: int, bot: Bot, container: Container, auto: bool = False):
    """Основная функция генерации"""
    
    # Check if already generating (simple lock in service or here?)
    # Service has 'generating' set but it's per instance. Container is singleton so service is singleton.
    if chat_id in container.digest_service.generating:
        return
    
    container.digest_service.generating.add(chat_id)
    
    try:
        # Собираем данные
        chat_log = container.digest_service.format_for_llm(chat_id, 500)
        stats = container.digest_service.get_stats(chat_id)
        topics = container.digest_service.get_topics(chat_id)
        msg_count = len(container.digest_service.get_messages(chat_id))
        
        # Анонс
        if auto:
            announcement = await container.digest_service.generate_short_reaction(f"накопилось {msg_count} сообщений в чате")
            status_msg = await bot.send_message(chat_id, announcement)
        else:
            status_msg = await bot.send_message(
                chat_id,
                f"🗞️ Сенсей читает {msg_count} сообщений...\n"
                "Подождите, он пытается понять какого хуя тут происходит."
            )
        
        # Печатаем...
        await bot.send_chat_action(chat_id, "typing")
        
        # Генерируем
        digest = await container.digest_service.generate_digest(chat_log, stats, topics, msg_count)
        
        # Удаляем статус
        try:
            await status_msg.delete()
        except:
            pass
        
        # Отправляем результат (разбиваем если длинный)
        if len(digest) > 4000:
            parts = [digest[i:i+4000] for i in range(0, len(digest), 4000)]
            for i, part in enumerate(parts):
                if i == 0:
                    await bot.send_message(chat_id, part)
                else:
                    await asyncio.sleep(0.5)
                    await bot.send_message(chat_id, part)
        else:
            await bot.send_message(chat_id, digest)
        
        # Отмечаем что сделали
        container.digest_service.mark_digest_done(chat_id)
        
    finally:
        container.digest_service.generating.discard(chat_id)


@router.message(Command("senseivesti", "вестник", "digest"))
async def cmd_digest(message: Message, container: Container):
    """Ручной вызов меню сводки"""
    chat_id = message.chat.id
    
    username = message.from_user.username
    mention = f"@{username}" if username else f"<b>{html.escape(message.from_user.full_name)}</b>"

    # Проверка типа чата
    if message.chat.type == "private":
        await message.reply(
            f"{mention}\n\n"
            "❌ Сенсей работает только в групповых чатах!\n"
            "Добавь меня в группу, ученик."
        )
        return

    # Проверка прав администратора
    if message.from_user.id not in settings.admin_ids:
        await message.reply(
            f"{mention}\n\n"
            "⛔ <b>Доступ запрещен!</b>\n"
            "Эту команду может использовать только Сенсей (админ)."
        )
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Балдой", callback_data=DigestCb(mode="baldoi", user_id=message.from_user.id).pack()),
            InlineKeyboardButton(text="На Вайбе", callback_data=DigestCb(mode="vestnik", user_id=message.from_user.id).pack())
        ]
    ])
    
    await message.reply(
        f"{mention}\n\n"
        "Выберите режим генерации сводки:",
        reply_markup=keyboard
    )


@router.callback_query(DigestCb.filter(F.mode == "baldoi"))
async def callback_digest_baldoi(callback: CallbackQuery, callback_data: DigestCb, container: Container):
    chat_id = callback.message.chat.id
    user = callback.from_user
    username = user.username
    mention = f"@{username}" if username else f"<b>{html.escape(user.full_name)}</b>"
    
    if not await check_owner(callback, callback_data.user_id):
        return

    if user.id not in settings.admin_ids:
        await callback.answer("⛔ Доступ запрещен!", show_alert=True)
        return
    
    # Проверка кулдауна
    can, remaining = container.digest_service.can_generate(chat_id)
    if not can:
        mins = remaining // 60
        secs = remaining % 60
        await callback.message.answer(
            f"{mention}\n\n"
            f"⏳ Сенсей отдыхает. Подожди ещё {mins}м {secs}с\n"
            "Не еби мозги старику, он только что делал сводку."
        )
        await callback.answer()
        return
    
    # Проверка количества сообщений
    msg_count = len(container.digest_service.get_messages(chat_id))
    
    if msg_count < 10: 
        await callback.message.answer(
            f"{mention}\n\n"
            f"📭 Всего {msg_count} сообщений? Это даже не смешно.\n"
            "Наберите хотя бы 10, тогда сенсею будет что анализировать.\n"
            "А пока — идите общайтесь, дегенераты."
        )
        await callback.answer()
        return
    
    await callback.message.delete()
    await container.digest_service.trigger_digest(chat_id, callback.message.bot, auto=False)
    await callback.answer()


@router.callback_query(DigestCb.filter(F.mode == "vestnik"))
async def callback_digest_vestnik(callback: CallbackQuery, callback_data: DigestCb, container: Container):
    chat_id = callback.message.chat.id
    user = callback.from_user
    username = user.username
    mention = f"@{username}" if username else f"<b>{html.escape(user.full_name)}</b>"
    
    if not await check_owner(callback, callback_data.user_id):
        return

    if user.id not in settings.admin_ids:
        await callback.answer("⛔ Доступ запрещен!", show_alert=True)
        return
        
    msg_count = len(container.digest_service.get_messages(chat_id))
    
    if msg_count < 5: 
        await callback.message.answer(
            f"{mention}\n\n"
            f"📭 Всего {msg_count} сообщений? Маловато для эпоса.\n"
        )
        await callback.answer()
        return
    
    await callback.message.delete()
    await container.digest_service.trigger_vestnik(chat_id, callback.message.bot)
    await callback.answer()


@router.message(Command("senseivestnik"))
async def cmd_vestnik(message: Message, container: Container):
    """Ручной вызов ВЕРХОВНОГО СЕНСЕЯ (GROQ)"""
    chat_id = message.chat.id
    username = message.from_user.username
    mention = f"@{username}" if username else f"<b>{html.escape(message.from_user.full_name)}</b>"

    # Проверка типа чата
    if message.chat.type == "private":
        await message.reply(
            f"{mention}\n\n"
            "❌ Сенсей работает только в групповых чатах!"
        )
        return

    # Проверка прав администратора
    if message.from_user.id not in settings.admin_ids:
        await message.reply(
            f"{mention}\n\n"
            "⛔ <b>Доступ запрещен!</b>\n"
            "Эту команду может использовать только ВЕРХОВНЫЙ (админ)."
        )
        return
    
    # Проверка количества сообщений
    msg_count = len(container.digest_service.get_messages(chat_id))
    
    if msg_count < 5: 
        await message.reply(
            f"{mention}\n\n"
            f"📭 Всего {msg_count} сообщений? Маловато для эпоса.\n"
        )
        return
    
    await container.digest_service.trigger_vestnik(chat_id, message.bot)


@router.message(Command("senseistat", "статс", "stats"))
async def cmd_stats(message: Message, container: Container):
    """Статистика чата"""
    chat_id = message.chat.id
    username = message.from_user.username
    mention = f"@{username}" if username else f"<b>{html.escape(message.from_user.full_name)}</b>"

    stats = container.digest_service.get_stats(chat_id)
    msg_count = len(container.digest_service.get_messages(chat_id))
    new_count = container.digest_service.get_new_messages_count(chat_id)
    
    if not stats:
        await message.reply(f"{mention}\n\n📭 Пусто. Тишина. Как у вас в головах.")
        return
    
    sorted_stats = sorted(stats.items(), key=lambda x: -x[1]['count'])
    
    w = Visuals.FRAME_W_MENU
    lines = [
        Visuals.frame_top_left(w),
        Visuals.frame_line_left("📊 СТАТИСТИКА", w, "center"),
        Visuals.frame_separator_left(w),
        Visuals.frame_line_left(f"📝 Всего: {msg_count}", w),
        Visuals.frame_line_left(f"🆕 Новых: {new_count}", w),
        Visuals.frame_line_left(f"🎯 Лимит: {container.settings.auto_digest_threshold}", w),
        Visuals.frame_separator_left(w),
        Visuals.frame_line_left("🏆 ТОП АКТИВНЫХ", w, "center"),
        Visuals.frame_separator_left(w),
    ]
    
    medals = ["🥇", "🥈", "🥉"]
    
    for i, (name, data) in enumerate(sorted_stats[:10]):
        rank_str = medals[i] if i < 3 else f"{i+1}."
        count = data['count']
        
        # Format: "1. Name...   123"
        val_str = str(count)
        
        # Calculate spacing similar to top_table
        available_w = w - 4
        max_name_len = available_w - len(rank_str) - len(val_str) - 2
        if max_name_len < 3:
            max_name_len = 3
            
        safe_name = Visuals.escape(name)
        short_name = safe_name[:max_name_len]
        
        left_part = f"{rank_str} {short_name}"
        spaces_count = max(1, available_w - len(left_part) - len(val_str))
        
        full_row = f"{left_part}{' ' * spaces_count}{val_str}"
        lines.append(Visuals.frame_line_left(full_row, w))
        
    lines.append(Visuals.frame_bottom_left(w))
    
    table = "<pre>\n" + "\n".join(lines) + "\n</pre>"
    await message.reply(f"{mention}\n{table}", parse_mode=ParseMode.HTML)


@router.message(F.text.lower().startswith("сенсей мудрец"))
async def cmd_sage(message: Message, container: Container):
    """Сенсей отвечает на вопрос"""
    # Extract question
    # "Сенсей мудрец (вопрос)" -> remove "сенсей мудрец"
    text = message.text
    prefix = "сенсей мудрец"
    
    username = message.from_user.username
    mention = f"@{username}" if username else f"<b>{html.escape(message.from_user.full_name)}</b>"

    # Find where the prefix ends (case insensitive)
    start_index = text.lower().find(prefix)
    if start_index == -1:
        return
        
    question = text[start_index + len(prefix):].strip()
    
    if not question:
        await message.reply(f"{mention}\n\n👂 Ты позвал меня, но ничего не спросил. Ты пьян, ученик?")
        return
        
    await message.bot.send_chat_action(message.chat.id, "typing")
    
    answer = await container.digest_service.ask_sensei(question)
    
    await message.reply(f"{mention}\n\n{answer}")
