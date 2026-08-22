from __future__ import annotations
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.filters import CommandObject

from src.core.container import Container
from src.core.visuals import Visuals
from src.bot.presenters.sensei_check_presenter import SenseiCheckPresenter
from src.bot.states.sensei_check import SenseiCheckActivateStates
from src.services.sensei_check_service import ActivationError, ActivationResult


logger = logging.getLogger(__name__)

router = Router(name="sensei_check_user")

# ==================== INLINE QUERY ====================

@router.inline_query(F.query.startswith("sc_"))
async def sc_inline_query(query: InlineQuery, container: Container) -> None:
    code = query.query.strip()
    # Check exists?
    info = await container.sensei_check_service.get_check_info(query.bot, code)
    if not info:
        return

    results = SenseiCheckPresenter.build_inline_results(info.__dict__, info.amount_ton, info.link)
    await query.answer(results, cache_time=5, is_personal=True)

# ==================== ACTIVATION (DEEP LINK) ====================
# Deep link handling is usually in user_commands.py /start.
# but we can handle specific payload here if we use deep linking filters or just let /start handler call a service/function.
# In the original code, it seemed /start processing was in user_commands.py. 
# We need to make sure user_commands.py calls the service or redirects here.
# For now, we assume standard button activation via callback.

# ==================== ACTIVATION (CALLBACK) ====================

@router.callback_query(F.data.startswith("scheck:activate:"))
async def sc_user_activate(query: CallbackQuery, container: Container, state: FSMContext) -> None:
    if not query.from_user or not query.message:
        return
    
    parts = query.data.split(":")
    code = parts[2]
    user_id = query.from_user.id
    
    # Получаем referrer_id из Redis (кто поделился ссылкой чека)
    referrer_id = None
    try:
        ref_raw = await container.redis.get(f"user:{user_id}:check_referrer")
        if ref_raw:
            if isinstance(ref_raw, bytes):
                ref_raw = ref_raw.decode()
            referrer_id = int(ref_raw)
    except Exception as e:
        logger.debug(f"Failed to get check referrer from Redis: {e}")
    
    data = await state.get_data()
    captcha_solved = data.get("captcha_solved", False)
    password = data.get("password")
    
    # Активация чека
    res = await container.sensei_check_service.activate_check(
        query.bot,
        code=code,
        user_id=user_id,
        password=password,
        referrer_id=referrer_id,
        captcha_solved=captcha_solved,
    )
    
    # Handle success/errors
    await _handle_activation_response(query.message, query, state, res, code)

async def _handle_activation_response(
    message: Message, 
    query: CallbackQuery | None, 
    state: FSMContext, 
    res: ActivationResult, 
    code: str
) -> None:
    if res.success:
        if res.already_activated:
            if query: await query.answer(f"⚠️ Вы уже активировали этот чек!", show_alert=True)
            else: await message.answer(f"⚠️ Вы уже активировали этот чек!")
        else:
            text = SenseiCheckPresenter.render_activation_success(
                res.amount_ton, 
                is_referral=res.referral_paid, 
                ref_amount=res.referral_amount_ton
            )
            try:
                if query and query.message.via_bot:
                     await query.answer(f"✅ Активировано! +{res.amount_ton} GRAM", show_alert=True)
                else:
                     await message.answer(text, parse_mode="HTML")
                     if query: await query.answer()
            except:
                pass
        return

    # Обработка ошибок активации
    err_type = res.error
    
    if err_type == ActivationError.CAPTCHA_REQUIRED:
        from random import randint
        a, b = randint(1, 10), randint(1, 10)
        answer = str(a + b)
        await state.update_data(check_code=code, captcha_answer=answer)
        await state.set_state(SenseiCheckActivateStates.waiting_captcha)
        try:
            msg = await message.answer(
                f"🛡 <b>Защита от ботов</b>\nСколько будет: <b>{a} + {b}</b> ?\n\n<i>Отправьте ответ цифрами.</i>",
                parse_mode="HTML",
                reply_markup=SenseiCheckPresenter.nav_kb(cancel="scheck:cancel_act")
            )
            await state.update_data(ui_mid=msg.message_id)
        except Exception:
            pass
        if query: await query.answer()
        return
        
    if err_type == ActivationError.NOT_SUBSCRIBED:
        missing = res.missing_channels or []
        all_channels = res.all_channels or missing
        
        rows = []
        for ch in missing:
            label = ch
            url = f"https://t.me/{ch.lstrip('@')}" if ch.startswith("@") else None
            if url:
                rows.append([InlineKeyboardButton(text=f"📢 {label}", url=url)])
        rows.append([InlineKeyboardButton(text="🔄 Проверить подписку", callback_data=f"scheck:activate:{code}")])
        new_kb = InlineKeyboardMarkup(inline_keyboard=rows)
        
        if query: await query.answer("❌ Подпишитесь на все каналы!", show_alert=True)
        try:
            txt = f"<b>🔒 Для активации подпишись:</b>\n\n"
            for ch in all_channels:
                if ch in missing:
                    txt += f"❌ {ch}\n"
                else:
                    txt += f"✅ {ch}\n"
            await message.answer(txt, reply_markup=new_kb, parse_mode="HTML")
        except Exception:
            pass
        return

    if err_type == ActivationError.PASSWORD_REQUIRED:
        await state.update_data(check_code=code)
        await state.set_state(SenseiCheckActivateStates.waiting_password)
        try:
            msg = await message.answer(
                SenseiCheckPresenter.render_user_password_prompt(),
                parse_mode="HTML",
                reply_markup=SenseiCheckPresenter.nav_kb(cancel="scheck:cancel_act")
            )
            await state.update_data(ui_mid=msg.message_id)
        except Exception:
            pass
        if query: await query.answer()
        return

    if err_type == ActivationError.WRONG_PASSWORD:
        if query: await query.answer("❌ Неверный пароль", show_alert=True)
        else:
            msg = await message.answer(
                SenseiCheckPresenter.render_password_error("wrong"),
                parse_mode="HTML",
                reply_markup=SenseiCheckPresenter.nav_kb(cancel="scheck:cancel_act")
            )
            await state.update_data(ui_mid=msg.message_id)
        return

    if err_type == ActivationError.EXHAUSTED:
        await query.answer("❌ Чек закончился 😔", show_alert=True)
        return

    if err_type == ActivationError.INACTIVE:
        await query.answer("❌ Чек деактивирован ⛔", show_alert=True)
        return

    if err_type == ActivationError.EXPIRED:
        await query.answer("❌ Срок чека истёк 🕐", show_alert=True)
        return

    if err_type == ActivationError.AMOUNT_TOO_SMALL:
        await query.answer("❌ Сумма чека слишком мала для выплаты", show_alert=True)
        return

    # Generic error
    await query.answer(f"❌ Ошибка: {err_type}", show_alert=True)


@router.callback_query(F.data == "scheck:cancel_act")
async def sc_cancel_act(query: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    try:
        await query.message.delete()
    except Exception:
        pass
    try:
        await query.answer()
    except Exception:
        pass

@router.message(SenseiCheckActivateStates.waiting_password)
async def sc_pwd_input(message: Message, state: FSMContext, container: Container) -> None:
    if not message.from_user or not message.text:
        return
    pwd = message.text.strip()
    data = await state.get_data()
    code = data.get("check_code")
    ui_mid = data.get("ui_mid")
    
    if not code:
        await state.clear()
        return

    # Получаем referrer_id из Redis
    referrer_id = None
    try:
        ref_raw = await container.redis.get(f"user:{message.from_user.id}:check_referrer")
        if ref_raw:
            if isinstance(ref_raw, bytes):
                ref_raw = ref_raw.decode()
            referrer_id = int(ref_raw)
    except Exception:
        pass

    res = await container.sensei_check_service.activate_check(
        message.bot,
        code=code,
        user_id=message.from_user.id,
        password=pwd,
        referrer_id=referrer_id,
        captcha_solved=data.get("captcha_solved", False)
    )
    
    # Cleanup input and prompt
    try:
        await message.delete()
    except Exception:
        pass
    if ui_mid:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=ui_mid)
        except Exception:
            pass

    await _handle_activation_response(message, None, state, res, code)

@router.message(SenseiCheckActivateStates.waiting_captcha)
async def sc_captcha_input(message: Message, state: FSMContext, container: Container) -> None:
    if not message.from_user or not message.text:
        return
    ans = message.text.strip()
    data = await state.get_data()
    correct = data.get("captcha_answer")
    code = data.get("check_code")
    ui_mid = data.get("ui_mid")
    
    if not code or not correct:
        await state.clear()
        return

    try:
        await message.delete()
    except Exception:
        pass

    if ans != correct:
        msg = await message.answer(
            "❌ <b>Неверный ответ!</b> Попробуйте снова или отмените.",
            parse_mode="HTML",
            reply_markup=SenseiCheckPresenter.nav_kb(cancel="scheck:cancel_act")
        )
        await state.update_data(ui_mid=msg.message_id)
        if ui_mid:
            try:
                await message.bot.delete_message(chat_id=message.chat.id, message_id=ui_mid)
            except Exception:
                pass
        return

    await state.update_data(captcha_solved=True)
    referrer_id = None
    try:
        ref_raw = await container.redis.get(f"user:{message.from_user.id}:check_referrer")
        if ref_raw:
            referrer_id = int(ref_raw.decode() if isinstance(ref_raw, bytes) else ref_raw)
    except Exception:
        pass

    res = await container.sensei_check_service.activate_check(
        message.bot,
        code=code,
        user_id=message.from_user.id,
        referrer_id=referrer_id,
        captcha_solved=True
    )
    
    if ui_mid:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=ui_mid)
        except Exception:
            pass

    await _handle_activation_response(message, None, state, res, code)

@router.callback_query(F.data.startswith("scheck:copy:"))
async def sc_copy_link(query: CallbackQuery) -> None:
    # Just answer with link to copy? No, copy button copies to clipboard on client usually?
    # Telegram doesn't support 'copy to clipboard' action in callback API directly except for simple text alerts.
    # But we can send message with monospaced link.
    code = query.data.split(":")[-1]
    me = await query.bot.get_me()
    link = f"https://t.me/{me.username}?start=check_{code}"
    
    await query.answer("Ссылка отправлена ниже", show_alert=False)
    await query.message.answer(f"🔗 Ваша ссылка:\n<code>{link}</code>", parse_mode="HTML")

@router.callback_query(F.data == "scheck:close")
async def sc_close(query: CallbackQuery) -> None:
    try:
        await query.message.delete()
    except Exception:
        pass

