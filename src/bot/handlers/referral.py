from aiogram import Router, F
import html
import random
import logging
from typing import Optional, List, Dict, Any

from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest

from src.core.container import Container
from src.domain.entities.referral import ReferralRank, REWARDS, ReferralStats
from src.core.visuals import Visuals
from src.bot.keyboards.inline import (
    get_referral_keyboard, 
    get_referral_back_keyboard, 
    RefCb
)
from src.bot.utils import check_owner

logger = logging.getLogger(__name__)

router = Router(name="referral")

EMPIRE_TITLES = {
    "novice": "Деревня",
    "beginner": "Поселение",
    "apprentice": "Городок",
    "adept": "Город",
    "master": "Мегаполис",
    "sensei": "Столица",
    "legend": "Империя",
    "emperor": "Доминион",
    "god": "Вселенная"
}

EMPIRE_QUOTES = [
    "Налоги — это любовь.",
    "Строй зиккурат!",
    "Нужно больше золота.",
    "Казна пустеет, милорд.",
    "Вассалы довольны.",
    "Крипта — наш фундамент."
]

def get_ref_link(bot_username: str, user_id: int) -> str:
    """Генерирует реферальную ссылку."""
    return f"https://t.me/{bot_username}?start=ref_{user_id}"

def format_stats_card(stats: ReferralStats, name: str) -> str:
    """Форматирует карточку статистики."""
    r, nr = stats.rank, stats.next_rank
    w = Visuals.FRAME_W_PROFILE
    
    # Header
    lines = [
        Visuals.frame_top_left(w),
        Visuals.frame_line_left(f"👤 {name}", w),
        Visuals.frame_line_left(f"{r.emoji} {r.title}", w),
        Visuals.frame_separator_left(w),
        Visuals.frame_line_left(f"👥 L1: {stats.level_1_count} (✅{stats.level_1_active})", w),
        Visuals.frame_line_left(f"🔗 L2: {stats.level_2_count} (✅{stats.level_2_active})", w),
        Visuals.frame_separator_left(w),
        Visuals.frame_line_left(f"💰 {stats.total_coins_earned:,.0f} | ✨ {stats.total_xp_earned:,}", w),
    ]
    
    # Progress to next rank
    if nr:
        # Custom progress bar using Visuals logic
        p_bar = Visuals.progress_bar(int(stats.progress_to_next), 100, length=12)
        lines.append(Visuals.frame_separator_left(w))
        lines.append(Visuals.frame_line_left(f"🚀 До {nr.title}:", w))
        lines.append(Visuals.frame_line_left(p_bar, w))
        lines.append(Visuals.frame_line_left(f"{stats.level_1_count}/{nr.required} {nr.emoji}", w, "right"))
    else:
        lines.append(Visuals.frame_separator_left(w))
        lines.append(Visuals.frame_line_left("🏆 Максимальный ранг!", w, "center"))

    lines.append(Visuals.frame_bottom_left(w))
    
    return "<pre>\n" + "\n".join(lines) + "\n</pre>"

async def _show_referral_menu(
    message: Message, 
    user_id: int, 
    container: Container, 
    is_edit: bool = False,
    user_name: str = None
):
    """Отображает главное меню реферальной системы."""
    bot = await message.bot.get_me()
    link = get_ref_link(bot.username, user_id)
    
    stats = await container.referral_service.get_stats(user_id)
    
    if not user_name:
        # Fallback if not provided (should not happen if caller passes it)
        chat = await message.bot.get_chat(user_id)
        user_name = f"@{chat.username}" if chat.username else html.escape(chat.full_name)

    text = f"🐉 <b>РЕФЕРАЛЬНАЯ СИСТЕМА</b>\n{format_stats_card(stats, user_name)}\n\n🔗 <code>{link}</code>"
    keyboard = get_referral_keyboard(link, user_id)
    
    if is_edit:
        await message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=keyboard)

@router.message(Command("senseireferal", "referral", "ref", "referal", "реферал"))
@router.message(F.text.regexp(r"(?i)(?:^|\s)/senseireferal(@\w+)?\b"))
async def cmd_ref(msg: Message, container: Container):
    if not msg.from_user:
        return
    
    try:
        u = msg.from_user
        name = f"@{u.username}" if u.username else html.escape(u.full_name)
        await _show_referral_menu(msg, u.id, container, is_edit=False, user_name=name)
    except Exception as e:
        logger.error(f"Error in cmd_ref: {e}", exc_info=True)
        await msg.answer("❌ Произошла ошибка при получении данных.")

@router.callback_query(RefCb.filter(F.action == "menu"))
async def cb_menu(cb: CallbackQuery, callback_data: RefCb, container: Container):
    if not await check_owner(cb, callback_data.user_id):
        return
    
    try:
        u = cb.from_user
        name = f"@{u.username}" if u.username else html.escape(u.full_name)
        await _show_referral_menu(cb.message, u.id, container, is_edit=True, user_name=name)
    except Exception as e:
        logger.error(f"Error in cb_menu: {e}", exc_info=True)
        await cb.answer("❌ Ошибка загрузки меню", show_alert=True)

@router.callback_query(RefCb.filter(F.action == "main"))
async def cb_main(cb: CallbackQuery, callback_data: RefCb, container: Container):
    """Возврат в главное меню (алиас для menu)."""
    await cb_menu(cb, callback_data, container)

@router.callback_query(RefCb.filter(F.action == "stats"))
async def cb_stats(cb: CallbackQuery, callback_data: RefCb, container: Container):
    if not await check_owner(cb, callback_data.user_id):
        return
    
    try:
        stats = await container.referral_service.get_stats(cb.from_user.id)
        name = f"@{cb.from_user.username}" if cb.from_user.username else html.escape(cb.from_user.full_name)
        
        await cb.message.edit_text(
            f"📊 <b>СТАТИСТИКА</b>\n{format_stats_card(stats, name)}", 
            parse_mode="HTML", 
            reply_markup=get_referral_back_keyboard(callback_data.user_id)
        )
    except Exception as e:
        logger.error(f"Error in cb_stats: {e}", exc_info=True)
        await cb.answer("❌ Ошибка загрузки статистики", show_alert=True)

@router.callback_query(RefCb.filter(F.action == "share"))
async def cb_share(cb: CallbackQuery, callback_data: RefCb):
    if not await check_owner(cb, callback_data.user_id):
        return
    
    try:
        u = cb.from_user
        bot = await cb.bot.get_me()
        link = get_ref_link(bot.username, u.id)
        
        await cb.message.answer(
            f"🔗 <b>Твоя реферальная ссылка:</b>\n\n<code>{link}</code>\n\n"
            "👆 <i>Нажми на ссылку, чтобы скопировать</i>",
            parse_mode="HTML"
        )
        try:
            await cb.answer("Ссылка отправлена новым сообщением!")
        except TelegramBadRequest:
            pass
    except Exception as e:
        logger.error(f"Error in cb_share: {e}", exc_info=True)

@router.callback_query(RefCb.filter(F.action == "top"))
async def cb_top(cb: CallbackQuery, callback_data: RefCb, container: Container):
    if not await check_owner(cb, callback_data.user_id):
        return
    
    try:
        top = await container.referral_service.get_top(10)
        
        items = []
        for uid, cnt, uname, fname in top:
            display_name = f"@{uname}" if uname else fname
            if not display_name:
                display_name = f"ID:{uid}"
            items.append({"username": display_name, "count": cnt})
            
        # Visuals.top_table(title, emoji, items, value_key)
        table = Visuals.top_table("ОБЩИЙ ЛИДЕРБОРД", "🏆", items, "count")
        
        await cb.message.edit_text(table, parse_mode="HTML", reply_markup=get_referral_back_keyboard(callback_data.user_id))
    except Exception as e:
        logger.error(f"Error in cb_top: {e}", exc_info=True)
        await cb.answer("❌ Ошибка загрузки топа", show_alert=True)

@router.callback_query(RefCb.filter(F.action == "rewards"))
async def cb_rewards(cb: CallbackQuery, callback_data: RefCb):
    if not await check_owner(cb, callback_data.user_id):
        return
    
    r1, r2 = REWARDS[1], REWARDS[2]
    w = Visuals.FRAME_W_PROFILE
    lines = [
        Visuals.frame_top_left(w),
        Visuals.frame_line_left("💎 НАГРАДЫ", w, "center"),
        Visuals.frame_separator_left(w),
        Visuals.frame_line_left("🔵 Уровень 1 (L1)", w),
        Visuals.frame_line_left(f"Вам: +{r1[0]}💰 +{r1[1]}✨", w),
        Visuals.frame_line_left(f"Другу: +{r1[2]}💰 +{r1[3]}✨", w),
        Visuals.frame_separator_left(w),
        Visuals.frame_line_left("🟣 Уровень 2 (L2)", w),
        Visuals.frame_line_left(f"Вам: +{r2[0]}💰 +{r2[1]}✨", w),
        Visuals.frame_bottom_left(w)
    ]
    text = "<pre>\n" + "\n".join(lines) + "\n</pre>"
    await cb.message.edit_text(text, parse_mode="HTML", reply_markup=get_referral_back_keyboard(callback_data.user_id))

@router.callback_query(RefCb.filter(F.action == "ranks"))
async def cb_ranks(cb: CallbackQuery, callback_data: RefCb):
    if not await check_owner(cb, callback_data.user_id):
        return
    
    w = Visuals.FRAME_W_PROFILE
    lines = [
        Visuals.frame_top_left(w),
        Visuals.frame_line_left("🏅 РАНГИ ИМПЕРИИ", w, "center"),
        Visuals.frame_separator_left(w)
    ]
    
    for r in ReferralRank:
        row = f"{r.emoji} {r.title}: {r.required}+"
        lines.append(Visuals.frame_line_left(row, w))
        
    lines.append(Visuals.frame_bottom_left(w))
    text = "<pre>\n" + "\n".join(lines) + "\n</pre>"
    await cb.message.edit_text(text, parse_mode="HTML", reply_markup=get_referral_back_keyboard(callback_data.user_id))

@router.callback_query(RefCb.filter(F.action == "list"))
async def cb_list(cb: CallbackQuery, callback_data: RefCb, container: Container):
    if not await check_owner(cb, callback_data.user_id):
        return
    
    try:
        refs = await container.referral_service.get_referrals_list(cb.from_user.id)
        w = Visuals.FRAME_W_MENU
        
        lines = [
            Visuals.frame_top_left(w),
            Visuals.frame_line_left("📋 ВАШИ РЕФЕРАЛЫ", w, "center"),
            Visuals.frame_separator_left(w)
        ]
        
        if not refs:
            lines.append(Visuals.frame_line_left("Пока пусто...", w, "center"))
        else:
            # Show last 10
            for r in refs[:10]:
                s = "✅" if r.is_active else "💤"
                row = f"{s} {r.referred_id} +{int(r.coins_earned)}"
                lines.append(Visuals.frame_line_left(row, w))
                
            if len(refs) > 10:
                 lines.append(Visuals.frame_separator_left(w))
                 lines.append(Visuals.frame_line_left(f"И еще {len(refs)-10}...", w, "center"))

        lines.append(Visuals.frame_bottom_left(w))
        text = "<pre>\n" + "\n".join(lines) + "\n</pre>"
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=get_referral_back_keyboard(callback_data.user_id))
    except Exception as e:
        logger.error(f"Error in cb_list: {e}", exc_info=True)
        await cb.answer("❌ Ошибка загрузки списка", show_alert=True)

@router.callback_query(RefCb.filter(F.action == "help"))
async def cb_help(cb: CallbackQuery, callback_data: RefCb):
    if not await check_owner(cb, callback_data.user_id):
        return
    w = Visuals.FRAME_W_PROFILE
    lines = [
        Visuals.frame_top_left(w),
        Visuals.frame_line_left("❓ КАК ЭТО РАБОТАЕТ", w, "center"),
        Visuals.frame_separator_left(w),
        Visuals.frame_line_left("🔵 L1 (Друзья):", w),
        Visuals.frame_line_left("Награда вам и другу", w),
        Visuals.frame_line_left("", w),
        Visuals.frame_line_left("🟣 L2 (Их друзья):", w),
        Visuals.frame_line_left("Пассивный доход вам", w),
        Visuals.frame_separator_left(w),
        Visuals.frame_line_left("⚠️ Правила:", w),
        Visuals.frame_line_left("Не приглашать ботов", w),
        Visuals.frame_line_left("Не абузить", w),
        Visuals.frame_bottom_left(w)
    ]
    text = "<pre>\n" + "\n".join(lines) + "\n</pre>"
    await cb.message.edit_text(text, parse_mode="HTML", reply_markup=get_referral_back_keyboard(callback_data.user_id))

@router.callback_query(RefCb.filter(F.action == "empire"))
async def cb_empire(cb: CallbackQuery, callback_data: RefCb, container: Container):
    if not await check_owner(cb, callback_data.user_id):
        return
    
    try:
        stats = await container.referral_service.get_stats(cb.from_user.id)
        w = Visuals.FRAME_W_PROFILE
        rank = stats.rank
        
        empire_title = EMPIRE_TITLES.get(rank.id_, "Земли")
        quote = random.choice(EMPIRE_QUOTES)

        lines = [
            Visuals.frame_top_left(w),
            Visuals.frame_line_left(f"🏰 {empire_title.upper()}", w, "center"),
            Visuals.frame_separator_left(w),
            Visuals.frame_line_left(f"👑 {cb.from_user.first_name}", w, "center"),
            Visuals.frame_separator_left(w),
            Visuals.frame_line_left("📊 Население:", w),
            Visuals.frame_line_left(f"👥 Граждане: {stats.level_1_count}", w),
            Visuals.frame_line_left(f"🔗 Вассалы: {stats.level_2_count}", w),
            Visuals.frame_separator_left(w),
            Visuals.frame_line_left("💰 Казна:", w),
            Visuals.frame_line_left(f"🪙 {stats.total_coins_earned:,.0f}", w),
            Visuals.frame_separator_left(w),
            Visuals.frame_line_left(f"📜 {quote}", w, "center"),
            Visuals.frame_bottom_left(w)
        ]
        
        text = "<pre>\n" + "\n".join(lines) + "\n</pre>"
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=get_referral_back_keyboard(callback_data.user_id))
    except Exception as e:
        logger.error(f"Error in cb_empire: {e}", exc_info=True)
        await cb.answer("❌ Ошибка загрузки империи", show_alert=True)
