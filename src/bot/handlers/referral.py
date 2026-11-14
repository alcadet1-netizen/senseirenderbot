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

def coin_text(value):
    """Compact Coin amount without hiding sub-Coin commissions."""
    return f"{value:,.3f}".rstrip('0').rstrip('.').replace(',', ' ').replace('.', ',')


from aiogram.filters.callback_data import CallbackData


class ReferralPage(CallbackData, prefix='refpage'):
    user_id: int
    kind: str
    level: int = 1
    page: int = 0


def page_keyboard(uid, kind, level, page, has_next):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    rows = []
    if kind == 'network':
        rows.append([InlineKeyboardButton(text=f"{'● ' if n == level else ''}{n} уровень",
            callback_data=ReferralPage(user_id=uid, kind=kind, level=n).pack()) for n in (1, 2, 3)])
    nav = []
    if page:
        nav.append(InlineKeyboardButton(text='← Ранее', callback_data=ReferralPage(user_id=uid, kind=kind, level=level, page=page-1).pack()))
    if has_next:
        nav.append(InlineKeyboardButton(text='Далее →', callback_data=ReferralPage(user_id=uid, kind=kind, level=level, page=page+1).pack()))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text='🥷 В додзё', callback_data=RefCb(action='menu', user_id=uid).pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def edit_referral(cb, text, keyboard):
    from aiogram.types import LinkPreviewOptions
    try:
        await cb.message.edit_text(text, parse_mode='HTML', reply_markup=keyboard,
            link_preview_options=LinkPreviewOptions(is_disabled=True))
    except TelegramBadRequest as exc:
        if 'message is not modified' not in str(exc):
            raise
    await cb.answer()


def bonus_progress(stats):
    if not stats.bonus_eligible:
        return ''
    if stats.bonus_paid:
        return '\n\n🎁 <b>Твой стартовый бонус получен</b> · 50 Coin'
    days = min(3, max(0, stats.activity_days))
    bar = '●' * days + '○' * (3 - days)
    upgrade = '✅' if stats.paid_upgrade else '○'
    note = ('Условия выполнены. Выплата проверяется на следующем платном апе; нужны средства банка.'
        if days == 3 and stats.paid_upgrade else 'День платного апа тоже считается днём активности.')
    return (f'\n\n🎁 <b>Твой бонус · 50 Coin</b>\n{bar} Дни активности: {days}/3\n'
        f'{upgrade} Платный ап катаны\n<i>{note}</i>')


def format_stats_card(stats: ReferralStats, name: str) -> str:
    """Форматирует карточку статистики."""
    empty = "\n\n<i>Первый ученик начинается с одного приглашения. Создай объявление ниже ↓</i>" if not stats.level_1_count else ""
    return (
        f"🥷 <b>ДОДЗЁ ПРИГЛАШЕНИЙ</b>\n{name}\n\n"
        f"💰 Заработано по новой программе: <b>{coin_text(stats.total_coins_earned)} Coin</b>\n\n"
        f"🌳 <b>Твоя сеть</b>\n"
        f"├ I уровень: {stats.level_1_count} · бонус выдан {stats.level_1_active}\n"
        f"├ II уровень: {stats.level_2_count} · бонус выдан {stats.level_2_active}\n"
        f"└ III уровень: {stats.level_3_count} · бонус выдан {stats.level_3_active}\n\n"
        "⚔️ С каждой оплаченной попытки улучшения катаны:\n"
        "<b>10% / 1% / 0,1%</b> по трём уровням.\n"
        "За 500 Coin: 50 / 5 / 0,5 Coin, остаток — банку.\n\n"
        "🎁 За активацию нового ученика: 100 Coin тебе, 50 ему.\n"
        "Три дня активности + платный ап катаны; выплата при наличии средств банка."
        f"{bonus_progress(stats)}{empty}"
    )

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

    text = f"{format_stats_card(stats, user_name)}\n\n🔗 <code>{link}</code>"
    from aiogram.types import LinkPreviewOptions
    keyboard = get_referral_keyboard(link, user_id)
    preview = LinkPreviewOptions(is_disabled=True)
    
    if is_edit:
        try:
            await message.edit_text(text, parse_mode="HTML", reply_markup=keyboard, link_preview_options=preview)
        except TelegramBadRequest as exc:
            if 'message is not modified' not in str(exc):
                raise
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=keyboard, link_preview_options=preview)

@router.message(Command("senseireferal", "referral", "ref", "referal", "реферал"))
@router.message(F.text.regexp(r"(?i)(?:^|\s)/senseireferal(@\w+)?\b"))
async def cmd_ref(msg: Message, container: Container):
    if not msg.from_user:
        return
    
    if msg.chat.type != 'private':
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        bot = await msg.bot.get_me()
        await msg.answer('🥷 Твоё додзё приглашений — в личном кабинете.\nСсылка, объявление, ученики и доход — всё там.',
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
                text='🥷 Открыть моё додзё', url=f'https://t.me/{bot.username}?start=referrals_menu')]]))
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
        await cb.answer()
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
    
    await cb.message.edit_text(
        "📜 <b>ПРАВИЛА ДОДЗЁ</b>\n\n"
        "Приглашение закрепляется при регистрации. Самоприглашения и смена пригласившего запрещены.\n\n"
        "С каждой оплаченной попытки улучшения катаны, включая неудачную: 10% / 1% / 0,1% трём пригласившим. "
        "Остаток и доли отсутствующих участников получает SenseiBank. Переводы и награды процентов не дают.\n\n"
        "Новым приглашённым: три разных дня активности, включая день платного апа. "
        "После этого банк выплачивает 100 Coin пригласившему и 50 новичку. Если средств не хватает — "
        "проверка повторяется при следующем платном апе. Старые бонусы не переигрываются. XP не начисляется.",
        parse_mode="HTML", reply_markup=get_referral_back_keyboard(callback_data.user_id))
    await cb.answer()

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
    
    await show_network(cb, container, 1)


async def show_network(cb, container, level, page=0):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    pipeline = [{'$match': {'referrer_id': cb.from_user.id}}]
    for _ in range(level - 1):
        pipeline += [{'$lookup': {'from': 'users', 'localField': 'id', 'foreignField': 'referrer_id', 'as': 'children'}},
            {'$unwind': '$children'}, {'$replaceRoot': {'newRoot': '$children'}}]
    pipeline += [{'$sort': {'id': 1}}, {'$skip': page * 10}, {'$limit': 11}]
    rows = await container.referral_service.mongo_client.database.users.aggregate(pipeline).to_list(length=11)
    lines = [f'🌳 <b>УЧЕНИКИ · УРОВЕНЬ {level}</b>', f'Страница {page + 1}', '']
    for position, user in enumerate(rows[:10], page * 10 + 1):
        status = '✅' if user.get('referral_bonus_paid') else '💤'
        name = html.escape((user.get('first_name') or str(user['id']))[:50])
        lines.append(f'{position}. {status} {name}')
    if not rows:
        lines.append('Здесь пока тихо. Пригласи первого ученика!')
    lines.append('\n✅ Бонус выдан · 💤 Бонус не выдан\nСтатус бонуса не ограничивает постоянные комиссии.')
    await edit_referral(cb, '\n'.join(lines), page_keyboard(cb.from_user.id, 'network', level, page, len(rows) > 10))


@router.callback_query(RefCb.filter(F.action.in_({'level1', 'level2', 'level3'})))
async def cb_network_level(cb: CallbackQuery, callback_data: RefCb, container: Container):
    if await check_owner(cb, callback_data.user_id):
        await show_network(cb, container, int(callback_data.action[-1]))


@router.callback_query(RefCb.filter(F.action == 'income'))
async def cb_income(cb: CallbackQuery, callback_data: RefCb, container: Container):
    if not await check_owner(cb, callback_data.user_id):
        return
    await show_income(cb, container)


async def show_income(cb, container, page=0):
    rows = await container.referral_service.mongo_client.database.transactions.find({
        'user_id': cb.from_user.id, 'tx_type': {'$in': ['referral_commission', 'referral_activation']}
    }).sort([('created_at', -1), ('_id', -1)]).skip(page * 10).limit(11).to_list(length=11)
    lines = ['💰 <b>ИСТОРИЯ ДОХОДА</b>', f'Страница {page + 1} · время UTC', '']
    for row in rows[:10]:
        if row['tx_type'] == 'referral_commission':
            reason = f"Катана · уровень {row.get('level', 1)}"
        else:
            reason = 'Твой стартовый бонус' if row.get('source_user_id') == cb.from_user.id else 'Активация ученика'
        date = row['created_at'].strftime('%d.%m.%Y · %H:%M')
        lines.append(f"<b>+{coin_text(row['coins_change'])} Coin</b> · {reason}\n{date}")
    if not rows:
        lines.append('Здесь появятся реальные начисления.\nПригласи друга — его платные апы принесут тебе Coin.')
    await edit_referral(cb, '\n'.join(lines), page_keyboard(cb.from_user.id, 'income', 1, page, len(rows) > 10))


@router.callback_query(ReferralPage.filter())
async def cb_referral_page(cb: CallbackQuery, callback_data: ReferralPage, container: Container):
    if not await check_owner(cb, callback_data.user_id):
        return
    if callback_data.kind not in {'network', 'income'} or callback_data.level not in (1, 2, 3) or not 0 <= callback_data.page <= 10000:
        await cb.answer('Открой меню заново: /senseireferal', show_alert=True)
        return
    if callback_data.kind == 'network':
        await show_network(cb, container, callback_data.level, callback_data.page)
    else:
        await show_income(cb, container, callback_data.page)

@router.callback_query(RefCb.filter(F.action == "help"))
async def cb_help(cb: CallbackQuery, callback_data: RefCb):
    await cb_rewards(cb, callback_data)

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


ADVERT_TEXT = (
    "🥷 <b>ТВОЁ МЕСТО В ДОДЗЁ СВОБОДНО</b>\n\n"
    "Прокачивай катану, сражайся с боссами и собирай SenseiCoin.\n"
    "Приглашай друзей и получай доход с улучшений их катан на трёх уровнях.\n\n"
    "🎁 Новичку — 50 Coin после трёх дней активности и платного апа катаны, "
    "при наличии средств SenseiBank. Подробности: /senseireferal."
)


def advert_keyboard(link):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CopyTextButton
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚔️ Вступить в додзё", url=link)],
        [InlineKeyboardButton(text="🔗 Скопировать ссылку", copy_text=CopyTextButton(text=link))]])


@router.callback_query(RefCb.filter(F.action == "advert"))
async def cb_advert(cb: CallbackQuery, callback_data: RefCb):
    if not await check_owner(cb, callback_data.user_id):
        return
    bot = await cb.bot.get_me()
    await cb.message.answer(ADVERT_TEXT, parse_mode="HTML",
        reply_markup=advert_keyboard(get_ref_link(bot.username, cb.from_user.id)))
    await cb.answer("Готово! Перешли объявление или выбери чат в меню.")


@router.inline_query(F.query == "senseireferal")
async def referral_inline(query):
    from aiogram.types import InlineQueryResultArticle, InputTextMessageContent
    bot = await query.bot.get_me()
    link = get_ref_link(bot.username, query.from_user.id)
    await query.answer([InlineQueryResultArticle(id=f"ref_{query.from_user.id}",
        title="🥷 Приглашение в додзё", description="Объявление с твоей кнопкой и копированием ссылки",
        input_message_content=InputTextMessageContent(message_text=ADVERT_TEXT, parse_mode="HTML"),
        reply_markup=advert_keyboard(link))], cache_time=0, is_personal=True)
