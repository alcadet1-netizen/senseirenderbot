"""
🖱️ Обработчики callback-запросов.
"""

from aiogram import Router, F
import html
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest

from src.core.container import Container
from src.core.visuals import Visuals
from src.core.exceptions import (
    DailyAlreadyClaimedError, 
    InsufficientFundsError, 
    InsufficientTicketsError,
    UserNotFoundError, 
    CooldownError, 
    NoKatanaError
)
from src.bot.keyboards.inline import (
    MenuCb,
    KatanaTopCb,
    get_start_keyboard,
    get_top_keyboard,
    get_profile_keyboard,
    get_exchange_keyboard,
    get_katana_top_keyboard
)
from src.bot.handlers.user_commands import show_profile
from src.bot.utils import check_owner
import math

router = Router(name="callbacks")


@router.callback_query(F.data == "check_sub")
async def cb_check_sub(query: CallbackQuery, container: Container):
    """Проверка подписки по кнопке."""
    user_id = query.from_user.id
    channel_username = "@SenseiDurova"

    # Always check with Telegram
    try:
        member = await query.bot.get_chat_member(chat_id=channel_username, user_id=user_id)
        is_subscribed = member.status in ("creator", "administrator", "member", "restricted")
    except Exception:
        is_subscribed = False
            
    if is_subscribed:
        try:
            await query.answer("✅ Подписка подтверждена! Теперь вы можете пользоваться ботом.", show_alert=True)
        except TelegramBadRequest:
            pass
        # Опционально: можно удалить сообщение с требованием подписки, если оно было отдельным
        try:
            await query.message.delete()
        except Exception:
            pass
        # Отправляем приветственное сообщение или меню
        await query.message.answer("👋 Привет! Используй меню или команды.", reply_markup=get_start_keyboard(user_id))
    else:
        try:
            await query.answer("❌ Вы всё ещё не подписаны!", show_alert=True)
        except TelegramBadRequest:
            pass


@router.callback_query(MenuCb.filter(F.action == "profile"))
async def cb_profile(query: CallbackQuery, callback_data: MenuCb, container: Container):
    """Показать профиль."""
    if not query.message:
        return
    
    if not await check_owner(query, callback_data.user_id):
        return
        
    try:
        await query.answer()
    except TelegramBadRequest:
        pass
    await show_profile(query.message, container, query.from_user, is_edit=True)


@router.callback_query(MenuCb.filter(F.action == "back_to_profile"))
async def cb_back_to_profile(query: CallbackQuery, callback_data: MenuCb, container: Container):
    """Назад в профиль."""
    if not query.message:
        return
        
    if not await check_owner(query, callback_data.user_id):
        return
        
    try:
        await query.answer()
    except TelegramBadRequest:
        pass
    await show_profile(query.message, container, query.from_user, is_edit=True)


@router.callback_query(KatanaTopCb.filter())
async def cb_top_katana_page(query: CallbackQuery, callback_data: KatanaTopCb, container: Container):
    """Пагинация топа катан."""
    if not query.message:
        return
        
    if not await check_owner(query, callback_data.user_id):
        return

    page = callback_data.page
    limit = 10
    offset = (page - 1) * limit
    
    result = await container.user_service.get_top_by_katana(limit, offset)
    items = result["items"]
    total = result["total"]
    
    total_pages = math.ceil(total / limit)
    
    text = Visuals.top_katana_table(
        title="ТОП КАТАН",
        emoji="🗡️",
        items=items,
        offset=offset
    )
    
    try:
        await query.message.edit_text(
            text, 
            parse_mode="HTML", 
            reply_markup=get_katana_top_keyboard(
                user_id=callback_data.user_id,
                page=page,
                total_pages=total_pages
            )
        )
    except TelegramBadRequest:
        pass # Message content is the same
        
    try:
        await query.answer()
    except TelegramBadRequest:
        pass


@router.callback_query(MenuCb.filter(F.action == "top_menu"))
async def cb_top_menu(query: CallbackQuery, callback_data: MenuCb, container: Container):
    """Меню топов."""
    if not query.message:
        return
        
    if not await check_owner(query, callback_data.user_id):
        return

    top_xp = await container.user_service.get_top_by_xp(10)
    text = Visuals.top_table("ТОП ПО XP", "⚡", top_xp, "xp")
    await query.message.edit_text(text, parse_mode="HTML", reply_markup=get_top_keyboard(user_id=callback_data.user_id))
    try:
        await query.answer()
    except TelegramBadRequest:
        pass


@router.callback_query(MenuCb.filter(F.action == "daily"))
async def cb_daily(query: CallbackQuery, callback_data: MenuCb, container: Container):
    """Ежедневный бонус."""
    if not query.message:
        return
        
    if not await check_owner(query, callback_data.user_id):
        return
        
    try:
        result = await container.daily_service.claim_daily(
            user_id=query.from_user.id,
            username=query.from_user.username,
            first_name=query.from_user.first_name or "",
            is_bot=query.from_user.is_bot or False
        )
        
        if result["success"]:
            card = Visuals.daily_reward(
                xp=result["xp"],
                coins=result["coins"],
                streak=result["streak"],
                bonus_xp=result["bonus_xp"],
                bonus_coins=result["bonus_coins"]
            )
            await query.message.edit_text(card, parse_mode="HTML")
            try:
                await query.answer("🎁 Бонус получен!", show_alert=True)
            except TelegramBadRequest:
                pass
        else:
             try:
                await query.answer(f"❌ {result.get('error', 'Ошибка')}", show_alert=True)
             except TelegramBadRequest:
                pass

    except DailyAlreadyClaimedError as e:
        try:
            await query.answer(f"⏳ {e}", show_alert=True)
        except TelegramBadRequest:
            pass
    except Exception as e:
        try:
            await query.answer(f"❌ Ошибка: {e}", show_alert=True)
        except TelegramBadRequest:
            pass


@router.callback_query(MenuCb.filter(F.action == "upgrade_katana_confirm"))
async def cb_upgrade_katana_confirm(query: CallbackQuery, callback_data: MenuCb):
    """Подтверждение улучшения катаны."""
    if not query.message:
        return
        
    if not await check_owner(query, callback_data.user_id):
        return
        
    username = query.from_user.username
    mention = f"@{username}" if username else f"<b>{html.escape(query.from_user.full_name)}</b>"
        
    from src.bot.keyboards.inline import get_confirm_keyboard
    
    try:
        await query.answer()
    except TelegramBadRequest:
        pass

    await query.message.edit_text(
        f"{mention}\n\n"
        "⚔️ <b>Улучшение катаны</b>\n\n"
        "Ты уверен, что хочешь попробовать улучшить катану?\n"
        "Это стоит монет, и результат зависит от удачи!",
        reply_markup=get_confirm_keyboard(query.from_user.id, "upgrade_katana"),
        parse_mode="HTML"
    )


@router.callback_query(MenuCb.filter(F.action == "confirm_upgrade_katana"))
async def cb_do_upgrade_katana(query: CallbackQuery, callback_data: MenuCb, container: Container):
    """Выполнение улучшения катаны."""
    if not query.message:
        return
        
    if not await check_owner(query, callback_data.user_id):
        return
        
    try:
        result = await container.economy_service.upgrade_katana(query.from_user.id)
        
        is_upgraded = result["is_upgraded"]
        growth = result["growth"]
        new_length = result["new_length"]
        cost = result["cost"]
        
        text = Visuals.katana_upgrade_result(
            is_success=is_upgraded,
            growth=growth,
            length=new_length,
            cost=cost
        )
        
        # Показываем результат и кнопку назад в профиль
        back_markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👤 В профиль", callback_data=MenuCb(action="profile", user_id=query.from_user.id).pack())]
        ])
        
        await query.message.edit_text(text, parse_mode="HTML", reply_markup=back_markup)
        try:
            await query.answer()
        except TelegramBadRequest:
            pass
        
    except InsufficientFundsError as e:
        try:
            await query.answer(f"❌ Не хватает монет! Нужно {e.required:,.0f} 💰", show_alert=True)
        except TelegramBadRequest:
            pass
        await show_profile(query.message, container, query.from_user, is_edit=True)
        
    except CooldownError as e:
        try:
            await query.answer(f"⏳ {e}", show_alert=True)
        except TelegramBadRequest:
            pass
        
    except (UserNotFoundError, NoKatanaError) as e:
        try:
            await query.answer(f"❌ Ошибка: {e}", show_alert=True)
        except TelegramBadRequest:
            pass
        await show_profile(query.message, container, query.from_user, is_edit=True)
        
    except Exception as e:
        try:
            await query.answer(f"❌ Ошибка: {e}", show_alert=True)
        except TelegramBadRequest:
            pass


@router.callback_query(MenuCb.filter(F.action == "cancel"))
async def cb_cancel(query: CallbackQuery, callback_data: MenuCb, container: Container):
    """Отмена действия, возврат в профиль."""
    if not query.message:
        return
        
    if not await check_owner(query, callback_data.user_id):
        return

    await show_profile(query.message, container, query.from_user, is_edit=True)
    try:
        await query.answer()
    except TelegramBadRequest:
        pass


@router.callback_query(MenuCb.filter(F.action == "help"))
async def cb_help(query: CallbackQuery, callback_data: MenuCb):
    """Помощь."""
    if not query.message:
        return
        
    # Help доступен всем, но кнопку назад лучше проверить
    
    text = Visuals.help_card()
    back_markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data=MenuCb(action="back_to_start", user_id=query.from_user.id).pack())]
    ])
    
    await query.message.edit_text(text, parse_mode="HTML", reply_markup=back_markup)
    try:
        await query.answer()
    except TelegramBadRequest:
        pass


@router.callback_query(MenuCb.filter(F.action == "back_to_start"))
async def cb_back_to_start(query: CallbackQuery, callback_data: MenuCb):
    """Назад в главное меню."""
    if not query.message:
        return
        
    if not await check_owner(query, callback_data.user_id):
        return
        
    username = query.from_user.username
    mention = f"@{username}" if username else f"<b>{query.from_user.full_name}</b>"
    
    text = Visuals.start_menu(query.from_user.first_name)

    if query.message.chat.type == "private":
        text += "\n\nПроект существует в том числе на ваши пожертвования, если вам нравится бот можете поддержать автора <code>https://t.me/xrocket?start=inv_uBCMaE7YvzGJYwF</code>"
    
    await query.message.edit_text(
        f"{mention}\n\n{text}",
        parse_mode="HTML",
        reply_markup=get_start_keyboard(query.from_user.id)
    )
    try:
        await query.answer()
    except TelegramBadRequest:
        pass


@router.callback_query(MenuCb.filter(F.action.in_({"top_xp", "top_coins", "top_messages", "top_tickets", "top_streak"})))
async def cb_show_top(query: CallbackQuery, callback_data: MenuCb, container: Container):
    """Показать конкретный топ."""
    if not query.message:
        return
        
    if not await check_owner(query, callback_data.user_id):
        return
        
    action_map = {
        "top_xp": ("xp", "⚡ Топ по опыту"),
        "top_coins": ("coins", "💰 Богатейшие"),
        "top_messages": ("messages", "🗣 Самые активные"),
        "top_tickets": ("tickets", "🎫 Владельцы билетов"),
        "top_streak": ("streak", "🔥 Самые стойкие"),
    }
    
    field, title = action_map.get(callback_data.action)
    
    users = []
    if field == "xp":
        users = await container.user_service.get_top_by_xp(limit=10)
    elif field == "coins":
        users = await container.user_service.get_top_by_coins(limit=10)
    elif field == "messages":
        users = await container.user_service.get_top_by_messages(limit=10)
    elif field == "tickets":
        users = await container.user_service.get_top_by_tickets(limit=10)
    elif field == "streak":
        users = await container.user_service.get_top_by_streak(limit=10)
        
    text = Visuals.top_table(title.upper(), title.split()[0], users, field)
        
    back_markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data=MenuCb(action="top_menu", user_id=query.from_user.id).pack())]
    ])
    
    await query.message.edit_text(text, parse_mode="HTML", reply_markup=back_markup)
    try:
        await query.answer()
    except TelegramBadRequest:
        pass


@router.callback_query(MenuCb.filter(F.action == "exchange_menu"))
async def cb_exchange_menu(query: CallbackQuery, callback_data: MenuCb, container: Container):
    """Меню обмена."""
    if not query.message:
        return
        
    if not await check_owner(query, callback_data.user_id):
        return
        
    text = Visuals.exchange_info_card()
    
    await query.message.edit_text(
        text,
        reply_markup=get_exchange_keyboard(query.from_user.id),
        parse_mode="HTML"
    )
    try:
        await query.answer()
    except TelegramBadRequest:
        pass


@router.callback_query(MenuCb.filter(F.action == "achievements"))
async def cb_achievements(query: CallbackQuery, callback_data: MenuCb, container: Container):
    """Показать достижения."""
    if not query.message:
        return
        
    if not await check_owner(query, callback_data.user_id):
        return

    try:
        await query.answer()
    except TelegramBadRequest:
        pass
        
    achievements = await container.achievement_service.get_user_achievements(query.from_user.id)
    
    unlocked = achievements["unlocked"]
    locked = achievements["locked"]
    total = achievements["total"]
    unlocked_count = achievements["unlocked_count"]
    
    text = f"🏆 <b>Достижения ({unlocked_count}/{total})</b>\n\n"
    
    if unlocked:
        text += "<b>✅ Открытые:</b>\n"
        for ach in unlocked:
            text += f"• <b>{ach['name']}</b>\n"
    else:
        text += "У тебя пока нет достижений.\n"
        
    if locked:
        text += "\n<b>🔒 Закрытые (ближайшие):</b>\n"
        for ach in locked[:3]:
            text += f"• <b>{ach['name']}</b>\n"
            
    back_markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data=MenuCb(action="back_to_profile", user_id=query.from_user.id).pack())]
    ])
    
    await query.message.edit_text(text, parse_mode="HTML", reply_markup=back_markup)


@router.callback_query(MenuCb.filter(F.action == "buy_katana"))
async def cb_buy_katana(query: CallbackQuery, callback_data: MenuCb, container: Container):
    """Купить катану."""
    if not query.message:
        return
        
    if not await check_owner(query, callback_data.user_id):
        return
        
    try:
        result = await container.economy_service.buy_katana(query.from_user.id)
        
        if result["success"]:
            try:
                await query.answer("⚔️ Катана куплена! Поздравляю!", show_alert=True)
            except TelegramBadRequest:
                pass
            await show_profile(query.message, container, query.from_user, is_edit=True)
        else:
             reason = result.get("reason")
             if reason == "insufficient_funds":
                 try:
                    await query.answer(f"❌ Не хватает монет! Нужно {result['price']} 💰", show_alert=True)
                 except TelegramBadRequest:
                    pass
             elif reason == "already_has_katana":
                 try:
                    await query.answer("⚔️ У тебя уже есть катана!", show_alert=True)
                 except TelegramBadRequest:
                    pass
                 await show_profile(query.message, container, query.from_user, is_edit=True)
             else:
                 try:
                    await query.answer(f"❌ Ошибка: {reason}", show_alert=True)
                 except TelegramBadRequest:
                    pass
             
    except InsufficientFundsError as e:
        try:
            await query.answer(f"❌ Не хватает монет! Нужно {e.required} 💰", show_alert=True)
        except TelegramBadRequest:
            pass
    except Exception as e:
        try:
            await query.answer(f"❌ Ошибка: {e}", show_alert=True)
        except TelegramBadRequest:
            pass


@router.callback_query(MenuCb.filter(F.action == "exchange_coins_to_ticket"))
async def cb_exchange_coins_to_ticket(query: CallbackQuery, callback_data: MenuCb, container: Container):
    """Обмен монет на билет."""
    if not query.message:
        return
        
    if not await check_owner(query, callback_data.user_id):
        return
        
    try:
        result = await container.exchange_service.coins_to_ticket(query.from_user.id)
        
        if result["success"]:
            text = Visuals.exchange_result(
                direction="coins_to_ticket",
                amount_from=result["coins_spent"],
                amount_to=1,
                currency_from="💰",
                currency_to="🎫"
            )
            text += f"\n\n🎫 Ваш билет: <code>{result['ticket_code']}</code>"
            await query.message.edit_text(text, parse_mode="HTML", reply_markup=get_exchange_keyboard(query.from_user.id))
            try:
                await query.answer("🎫 Билет куплен!")
            except TelegramBadRequest:
                pass
        else:
            try:
                await query.answer(f"❌ Ошибка: {result.get('error')}", show_alert=True)
            except TelegramBadRequest:
                pass
            
    except InsufficientFundsError as e:
        try:
            await query.answer(f"❌ Не хватает монет! Нужно {e.required} 💰", show_alert=True)
        except TelegramBadRequest:
            pass
    except Exception as e:
        try:
            await query.answer(f"❌ Ошибка: {e}", show_alert=True)
        except TelegramBadRequest:
            pass


@router.callback_query(MenuCb.filter(F.action == "exchange_ticket_to_coins"))
async def cb_exchange_ticket_to_coins(query: CallbackQuery, callback_data: MenuCb, container: Container):
    """Обмен билета на монеты."""
    if not query.message:
        return
        
    if not await check_owner(query, callback_data.user_id):
        return
        
    username = query.from_user.username
    mention = f"@{username}" if username else f"<b>{query.from_user.full_name}</b>"

    try:
        result = await container.exchange_service.ticket_to_coins(query.from_user.id)
        
        if result["success"]:
            text = Visuals.exchange_result(
                direction="ticket_to_coins",
                amount_from=1,
                amount_to=result["coins_received"],
                currency_from="🎫",
                currency_to="💰"
            )
            await query.message.edit_text(f"{mention}\n\n{text}", parse_mode="HTML", reply_markup=get_exchange_keyboard(query.from_user.id))
            try:
                await query.answer(f"💰 Получено {result['coins_received']} монет!")
            except TelegramBadRequest:
                pass
        else:
            try:
                await query.answer(f"❌ Ошибка: {result.get('error')}", show_alert=True)
            except TelegramBadRequest:
                pass
            
    except InsufficientTicketsError:
        try:
            await query.answer("❌ У тебя нет билетов!", show_alert=True)
        except TelegramBadRequest:
            pass
    except Exception as e:
        try:
            await query.answer(f"❌ Ошибка: {e}", show_alert=True)
        except TelegramBadRequest:
            pass
