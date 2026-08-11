"""
📢 Обработчики команды ZOV (Созыв).
"""

import asyncio
import logging
import re
from typing import Dict, List, Optional

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter

from src.bot.filters import AdminFilter
from src.core.config import settings
from src.core.container import Container

logger = logging.getLogger(__name__)

router = Router(name="zov")
router.message.filter(AdminFilter())

EMOJI_LIST = [
    "🐶","🐱","🐭","🐹","🐰","🦊","🐻","🐼","🐻‍❄️","🦁","🐯","🐮","🐷","🐽","🐸","🐵",
    "🙈","🙉","🙊","🐒","🐔","🐧","🐦","🐤","🐣","🐥","🦆","🦅","🦉","🦇","🐺","🐗",
    "🐴","🦄","🐝","🪲","🐛","🦋","🐌","🐞","🐜","🪳","🦟","🦗","🕷️","🦂","🐢","🐍",
    "🦎","🦖","🦕","🐙","🦑","🦐","🦞","🦀","🐡","🐠","🐟","🐬","🐳","🐋","🦈","🐊",
    "🐅","🐆","🦓","🦍","🦧","🦣","🐘","🦛","🦏","🐪","🐫","🦒","🦘","🦬","🐃","🐂",
    "🐄","🐎","🐖","🐏","🐑","🦙","🐐","🦌","🐕","🐩","🦮","🐈","🐓","🦃","🦤","🦚",
    "🦜","🦢","🦩","🕊️","🐇","🦝","🦨","🦡","🦫","🦦","🦥","🐁","🐀","🐿️","🦔","🐾",
    "🌸","🌺","🌻","🌼","🌷","🌹","🥀","🪻","🪷","💐","🌾","🌵","🌴","🌲","🌳","🌱",
    "🍀","☘️","🍃","🍂","🍁","🪺","🪹","🍄","🐚","🪸","🪨","🌿","🪴","💮","🎋","🎍",
    "⭐","🌟","💫","✨","🔥","💥","💢","💦","💨","🌈","☀️","🌤️","⛅","🌥️","☁️","🌧️",
    "⛈️","🌩️","🌨️","❄️","☃️","⛄","🌬️","💨","🌊","🌫️","🌪️","🌀","🔥","💧",
    "🍎","🍏","🍊","🍋","🍌","🍉","🍇","🍓","🫐","🍈","🍒","🍑","🥭","🍍","🥥","🥝",
    "🍅","🍆","🥑","🥦","🥬","🥒","🌶️","🫑","🌽","🥕","🧄","🧅","🥔","🍠","🥐","🥯",
    "🍞","🥖","🥨","🧀","🥚","🍳","🧈","🥞","🧇","🥓","🥩","🍗","🍖","🌭","🍔","🍟",
    "🍕","🫓","🥪","🥙","🧆","🌮","🌯","🫔","🥗","🥘","🫕","🍝","🍜","🍲","🍛","🍣",
    "🍱","🥟","🦪","🍤","🍙","🍚","🍘","🍥","🥠","🥮","🍢","🍡","🍧","🍨","🍦","🥧",
    "🧁","🍰","🎂","🍮","🍭","🍬","🍫","🍿","🍩","🍪","🌰","🥜","🍯","🥛","🍼","☕",
    "🫖","🍵","🧃","🥤","🧋","🍶","🍺","🍻","🥂","🍷","🥃","🍸","🍹","🧉","🍾","🧊",
    "⚽","🏀","🏈","⚾","🥎","🎾","🏐","🏉","🥏","🎱","🪀","🏓","🏸","🏒","🏑","🥍",
    "🏏","🪃","🥅","⛳","🪁","🛝","🏹","🎣","🤿","🥊","🥋","🎽","🛹","🛼","🛷","⛸️",
    "🎿","🎪","🎭","🩰","🎨","🎬","🎤","🎧","🎼","🎹","🥁","🪘","🎷","🎺","🎸","🪕",
    "🎻","🎲","♟️","🎯","🎳","🎮","🕹️","🧩","🧸","🪆","🪅","🎰","🎁","🎀","🎊","🎉",
    "🎈","🪩","🎐","🏮","🪔","🧧","💎","💍","👑","🎩","🧢","👒","🎓","⛑️","💄","👠",
    "👗","👔","👕","👖","🧣","🧤","🧥","🧦","👙","👘","🥻","🩱","🩲","🩳","👚","👛",
    "👜","👝","🎒","🩴","👞","👟","🥾","🥿","👢","👡","🌂","☂️","💼","🧳","🎭","🩹",
    "❤️","🧡","💛","💚","💙","💜","🖤","🤍","🤎","💔","❣️","💕","💞","💓","💗","💖",
    "💘","💝","💟","☮️","✝️","☪️","🕉️","☸️","✡️","🔯","🕎","☯️","☦️","🛐","⛎","♈",
    "♉","♊","♋","♌","♍","♎","♏","♐","♑","♒","♓","🆔","⚛️","🉑","☢️","☣️","📴","📳",
    "🈶","🈚","🈸","🈺","🈷️","✴️","🆚","💮","🉐","㊙️","㊗️","🈴","🈵","🈹","🈲","🅰️",
    "🅱️","🆎","🆑","🅾️","🆘","❌","⭕","🛑","⛔","📛","🚫","💯","💢","♨️","🚷","🚯",
    "🚳","🚱","🔞","📵","🚭","❗","❕","❓","❔","‼️","⁉️","🔅","🔆","〽️","⚠️","🚸",
    "🔱","⚜️","🔰","♻️","✅","🈯","💹","❇️","✳️","❎","🌐","💠","Ⓜ️","🌀","💤","🏧",
    "🚾","♿","🅿️","🛗","🈳","🈂️","🛂","🛃","🛄","🛅","🚹","🚺","🚻","🚮","🎦","📶",
    "🈁","🔣","ℹ️","🔤","🔡","🔠","🆖","🆗","🆙","🆒","🆕","🆓","0️⃣","1️⃣","2️⃣","3️⃣"
]


class ZovManager:
    """Менеджер задач созыва (ZOV)."""
    
    def __init__(self):
        self.active_tasks: Dict[int, asyncio.Task] = {}
        self.cancellation_flags: Dict[int, bool] = {}

    def is_running(self, chat_id: int) -> bool:
        task = self.active_tasks.get(chat_id)
        return task is not None and not task.done()

    def start_zov(self, chat_id: int, task: asyncio.Task):
        self.active_tasks[chat_id] = task
        self.cancellation_flags[chat_id] = False

    def stop_zov(self, chat_id: int):
        if chat_id in self.active_tasks:
            self.cancellation_flags[chat_id] = True
            task = self.active_tasks[chat_id]
            if not task.done():
                task.cancel()
            
    def is_cancelled(self, chat_id: int) -> bool:
        return self.cancellation_flags.get(chat_id, False)

    def cleanup(self, chat_id: int):
        self.active_tasks.pop(chat_id, None)
        self.cancellation_flags.pop(chat_id, None)


zov_manager = ZovManager()


def format_notification(title: str, lines: List[str], emoji: str = "📢", title_style: str = "bold") -> str:
    """Форматирование уведомления (Compact Left-Only Style)."""
    w = 30  # Compact width
    
    # Clean up lines (remove empty ones if needed, or keep them as empty frame lines)
    # Visuals.frame_line_left handles empty strings nicely if implemented correctly
    
    formatted_lines = [
        Visuals.frame_top_left(w),
        Visuals.frame_line_left(f"{emoji} {title}", w, "center"),
        Visuals.frame_separator_left(w),
    ]
    
    for line in lines:
        if line.strip() == "":
            formatted_lines.append(Visuals.frame_line_left(" ", w))
        else:
            # Wrap long lines if necessary, though Visuals usually truncates or we trust the content
            # For ZOV, content is usually simple stats.
            formatted_lines.append(Visuals.frame_line_left(line, w))
            
    formatted_lines.append(Visuals.frame_bottom_left(w))
    
    return "<pre>\n" + "\n".join(formatted_lines) + "\n</pre>"


async def _process_zov(bot, container: Container, chat_id: int, members: list):
    """Фоновая задача созыва."""
    try:
        await asyncio.sleep(10)
        
        if zov_manager.is_cancelled(chat_id):
            await bot.send_message(chat_id, "❌ Отменено.")
            return
        
        # Разбиваем на батчи по 5
        batch_size = 5
        batches = [members[i:i + batch_size] for i in range(0, len(members), batch_size)]
        total_batches = len(batches)
        total_members = len(members)
        
        done_count = 0
        coins_count = 0
        fail_count = 0
        
        idx = 0
        
        for bn, batch in enumerate(batches, 1):
            if zov_manager.is_cancelled(chat_id):
                await bot.send_message(chat_id, "❌ Отменено.")
                return
            
            mentions = []
            current_batch_success = 0
            
            for m in batch:
                uid = m.get('id')
                username = (m.get('un') or "").strip().lstrip("@")
                name = m.get('name', 'User')
                
                if not uid:
                    fail_count += 1
                    continue
                
                emoji = EMOJI_LIST[idx % len(EMOJI_LIST)]
                idx += 1
                
                is_valid_username = bool(username and re.match(r"^[A-Za-z0-9_]{5,32}$", username))
                
                if is_valid_username:
                    txt = f"@{username}"
                else:
                    txt = f'<a href="tg://user?id={uid}">{emoji}</a>'
                
                mentions.append(txt)
                current_batch_success += 1
                
                # Начисляем награду
                try:
                    success = await container.economy_service.distribute_zov_reward(uid, 1.0)
                    if success:
                        coins_count += 1
                except Exception:
                    pass
            
            if mentions:
                msg_text = " ".join(mentions)
                try:
                    await bot.send_message(chat_id, msg_text, parse_mode="HTML", disable_web_page_preview=True)
                    done_count += current_batch_success
                except TelegramBadRequest:
                    # Если не удалось батчем, шлем по одному
                    for mention_text in mentions:
                        try:
                            await bot.send_message(chat_id, mention_text, parse_mode="HTML", disable_web_page_preview=True)
                            done_count += 1
                            await asyncio.sleep(0.3)
                        except Exception:
                            fail_count += 1
                except TelegramRetryAfter as e:
                    await asyncio.sleep(e.retry_after)
                    try:
                        await bot.send_message(chat_id, msg_text, parse_mode="HTML", disable_web_page_preview=True)
                        done_count += current_batch_success
                    except Exception:
                        fail_count += current_batch_success
                except Exception:
                    fail_count += current_batch_success
            
            # Прогресс каждые 5 батчей или в конце
            if bn % 5 == 0 or bn == total_batches:
                try:
                    percent = done_count * 100 // max(total_members, 1)
                    await bot.send_message(chat_id, f"📊 {done_count}/{total_members} ({percent}%)")
                except Exception:
                    pass
            
            if bn < total_batches:
                await asyncio.sleep(5)
        
        if not zov_manager.is_cancelled(chat_id):
            lines = [
                "🙏 Спасибо!", 
                "", 
                f"👥 {done_count}", 
                f"💰 {coins_count:,}",
                "",
            ]
            if fail_count:
                lines.append(f"⚠️ {fail_count}")
            
            final_msg = format_notification("ГОТОВО", lines, "✅", "b")
            
            try:
                await bot.send_message(chat_id, final_msg, parse_mode="HTML")
            except Exception:
                pass
            
            logger.info(f"✅ Созыв завершен: {done_count}/{coins_count}/{fail_count}")

    except asyncio.CancelledError:
        logger.info("📢 Созыв отменен (task cancelled)")
    except Exception as e:
        logger.exception(f"❌ Ошибка в процессе созыва: {e}")
        try:
            await bot.send_message(chat_id, "❌ Произошла ошибка при выполнении созыва.")
        except Exception:
            pass
    finally:
        zov_manager.cleanup(chat_id)


@router.message(Command("senseizov"))
async def cmd_zov(message: Message, container: Container):
    """Команда /senseizov - массовый созыв."""
    
    # Определяем целевой чат
    chat_id = settings.main_chat_id
    if not chat_id or chat_id == 0:
        if message.chat.type in ["group", "supergroup"]:
            chat_id = message.chat.id
        else:
            await message.answer("❌ MAIN_CHAT_ID не настроен и команда вызвана не в группе.")
            return

    if zov_manager.is_running(chat_id):
        await message.answer("⚠️ Созыв в этом чате уже запущен! /senseinezov для отмены.")
        return
    
    try:
        # Получаем активных пользователей за 30 дней
        users = await container.user_service.get_active_users(limit=10000)
        admins = set(settings.admin_ids)
        
        candidates = [u for u in users if u.get('user_id') and u['user_id'] not in admins]

        sem = asyncio.Semaphore(20)

        async def check_member(u):
            async with sem:
                try:
                    member = await message.chat.get_member(u['user_id'])
                    if member.status not in [ChatMemberStatus.LEFT, ChatMemberStatus.KICKED]:
                        return {
                            'id': u['user_id'],
                            'name': u.get('first_name', 'User'),
                            'un': u.get('username')
                        }
                except Exception:
                    pass
                return None

        checked_results = await asyncio.gather(*[check_member(u) for u in candidates])
        members = [m for m in checked_results if m]
                
    except Exception as e:
        logger.exception(f"❌ Ошибка получения участников: {e}")
        await message.answer("❌ Ошибка получения списка участников!")
        return
    
    if not members:
        await message.answer("❌ Нет участников для созыва!")
        return
    
    total_members = len(members)
    # Расчет времени: 10с старт + (батчи * 5с)
    # Батчей = (total + 4) // 5
    estimated_time_s = 10 + ((total_members + 4) // 5) * 5
    
    try:
        bank_balance = await container.economy_service.get_bank_balance()
        if bank_balance < total_members:
            await message.answer(f"❌ В банке {bank_balance:,}, нужно минимум {total_members:,} монет.")
            return
    except Exception:
        await message.answer("❌ Ошибка проверки баланса банка!")
        return
    
    msg = format_notification(
        "СОЗЫВ", 
        [
            f"👥 {total_members}", 
            f"💰 {total_members:,}", 
            f"⏱ ~{estimated_time_s // 60}м {estimated_time_s % 60}с", 
            "", 
            "⏳ Старт через 10 сек..."
        ], 
        "📢", 
        "b"
    )
    
    try:
        await message.bot.send_message(chat_id, msg, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error sending start message to {chat_id}: {e}")
        await message.answer("❌ Ошибка отправки стартового сообщения! Проверьте права бота или ID чата.")
        return
    
    # Запускаем задачу
    task = asyncio.create_task(_process_zov(message.bot, container, chat_id, members))
    zov_manager.start_zov(chat_id, task)
    
    logger.info(f"📢 Созыв запущен в чате {chat_id}: {total_members} участников")


@router.message(Command("senseinezov"))
async def cmd_stop_zov(message: Message):
    """Отмена созыва."""
    
    # Определяем целевой чат (аналогично запуску)
    chat_id = settings.main_chat_id
    if not chat_id or chat_id == 0:
        if message.chat.type in ["group", "supergroup"]:
            chat_id = message.chat.id
        else:
            await message.answer("❌ Эта команда работает только в настроенном MAIN_CHAT_ID или в группе.")
            return

    if not zov_manager.is_running(chat_id):
        await message.answer("⚠️ Созыв не запущен.")
        return
    
    zov_manager.stop_zov(chat_id)
    await message.answer("✅ Отмена созыва запущена!")
    logger.info(f"🛑 Отмена созыва в чате {chat_id} пользователем {message.from_user.id}")
