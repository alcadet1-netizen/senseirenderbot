from __future__ import annotations
import logging
import re
from decimal import Decimal

from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.bot.filters import AdminFilter, PrivateChatFilter
from src.bot.states.sensei_check import SenseiCheckCreateStates, SenseiCheckPresetStates
from src.core.config import settings
from src.core.container import Container
from src.core.visuals import Visuals
from src.bot.presenters.sensei_check_presenter import SenseiCheckPresenter

from .shared import _ui_render, _parse_channels_input

logger = logging.getLogger(__name__)

router = Router(name="sensei_check_admin")

# ==================== MENU & NAVIGATION ====================

@router.message(Command("senseicheck"), AdminFilter())
async def cmd_senseicheck(message: Message, state: FSMContext) -> None:
    """Главное меню (Ultimate)."""
    await state.clear()
    
    # Check if arguments provided for quick create (legacy support)
    args = (message.text or "").split()[1:]
    if args:
        # Redirect to create flow directly if args exist
        amount = None
        count = None
        if len(args) >= 1:
            try:
                amount = Decimal(args[0].replace(",", "."))
            except:
                pass
        if len(args) >= 2:
            try:
                count = int(args[1])
            except:
                pass

        if amount:
            await state.update_data(channels=[], referral_percent=0)
            if count:
                await state.update_data(amount_ton=str(amount), activation_limit=count)
                await state.set_state(SenseiCheckCreateStates.confirm)
                await _ui_render(
                    state=state,
                    anchor=message,
                    text=SenseiCheckPresenter.render_fast_confirm(str(amount), count),
                    reply_markup=SenseiCheckPresenter.fast_confirm_kb()
                )
            else:
                await state.update_data(amount_ton=str(amount))
                await state.set_state(SenseiCheckCreateStates.waiting_activations)
                await _ui_render(
                    state=state, 
                    anchor=message,
                    text=SenseiCheckPresenter.render_activations_prompt(),
                    reply_markup=SenseiCheckPresenter.activations_kb()
                )
            return

    # Normal menu
    try:
        await message.delete()
    except:
        pass
        
    await _ui_render(
        state=state,
        anchor=message,
        text=SenseiCheckPresenter.render_main_menu(),
        reply_markup=_main_menu_kb() # Enhanced KB with presets
    )

@router.callback_query(F.data == "scheckult:menu")
async def cb_back_menu(query: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if not query.message: return
    
    await _ui_render(
        state=state,
        anchor=query.message,
        text=SenseiCheckPresenter.render_main_menu(),
        reply_markup=_main_menu_kb()
    )

# ==================== PRESETS MANAGEMENT ====================

@router.callback_query(F.data == "scheckult:presets")
async def cb_presets_list(query: CallbackQuery, container: Container, state: FSMContext) -> None:
    if not query.message: return
    
    presets = await container.sensei_check_service.get_channel_presets()
    
    text = f"📋 <b>Управление пресетами каналов</b>\n\nВсего: {len(presets)}"
    kb = _presets_list_kb(presets)
    
    await _ui_render(state=state, anchor=query.message, text=text, reply_markup=kb)

@router.callback_query(F.data == "scheckult:preset:add")
async def cb_preset_add(query: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SenseiCheckPresetStates.waiting_name)
    await query.answer()
    if not query.message: return
    
    await _ui_render(
        state=state, 
        anchor=query.message,
        text="📝 <b>Введите название для пресета</b>\n\nНапример: <i>Спонсоры Февраль</i>",
        reply_markup=SenseiCheckPresenter.nav_kb(back="scheckult:presets", cancel="scheckult:menu")
    )

@router.message(SenseiCheckPresetStates.waiting_name)
async def step_preset_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()[:64]
    await state.update_data(preset_name=name)
    await state.set_state(SenseiCheckPresetStates.waiting_channels)
    
    await _ui_render(
        state=state,
        anchor=message,
        text=f"📢 <b>Пресет: {name}</b>\n\nПришлите список каналов (юзернеймы или ID) через пробел или новой строкой.\nТакже можно переслать сообщения из каналов.",
        reply_markup=SenseiCheckPresenter.nav_kb(back="scheckult:presets", cancel="scheckult:menu")
    )

@router.message(SenseiCheckPresetStates.waiting_channels)
async def step_preset_channels(message: Message, state: FSMContext, container: Container) -> None:
    text = message.text or ""
    new_channels = _parse_channels_input(text)
    
    # Поддержка пересылки сообщений из каналов/чатов (forward_origin — новое API)
    fo = getattr(message, "forward_origin", None)
    if fo and getattr(fo, "type", None) == "channel" and getattr(fo, "chat", None):
        chat = fo.chat
        if getattr(chat, "username", None):
            new_channels.append(f"@{chat.username}")
        else:
            new_channels.append(str(chat.id))
    elif message.forward_from_chat:
        if message.forward_from_chat.username:
            new_channels.append(f"@{message.forward_from_chat.username}")
        else:
            new_channels.append(str(message.forward_from_chat.id))
            
    if not new_channels:
        await message.answer("❌ Не найдено каналов. Попробуй еще раз.")
        return
        
    data = await state.get_data()
    name = data.get("preset_name", "Unnamed")
    
    await container.sensei_check_service.create_channel_preset(name, new_channels)
    
    await message.answer(f"{Visuals.check()} Пресет <b>{name}</b> сохранен ({len(new_channels)} каналов)!", parse_mode="HTML")
    await state.clear()
    
    presets = await container.sensei_check_service.get_channel_presets()
    kb = _presets_list_kb(presets)
    await message.answer(
        f"📋 <b>Управление пресетами каналов</b>\n\nВсего: {len(presets)}",
        reply_markup=kb,
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("scheckult:preset:view:"))
async def cb_preset_view(query: CallbackQuery, container: Container) -> None:
    if not query.message: return
    preset_id = query.data.split(":")[-1]
    preset = await container.sensei_check_service.get_channel_preset(preset_id)
    if preset:
        text = f"Пресет: {preset['name']}\nКаналы: {', '.join(preset['channels'])}"
        await query.answer(text, show_alert=True)
    else:
        await query.answer("Пресет не найден", show_alert=True)

@router.callback_query(F.data.startswith("scheckult:preset:del:"))
async def cb_preset_del(query: CallbackQuery, container: Container, state: FSMContext) -> None:
    if not query.from_user or query.from_user.id not in settings.admin_ids:
        return
    pid = query.data.split(":")[-1]  # Keep as string
    await container.sensei_check_service.delete_channel_preset(pid)
    await query.answer("🗑 Пресет удален")
    await cb_presets_list(query, container, state)

# ==================== CHECK CREATION WIZARD ====================

@router.callback_query(F.data == "scheckult:create")
async def cb_create_start(query: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.update_data(channels=[], referral_percent=0)
    await state.set_state(SenseiCheckCreateStates.waiting_amount)
    
    if not query.message: return
    
    await _ui_render(
        state=state,
        anchor=query.message,
        text=SenseiCheckPresenter.render_amount_prompt(),
        reply_markup=SenseiCheckPresenter.amount_kb()
    )

# --- Amount ---
@router.callback_query(SenseiCheckCreateStates.waiting_amount, F.data.startswith("scheckadm:amt:"))
async def sc_amount_cb(query: CallbackQuery, state: FSMContext) -> None:
    amt = query.data.split(":")[-1]
    await state.update_data(amount_ton=amt)
    await state.set_state(SenseiCheckCreateStates.waiting_activations)
    if not query.message: return
    await _ui_render(
        state=state,
        anchor=query.message,
        text=SenseiCheckPresenter.render_activations_prompt(),
        reply_markup=SenseiCheckPresenter.activations_kb()
    )

@router.message(SenseiCheckCreateStates.waiting_amount)
async def sc_amount_msg(message: Message, state: FSMContext) -> None:
    try:
        val = float(message.text.replace(",", "."))
        if val <= 0: raise ValueError
        await state.update_data(amount_ton=str(val))
        await state.set_state(SenseiCheckCreateStates.waiting_activations)
        await _ui_render(
            state=state,
            anchor=message,
            text=SenseiCheckPresenter.render_activations_prompt(),
            reply_markup=SenseiCheckPresenter.activations_kb()
        )
    except:
        await message.reply("❌ Некорректная сумма. Введите число (например 0.1)")

# --- Activations ---
@router.callback_query(SenseiCheckCreateStates.waiting_activations, F.data.startswith("scheckadm:act:"))
async def sc_act_cb(query: CallbackQuery, state: FSMContext) -> None:
    act = query.data.split(":")[-1]
    await state.update_data(activation_limit=int(act))
    if query.message:
        await _show_dashboard(query.message, state)

@router.message(SenseiCheckCreateStates.waiting_activations)
async def sc_act_msg(message: Message, state: FSMContext) -> None:
    try:
        val = int(message.text)
        if val <= 0: raise ValueError
        await state.update_data(activation_limit=val)
        await _show_dashboard(message, state)
    except:
        await message.reply("❌ Некорректное число.")

# --- Channels ---
async def _ask_channels(anchor: Message, state: FSMContext) -> None:
    await state.set_state(SenseiCheckCreateStates.waiting_channels)
    data = await state.get_data()
    channels = data.get("channels", [])
    
    await _ui_render(
        state=state,
        anchor=anchor,
        text=SenseiCheckPresenter.render_channels_status(channels),
        reply_markup=_channels_kb_with_presets(channels) # Custom KB
    )

@router.message(SenseiCheckCreateStates.waiting_channels)
async def sc_channels_msg(message: Message, state: FSMContext) -> None:
    txt = message.text or ""
    new_ch = _parse_channels_input(txt)
    
    # Поддержка пересылки сообщений (forward_origin — новое API, forward_from_chat — старое)
    fo = getattr(message, "forward_origin", None)
    if fo and getattr(fo, "type", None) == "channel" and getattr(fo, "chat", None):
        chat = fo.chat
        if getattr(chat, "username", None):
            new_ch.append(f"@{chat.username}")
        else:
            new_ch.append(str(chat.id))
    elif message.forward_from_chat:
        if message.forward_from_chat.username:
            new_ch.append(f"@{message.forward_from_chat.username}")
        else:
            new_ch.append(str(message.forward_from_chat.id))

    data = await state.get_data()
    cur = data.get("channels", [])
    updated = list(dict.fromkeys(cur + new_ch))
    
    await state.update_data(channels=updated)
    await _ask_channels(message, state)

@router.callback_query(SenseiCheckCreateStates.waiting_channels, F.data.startswith("scheckadm:chdel:"))
async def sc_ch_del(query: CallbackQuery, state: FSMContext) -> None:
    idx = int(query.data.split(":")[-1])
    data = await state.get_data()
    channels = data.get("channels", [])
    if 0 <= idx < len(channels):
        channels.pop(idx)
        await state.update_data(channels=channels)
    if not query.message: return
    await _ask_channels(query.message, state)

@router.callback_query(SenseiCheckCreateStates.waiting_channels, F.data == "scheckadm:chclear")
async def sc_ch_clear(query: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(channels=[])
    if not query.message: return
    await _ask_channels(query.message, state)

@router.callback_query(SenseiCheckCreateStates.waiting_channels, F.data == "scheckadm:chpreset")
async def sc_ch_preset_list(query: CallbackQuery, container: Container, state: FSMContext) -> None:
    # DISABLED to avoid migrations
    await query.answer("Эта функция временно отключена (требуется миграция БД)", show_alert=True)


@router.callback_query(SenseiCheckCreateStates.waiting_channels, F.data == "scheckadm:chnext")
async def sc_ch_next(query: CallbackQuery, state: FSMContext) -> None:
    # Возврат в дашборд
    if not query.message: return
    await _show_dashboard(query.message, state)

# --- Referral ---
@router.callback_query(SenseiCheckCreateStates.waiting_referral, F.data.startswith("scheckadm:ref:"))
async def sc_ref_cb(query: CallbackQuery, state: FSMContext) -> None:
    ref_pct = int(query.data.split(":")[-1])
    await state.update_data(referral_percent=ref_pct)
    # Возврат в дашборд
    if not query.message: return
    await _show_dashboard(query.message, state)

# --- Text ---
@router.callback_query(SenseiCheckCreateStates.waiting_text, F.data == "scheckadm:skip:text")
async def sc_text_skip(query: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(message_text=None)
    if not query.message: return
    await _show_dashboard(query.message, state)

@router.message(SenseiCheckCreateStates.waiting_text)
async def sc_text_msg(message: Message, state: FSMContext) -> None:
    await state.update_data(message_text=message.html_text) # Use html_text to preserve formatting
    await _ask_photo(message, state)

async def _ask_photo(anchor: Message, state: FSMContext) -> None:
    await state.set_state(SenseiCheckCreateStates.waiting_photo)
    await _ui_render(
        state=state,
        anchor=anchor,
        text=SenseiCheckPresenter.render_photo_prompt(),
        reply_markup=SenseiCheckPresenter.nav_kb(skip="scheckadm:skip:photo", cancel="scheckadm:cancel")
    )

# --- Photo ---
@router.callback_query(SenseiCheckCreateStates.waiting_photo, F.data == "scheckadm:skip:photo")
async def sc_photo_skip(query: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(photo_file_id=None, video_file_id=None)
    if not query.message: return
    await _show_dashboard(query.message, state)

@router.message(SenseiCheckCreateStates.waiting_photo)
async def sc_photo_msg(message: Message, state: FSMContext) -> None:
    if message.photo:
        await state.update_data(photo_file_id=message.photo[-1].file_id)
    elif message.video:
        await state.update_data(video_file_id=message.video.file_id)
    else:
        await message.reply("📸 Пришлите фото/видео или нажмите Пропустить.")
        return
        
    await _show_dashboard(message, state)

async def _ask_password(anchor: Message, state: FSMContext) -> None:
    await state.set_state(SenseiCheckCreateStates.waiting_password)
    await _ui_render(
        state=state,
        anchor=anchor,
        text=SenseiCheckPresenter.render_admin_password_prompt(),
        reply_markup=SenseiCheckPresenter.password_input_kb()
    )

# --- Password ---
@router.callback_query(SenseiCheckCreateStates.waiting_password, F.data == "scheckadm:skip:password")
async def sc_pwd_skip(query: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(password=None)
    await _show_dashboard(query.message, state)

@router.callback_query(SenseiCheckCreateStates.waiting_password, F.data == "scheckadm:pwd:gen")
async def sc_pwd_gen(query: CallbackQuery, state: FSMContext) -> None:
    if not query.from_user or query.from_user.id not in settings.admin_ids:
        return
    import secrets
    p1 = secrets.token_hex(2)
    p2 = secrets.token_hex(2)
    pwd = f"{p1}-{p2}"
    await state.update_data(password=pwd)
    
    if not query.message: return
    # Показываем пароль сразу в дашборде (без отдельного сообщения)
    await _show_dashboard(query.message, state)
    try:
        await query.answer(f"🔑 Пароль: {pwd}")
    except Exception:
        pass

@router.message(SenseiCheckCreateStates.waiting_password)
async def sc_pwd_msg(message: Message, state: FSMContext) -> None:
    pwd = message.text.strip()
    await state.update_data(password=pwd)
    await _show_dashboard(message, state)

# --- Edit Handlers (from Dashboard) ---
@router.callback_query(SenseiCheckCreateStates.confirm, F.data.startswith("scheckadm:edit:"))
async def sc_edit_field(query: CallbackQuery, state: FSMContext) -> None:
    field = query.data.split(":")[-1]
    if not query.message: return
    
    if field == "amount":
        await state.set_state(SenseiCheckCreateStates.waiting_amount)
        await _ui_render(state=state, anchor=query.message, text=SenseiCheckPresenter.render_amount_prompt(), reply_markup=SenseiCheckPresenter.amount_kb())
    elif field == "activations":
        await state.set_state(SenseiCheckCreateStates.waiting_activations)
        await _ui_render(state=state, anchor=query.message, text=SenseiCheckPresenter.render_activations_prompt(), reply_markup=SenseiCheckPresenter.activations_kb())
    elif field == "channels":
        await _ask_channels(query.message, state)
    elif field == "password":
        await _ask_password(query.message, state)
    elif field == "referral":
        await state.set_state(SenseiCheckCreateStates.waiting_referral)
        await _ui_render(state=state, anchor=query.message, text=SenseiCheckPresenter.render_referral_prompt(), reply_markup=SenseiCheckPresenter.referral_kb())
    elif field == "text":
        await state.set_state(SenseiCheckCreateStates.waiting_text)
        await _ui_render(state=state, anchor=query.message, text=SenseiCheckPresenter.render_text_prompt(), reply_markup=SenseiCheckPresenter.nav_kb(skip="scheckadm:skip:text", cancel="scheckadm:cancel"))
    elif field == "settings":
        await _show_dashboard(query.message, state)

@router.callback_query(F.data == "scheckadm:back:dashboard")
async def sc_back_to_dash(query: CallbackQuery, state: FSMContext) -> None:
    if not query.message: return
    await _show_dashboard(query.message, state)

# --- Dashboard & Confirm ---
async def _show_dashboard(anchor: Message, state: FSMContext) -> None:
    await state.set_state(SenseiCheckCreateStates.confirm)
    data = await state.get_data()
    
    await _ui_render(
        state=state,
        anchor=anchor,
        text=SenseiCheckPresenter.render_dashboard(data),
        reply_markup=SenseiCheckPresenter.dashboard_kb(data)
    )

@router.callback_query(SenseiCheckCreateStates.confirm, F.data == "scheckadm:create")
async def sc_create_confirm(query: CallbackQuery, state: FSMContext, container: Container) -> None:
    if not query.message: return
    
    data = await state.get_data()
    ui_mid = data.get("ui_mid")
    
    try:
        code = await container.sensei_check_service.create_check(
            created_by=query.from_user.id,
            channels=data.get("channels"),
            amount_ton=data.get("amount_ton"),
            activation_limit=data.get("activation_limit"),
            referral_percent=data.get("referral_percent", 0),
            message_text=data.get("message_text"),
            photo_file_id=data.get("photo_file_id"),
            video_file_id=data.get("video_file_id"),
            password=data.get("password")
        )
        
        # Success
        info = await container.sensei_check_service.get_check_info(query.bot, code)
        if not info: raise Exception("Check not found after creation")
        
        # Cleanup UI
        if ui_mid:
            try:
                await query.bot.delete_message(chat_id=query.message.chat.id, message_id=int(ui_mid))
            except:
                pass
        
        # Show result
        await query.message.answer(
            f"✅ <b>Чек создан!</b>\n\nКод: <code>{code}</code>\nСсылка: {info.link}",
            reply_markup=SenseiCheckPresenter.share_direct_kb(info.link, code),
            parse_mode="HTML"
        )
        await state.clear()
        
    except Exception as e:
        logger.error(f"Failed to create check: {e}")
        await query.answer(f"{Visuals.cross()} Ошибка: {e}", show_alert=True)

@router.callback_query(F.data == "scheckadm:cancel")
async def sc_cancel(query: CallbackQuery, state: FSMContext) -> None:
    if not query.from_user or query.from_user.id not in settings.admin_ids:
        return
    await state.clear()
    await query.answer("❌ Отменено")
    if query.message:
        try:
            await query.message.delete()
        except Exception:
            pass
    
# ==================== HELPERS ====================

def _main_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Новый чек", callback_data="scheckult:create")
    builder.button(text="📋 Все чеки", callback_data="scheckult:list:0")
    builder.button(text="📌 Пресеты каналов", callback_data="scheckult:presets")
    builder.button(text="🔗 Реф.ссылки", callback_data="scheckult:reflinks:0")
    builder.adjust(1)
    return builder.as_markup()

def _presets_list_kb(presets: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if presets:
        for p in presets:
            builder.button(text=f"📂 {p['name']}", callback_data=f"scheckult:preset:view:{p['id']}")
            builder.button(text="❌", callback_data=f"scheckult:preset:del:{p['id']}")

    builder.button(text="➕ Добавить пресет", callback_data="scheckult:preset:add")
    builder.button(text="↩️ В меню", callback_data="scheckult:menu")
    builder.adjust(2 if presets else 1)
    return builder.as_markup()

def _channels_kb_with_presets(channels: list[str]) -> InlineKeyboardMarkup:
    # Use existing from presenter but injection extra button?
    # Or just rebuild manually since we want custom behavior
    rows: list[list[InlineKeyboardButton]] = []
    
    if channels:
         for idx, ch in enumerate(channels[:10]):
              rows.append([InlineKeyboardButton(text=f"❌ {ch}", callback_data=f"scheckadm:chdel:{idx}")])
         if len(channels) > 10:
              rows.append([InlineKeyboardButton(text=f"...и еще {len(channels)-10}", callback_data="noop")])

    # Preset button (REMOVED to avoid migrations)
    # rows.append([InlineKeyboardButton(text="📂 Выбрать из пресетов", callback_data="scheckadm:chpreset")])
    
    nav = []
    nav.append(InlineKeyboardButton(text="⬅️ Очистить", callback_data="scheckadm:chclear"))
    nav.append(InlineKeyboardButton(text="✅ Готово", callback_data="scheckadm:chnext"))
    rows.append(nav)
    
    back_row = [InlineKeyboardButton(text="🔙 Назад в дашборд", callback_data="scheckadm:back:dashboard")]
    rows.append(back_row)
    
    return InlineKeyboardMarkup(inline_keyboard=rows)

@router.callback_query(F.data.startswith("scheckult:list:"))
async def cb_list_checks(query: CallbackQuery, container: Container) -> None:
    if not query.message: return
    offset = int(query.data.split(":")[-1])
    try:
        all_checks = await container.sensei_check_service.get_all_checks()
        text = SenseiCheckPresenter.render_checks_list(all_checks, offset, 5)
        kb = SenseiCheckPresenter.checks_list_kb(all_checks, len(all_checks), offset, 5)

        await query.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception as e:
        logger.error(f"List error: {e}")
        await query.answer("Error")

@router.callback_query(F.data.startswith("scheckult:reflinks:"))
async def cb_reflinks(query: CallbackQuery, container: Container) -> None:
    if not query.message: return
    offset = int(query.data.split(":")[-1])
    limit = 3
    try:
        all_checks = await container.sensei_check_service.get_all_checks()
        total = len(all_checks)
        # Build text header
        text = (
            f"🔗 <b>РЕФЕРАЛЬНЫЕ ССЫЛКИ</b>\n\n"
            f"Всего: {total}\n\n"
            f"<i>Нажмите на ссылку, чтобы открыть её.</i>"
        )
        # Build keyboard with buttons for each link
        builder = InlineKeyboardBuilder()
        for check in all_checks[offset:offset+limit]:
            code = check.get("code", "?")
            me = await query.bot.get_me()
            bot_username = me.username
            ref_link = f"https://t.me/{bot_username}?start=check_{code}_{query.from_user.id}"
            # Create button showing short link
            short_ref = ref_link[:35] + "..." if len(ref_link) > 35 else ref_link
            builder.button(text=f"🔗 {short_ref}", url=ref_link)
        builder.adjust(1)  # Each button on its own row
        # Navigation
        nav_row = []
        if offset > 0:
            nav_row.append(InlineKeyboardButton(text="◀ Назад", callback_data=f"scheckult:reflinks:{max(0, offset-limit)}"))
        if offset + limit < total:
            nav_row.append(InlineKeyboardButton(text="Далее ▶", callback_data=f"scheckult:reflinks:{offset+limit}"))
        if nav_row:
            builder.row(*nav_row)
        # Menu button
        builder.row(InlineKeyboardButton(text="↩️ В меню", callback_data="scheckult:menu"))
        kb = builder.as_markup()
        await query.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        pass

@router.callback_query(F.data.startswith("scheckult:view:"))
async def cb_view_check(query: CallbackQuery, container: Container) -> None:
    if not query.message: return
    code = query.data.split(":")[-1]
    try:
        check_data = await container.sensei_check_service.get_check_public_view(query.bot, code)
        if not check_data:
            await query.answer("Чек не найден", show_alert=True)
            return
            
        stats = await container.sensei_check_service.get_advanced_stats(code)
        check_data.update(stats)
        
        text = SenseiCheckPresenter.render_check_detail(check_data, check_data.get('referral_link'))
        kb = SenseiCheckPresenter.check_detail_kb(code, can_delete=check_data.get('is_active', False))
        await query.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception as e:
        logger.error(f"View error: {e}")
        await query.answer("Ошибка просмотра", show_alert=True)

@router.callback_query(F.data.startswith("scheckult:burn:"))
async def cb_burn(query: CallbackQuery, container: Container) -> None:
    if not query.from_user or query.from_user.id not in settings.admin_ids:
        await query.answer("Нет прав", show_alert=True)
        return
        
    code = query.data.split(":")[-1]
    success, msg, refund_ton = await container.sensei_check_service.burn_check(code, query.from_user.id)
    
    if success:
        await query.answer(f"🔥 Чек сожжен! Возвращено {refund_ton:.4f} TON.", show_alert=True)
        # Return to main list
        try:
             await cb_list_checks(query, container)
        except Exception:
             pass
    else:
        await query.answer(msg, show_alert=True)

@router.callback_query(F.data.startswith("scheckult:delete:"))
async def cb_del(query: CallbackQuery, container: Container) -> None:
    if not query.from_user or query.from_user.id not in settings.admin_ids:
        return
    code = query.data.split(":")[-1]
    await container.sensei_check_service.admin_delete_check(code)
    await query.answer("Чек удален")
    # После удаления показываем список чеков с начала
    if query.message:
        all_checks = await container.sensei_check_service.get_all_checks()
        text = SenseiCheckPresenter.render_checks_list(all_checks, 0, 5)
        kb = SenseiCheckPresenter.checks_list_kb(all_checks, len(all_checks), 0, 5)
        await query.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
