import logging
import asyncio
import html

from aiogram import Router, F, Bot
from aiogram.filters import Command, CommandObject, StateFilter
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest

from src.core.config import settings
from src.core.container import Container
from src.core.visuals import Visuals
from src.bot.parsers.banzai_parser import BanzaiCommandParser
from src.domain.banzai.models import BanzaiCommand, BanzaiActionType

logger = logging.getLogger(__name__)

router = Router(name="banzai")

class BanzaiStates(StatesGroup):
    settings = State()
    set_minutes = State()
    set_reward = State()
    set_chat = State()

async def _delete_trigger_safe(message: Message) -> None:
    try:
        if message.chat and message.chat.type != "private":
            await message.delete()
    except Exception:
        pass
# Configuration constants
DEFAULT_MINUTES = 10
DEFAULT_REWARD = 0.0
MIN_DURATION = 1
MAX_DURATION = 1440  # 24 hours
DISPLAY_WIDTH = 30


def _validate_duration(minutes: int) -> int:
    """Ensure duration is within valid range."""
    if not isinstance(minutes, int):
        minutes = int(minutes)
    return max(MIN_DURATION, min(minutes, MAX_DURATION))


def _create_frame(title: str, lines: list[str], centered: bool = False) -> str:
    """Create a formatted frame for display."""
    result = [Visuals.frame_top_left(DISPLAY_WIDTH)]
    result.append(Visuals.frame_line_left(title, DISPLAY_WIDTH, "center" if centered else None))
    if lines:
        result.append(Visuals.frame_separator_left(DISPLAY_WIDTH))
        result.extend(Visuals.frame_line_left(line, DISPLAY_WIDTH) for line in lines)
    result.append(Visuals.frame_bottom_left(DISPLAY_WIDTH))
    return "<pre>\n" + "\n".join(result) + "\n</pre>"


async def get_banzai_keyboard(data: dict) -> InlineKeyboardMarkup:
    """Generate settings keyboard with current values."""
    minutes = data.get("minutes", DEFAULT_MINUTES)
    reward = data.get("reward", DEFAULT_REWARD)
    target_title = data.get("target_chat_title")
    target_id = data.get("target_chat_id")

    # Determine chat label
    if target_title and target_id:
        chat_label = target_title
    elif target_id:
        chat_label = f"ID {target_id}"
    else:
        chat_label = "не выбрано"

    kb = [
        [InlineKeyboardButton(text=f"📍 Чат: {chat_label}", callback_data="banzai_set_chat")],
        [InlineKeyboardButton(text=f"⏱ Длительность: {minutes} мин", callback_data="banzai_set_time")],
        [InlineKeyboardButton(text=f"💎 Награда: {reward} TON", callback_data="banzai_set_reward")],
        [InlineKeyboardButton(text="🚀 СТАРТ", callback_data="banzai_start")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


async def _check_admin(user_id: int, chat_id: int, bot: Bot) -> bool:
    """Check if user is admin in chat or global admin."""
    if user_id in settings.admin_ids:
        return True
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except Exception as e:
        logger.debug(f"Failed to check admin status for user {user_id}: {e}")
        return False


async def is_admin(message: Message, bot: Bot) -> bool:
    """Check if message sender is admin."""
    return await _check_admin(message.from_user.id, message.chat.id, bot)


async def is_admin_user(chat_id: int, user_id: int, bot: Bot) -> bool:
    """Check if user is admin in specific chat."""
    return await _check_admin(user_id, chat_id, bot)


# ============================================================================
# COMMAND HANDLERS
# ============================================================================

@router.message(Command("banzai", "банзай", "banzazi", "банзази"))
async def cmd_banzai(message: Message, command: CommandObject, container: Container, state: FSMContext):
    """Handle /banzai command - group and PM logic."""
    # 1. PM Logic - only show help, no settings
    if message.chat.type == "private":
        lines = [
            "🥷 БАНЗАЙ — ИГРА ТИШИНЫ",
            Visuals.frame_separator_left(DISPLAY_WIDTH),
            "📜 Использование в чате:",
            "/банзай [мин] — запустить игру",
            "",
            "Примеры:",
            "/банзай 5  — игра на 5 минут",
            "/банзай 10 — игра на 10 минут",
            "",
            "⚙️ Команды:",
            "/банзай stop   — остановить",
            "/банзай status — статус",
            "/банзай rules  — правила",
            "",
            "💡 Кнопки в чате:",
            "➕/➖ — изменить время",
            "🔄/🧭 — обновить/статус",
            "📜 — правила, 🛑 — стоп",
            "",
            "🤫 Как выиграть:",
            "Последний, чьё сообщение выдержало тишину — победил",
        ]
        text = "<pre>\n" + "\n".join([Visuals.frame_top_left(DISPLAY_WIDTH)] + [Visuals.frame_line_left(s, DISPLAY_WIDTH) for s in lines] + [Visuals.frame_bottom_left(DISPLAY_WIDTH)]) + "\n</pre>"
        await message.answer(text, parse_mode="HTML")
        return

    # 2. Group Logic - check admin rights
    if not await is_admin(message, message.bot):
        await message.answer(f"{Visuals.cross()} Только сенсей может управлять банзаем.")
        await _delete_trigger_safe(message)
        return

    service = container.banzai_service
    cmd_obj = BanzaiCommandParser.parse(command.args)
    chat_id = message.chat.id

    # Handle different actions
    if cmd_obj.action == BanzaiActionType.STOP:
        await _handle_stop_command(message, service, chat_id)
        return

    if cmd_obj.action == BanzaiActionType.STATUS:
        await _handle_status_command(message, service, chat_id)
        return

    if cmd_obj.action == BanzaiActionType.RULES:
        await _handle_rules_command(message)
        return

    # Check if game is active
    if await service.is_active(chat_id):
        await _handle_active_game_command(message, service, cmd_obj, chat_id)
    else:
        await _handle_start_game_command(message, service, cmd_obj, chat_id)


async def _handle_stop_command(message: Message, service, chat_id: int) -> None:
    """Handle stop action."""
    stopped = await service.stop_game(chat_id, bot=message.bot)
    msg = "🛑 Банзай остановлен." if stopped else "⚠️ Банзай не запущен."
    await message.answer(msg)
    await _delete_trigger_safe(message)


async def _handle_status_command(message: Message, service, chat_id: int) -> None:
    """Handle status action."""
    status = await service.get_status(chat_id)
    if not status.get("active"):
        await message.answer("💤 Банзай спит.")
        await _delete_trigger_safe(message)
        return

    import time
    now = int(time.time())
    duration_minutes = int(status.get("duration_minutes") or DEFAULT_MINUTES)
    duration_seconds = duration_minutes * 60
    started_at = int(status.get("started_at") or now)
    last_activity = status.get("last_activity")
    last_activity = int(last_activity) if isinstance(last_activity, (int, float)) else None

    last_time = max(float(last_activity or started_at), float(started_at))
    silence_duration = max(0, int(time.time() - last_time))
    remain_sec = max(0, duration_seconds - silence_duration)
    remain_min, remain_s = remain_sec // 60, remain_sec % 60

    lines = [
        f"⏱ До победы: {remain_min:02d}:{remain_s:02d}",
        f"💎 TON: {status.get('reward_ton', 0)}",
        "🔄 Окно игры обновляется"
    ]
    text = _create_frame("⏳ БАНЗАЙ АКТИВЕН", lines)
    await message.answer(text, parse_mode="HTML")
    await service.refresh_window(chat_id, message.bot, force=True)
    await _delete_trigger_safe(message)


async def _handle_rules_command(message: Message) -> None:
    """Show game rules."""
    lines = [
        "1. Жди тишины в чате.",
        "2. Кто последний написал — WIN.",
        "3. Лутай призы!"
    ]
    text = _create_frame("📜 ПРАВИЛА БАНЗАЙ", lines)
    await message.answer(text, parse_mode="HTML")
    await _delete_trigger_safe(message)


async def _handle_active_game_command(message: Message, service, cmd_obj, chat_id: int) -> None:
    """Handle commands while game is active."""
    status = await service.get_status(chat_id)
    current_minutes = int(status.get("duration_minutes") or DEFAULT_MINUTES)

    if cmd_obj.action == BanzaiActionType.SET_REWARD and cmd_obj.reward is not None:
        if await service.update_reward(chat_id, cmd_obj.reward):
            await message.answer(f"💎 Награда обновлена: {cmd_obj.reward} TON")
            await service.refresh_window(chat_id, message.bot, force=True)
        else:
            await message.answer("⚠️ Не удалось обновить награду.")
        await _delete_trigger_safe(message)
        return

    if cmd_obj.action == BanzaiActionType.ADD_TIME and cmd_obj.minutes is not None:
        new_minutes = _validate_duration(current_minutes + cmd_obj.minutes)
        if await service.update_duration(chat_id, new_minutes):
            await message.answer(f"✅ Время игры изменено: {current_minutes} → {new_minutes} мин.")
            await service.refresh_window(chat_id, message.bot, force=True)
        await _delete_trigger_safe(message)
        return

    if cmd_obj.action == BanzaiActionType.SET_TIME and cmd_obj.minutes is not None:
        new_minutes = _validate_duration(cmd_obj.minutes)
        if await service.update_duration(chat_id, new_minutes):
            await message.answer(f"✅ Время игры изменено: {current_minutes} → {new_minutes} мин.")
            await service.refresh_window(chat_id, message.bot, force=True)
        await _delete_trigger_safe(message)
        return

    await message.answer("⚠️ Игра уже идет! Используйте: /banzai stop, /banzai +5, /banzai reward 10")
    await _delete_trigger_safe(message)


async def _handle_start_game_command(message: Message, service, cmd_obj, chat_id: int) -> None:
    """Handle game start."""
    if cmd_obj.action != BanzaiActionType.SET_TIME or cmd_obj.minutes is None:
        await message.answer(f"{Visuals.cross()} Для старта введите число минут (например /banzai 10).")
        await _delete_trigger_safe(message)
        return

    minutes = _validate_duration(cmd_obj.minutes)
    reward = cmd_obj.reward or 0.0

    if not (1 <= minutes <= 60):
        await message.answer(f"{Visuals.cross()} Время должно быть от 1 до 60 минут.")
        await _delete_trigger_safe(message)
        return

    if await service.start_game(chat_id, message.bot, duration_minutes=minutes, reward_ton=reward):
        lines = [f"🤫 Цель: {minutes} мин тишины", "⏳ Подготовка..."]
        text = _create_frame("⚔️ БАНЗАЙ: ЗАПУСК...", lines, centered=True)
        msg = await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=service.get_game_keyboard(chat_id, active=True),
        )
        await service.set_game_message_id(chat_id, msg.message_id)
        # Pin the game message
        await service.pin_game_message(chat_id, msg.message_id, message.bot)
        await service.refresh_window(chat_id, message.bot, force=True)
    else:
        await message.answer("⚠️ Игра уже идет!")
    await _delete_trigger_safe(message)


# ============================================================================
# PM SETTINGS CALLBACKS
# ============================================================================

@router.callback_query(F.data == "banzai_set_time", StateFilter(BanzaiStates.settings))
async def cb_set_time(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("⏱ Введите длительность игры в минутах (1-60):")
    await state.set_state(BanzaiStates.set_minutes)
    await callback.answer()


@router.message(StateFilter(BanzaiStates.set_minutes))
async def process_set_time(message: Message, state: FSMContext):
    if not message.text or not message.text.isdigit():
        await message.answer(f"{Visuals.cross()} Введите число.")
        return

    val = _validate_duration(int(message.text))
    if not (1 <= val <= 60):
        await message.answer(f"{Visuals.cross()} От 1 до 60 минут.")
        return

    await state.update_data(minutes=val)
    await state.set_state(BanzaiStates.settings)
    data = await state.get_data()
    kb = await get_banzai_keyboard(data)
    await message.answer("✅ Время установлено.", reply_markup=kb)


@router.callback_query(F.data == "banzai_set_reward", StateFilter(BanzaiStates.settings))
async def cb_set_reward(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("💎 Введите сумму награды в TON (например 0.1):")
    await state.set_state(BanzaiStates.set_reward)
    await callback.answer()


@router.message(StateFilter(BanzaiStates.set_reward))
async def process_set_reward(message: Message, state: FSMContext):
    if not message.text:
        await message.answer(f"{Visuals.cross()} Введите корректное число.")
        return

    try:
        val = float(message.text.replace(",", "."))
        if val < 0:
            raise ValueError("Отрицательное значение")
    except (ValueError, AttributeError):
        await message.answer(f"{Visuals.cross()} Введите корректное число.")
        return

    await state.update_data(reward=val)
    await state.set_state(BanzaiStates.settings)
    data = await state.get_data()
    kb = await get_banzai_keyboard(data)
    await message.answer("✅ Награда установлена.", reply_markup=kb)


@router.callback_query(F.data == "banzai_set_chat", StateFilter(BanzaiStates.settings))
async def cb_set_chat(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "📍 Выбор чата для запуска:\n"
        "• Перешлите сюда любое сообщение из нужного чата\n"
        "  или\n"
        "• Введите ID чата (например -1001234567890)",
    )
    await state.set_state(BanzaiStates.set_chat)
    await callback.answer()


@router.message(StateFilter(BanzaiStates.set_chat))
async def process_set_chat(message: Message, state: FSMContext):
    target_chat_id = None
    target_chat_title = None

    # Try forwarded message
    try:
        origin = getattr(message, "forward_origin", None)
        if origin:
            if getattr(origin, "type", None) == "channel" and hasattr(origin, "chat"):
                target_chat_id = origin.chat.id
                target_chat_title = origin.chat.title
            elif getattr(origin, "type", None) == "chat" and hasattr(origin, "sender_chat"):
                target_chat_id = origin.sender_chat.id
                target_chat_title = origin.sender_chat.title
    except Exception as e:
        logger.debug(f"Failed to extract forwarded chat: {e}")

    # Try manual input
    if target_chat_id is None and message.text:
        try:
            target_chat_id = int(message.text.strip())
            chat = await message.bot.get_chat(target_chat_id)
            target_chat_title = chat.title or chat.full_name or str(target_chat_id)
        except (ValueError, Exception) as e:
            logger.debug(f"Failed to parse chat ID: {e}")
            target_chat_id = None

    if target_chat_id is None:
        await message.answer(f"{Visuals.cross()} Не удалось определить чат. Перешлите сообщение из чата или введите его ID.")
        return

    await state.update_data(target_chat_id=target_chat_id, target_chat_title=target_chat_title)
    await state.set_state(BanzaiStates.settings)
    data = await state.get_data()
    kb = await get_banzai_keyboard(data)

    display_title = html.escape(str(target_chat_title or target_chat_id))
    await message.answer(
        f"✅ Чат установлен: <b>{display_title}</b> (<code>{target_chat_id}</code>)",
        parse_mode="HTML",
        reply_markup=kb
    )


@router.callback_query(F.data == "banzai_start", StateFilter(BanzaiStates.settings))
async def cb_start(callback: CallbackQuery, state: FSMContext, container: Container):
    data = await state.get_data()
    minutes = data.get("minutes", DEFAULT_MINUTES)
    reward = data.get("reward", DEFAULT_REWARD)
    chat_id = data.get("target_chat_id") or settings.main_chat_id

    if not chat_id:
        await callback.answer(f"{Visuals.cross()} Чат не выбран и MAIN_CHAT_ID не настроен!", show_alert=True)
        return

    service = container.banzai_service

    try:
        success = await service.start_game(
            chat_id=chat_id,
            bot=callback.bot,
            duration_minutes=minutes,
            reward_ton=reward
        )

        if success:
            await callback.answer("🚀 Запущено!", show_alert=True)
            await callback.message.edit_text(
                f"🚀 <b>БАНЗАЙ ЗАПУЩЕН!</b>\n"
                f"📍 Чат: {chat_id}\n"
                f"⏱ Время: {minutes} мин\n"
                f"💎 Награда: {reward} TON",
                parse_mode="HTML"
            )

            lines = [f"🤫 Цель: {minutes} мин тишины", "⏳ Подготовка..."]
            msg_text = _create_frame("⚔️ БАНЗАЙ: ЗАПУСК...", lines, centered=True)
            msg = await callback.bot.send_message(
                chat_id,
                msg_text,
                parse_mode="HTML",
                reply_markup=service.get_game_keyboard(chat_id, active=True),
            )
            await service.set_game_message_id(chat_id, msg.message_id)
            await service.refresh_window(chat_id, callback.bot, force=True)
        else:
            await callback.answer("⚠️ Игра уже идет в этом чате!", show_alert=True)

    except Exception as e:
        logger.error(f"Failed to start Banzai from PM: {e}", exc_info=True)
        await callback.answer(f"{Visuals.cross()} Ошибка: {e}", show_alert=True)


# ============================================================================
# GAME CALLBACKS
# ============================================================================

async def _safe_callback_answer(callback: CallbackQuery, text: str = None, show_alert: bool = False) -> None:
    """Safely send callback answer, ignoring old query errors."""
    try:
        await callback.answer(text, show_alert=show_alert)
    except TelegramBadRequest:
        pass  # Ignore "query is too old"
    except Exception as e:
        logger.debug(f"Callback answer failed: {e}")


async def _handle_time_op(callback: CallbackQuery, parts: list[str], container: Container) -> bool:
    """Handle time adjustment operations (add/sub). Returns True if handled."""
    if parts[1] != "time" or len(parts) < 5:
        return False

    try:
        op = parts[2]
        val = int(parts[3])
        chat_id = int(parts[4])
    except (ValueError, IndexError):
        return False

    if not callback.message or callback.message.chat.id != chat_id:
        await _safe_callback_answer(callback, "Не тот чат", show_alert=True)
        return True

    if not await is_admin_user(chat_id, callback.from_user.id, callback.bot):
        await _safe_callback_answer(callback, "Только сенсей может менять время", show_alert=True)
        return True

    service = container.banzai_service
    status = await service.get_status(chat_id)
    if not status.get("active"):
        await _safe_callback_answer(callback, "Игра не активна", show_alert=True)
        return True

    current_minutes = int(status.get("duration_minutes") or DEFAULT_MINUTES)
    delta = val if op == "add" else -val if op == "sub" else 0
    new_minutes = _validate_duration(current_minutes + delta)

    if await service.update_duration(chat_id, new_minutes):
        await service.refresh_window(chat_id, callback.bot, force=True)
        await _safe_callback_answer(callback, f"Время: {new_minutes} мин")
    else:
        await _safe_callback_answer(callback, "Ошибка обновления", show_alert=True)
    return True


async def _handle_reward_op(callback: CallbackQuery, parts: list[str], container: Container) -> bool:
    """Handle reward TON adjustment operations (add/sub). Returns True if handled."""
    if parts[1] != "reward" or len(parts) < 5:
        return False
    try:
        op = parts[2]
        step = float(parts[3])
        chat_id = int(parts[4])
    except (ValueError, IndexError):
        return False
    if not callback.message or callback.message.chat.id != chat_id:
        await _safe_callback_answer(callback, "Не тот чат", show_alert=True)
        return True
    if not await is_admin_user(chat_id, callback.from_user.id, callback.bot):
        await _safe_callback_answer(callback, "Только сенсей может менять награду", show_alert=True)
        return True
    service = container.banzai_service
    status = await service.get_status(chat_id)
    if not status.get("active"):
        await _safe_callback_answer(callback, "Игра не активна", show_alert=True)
        return True
    current = float(status.get("reward_ton") or 0.0)
    delta = step if op == "add" else -step if op == "sub" else 0.0
    new_reward = max(0.0, round(current + delta, 2))
    if await service.update_reward(chat_id, new_reward):
        await service.refresh_window(chat_id, callback.bot, force=True)
        await _safe_callback_answer(callback, f"💎 Награда: {new_reward} TON")
    else:
        await _safe_callback_answer(callback, "Ошибка обновления награды", show_alert=True)
    return True


async def _action_refresh(callback: CallbackQuery, service, chat_id: int) -> None:
    """Handle refresh action."""
    if await service.refresh_window(chat_id, callback.bot, force=True):
        await _safe_callback_answer(callback, "Обновлено")
    else:
        await _safe_callback_answer(callback, "Банзай не активен", show_alert=True)


async def _action_status(callback: CallbackQuery, service, chat_id: int) -> None:
    """Handle status action."""
    if await service.refresh_window(chat_id, callback.bot, force=True):
        await _safe_callback_answer(callback, "Живой статус в окне", show_alert=True)
    else:
        await _safe_callback_answer(callback, "Банзай не активен", show_alert=True)


async def _action_rules(callback: CallbackQuery) -> None:
    """Show game rules."""
    rules_text = (
        "📜 <b>ПРАВИЛА БАНЗАЙ</b>\n\n"
        "🤫 <b>Цель:</b> Хранить тишину в чате ровно N минут.\n\n"
        "✍️ <b>Как это работает:</b>\n"
        "• Тишина начинает отсчёт с нуля\n"
        "• Каждое сообщение = сброс таймера\n"
        "• Чьё сообщение будет ПОСЛЕДНИМ = ТОТ ПОБЕДИЛ\n\n"
        "🏆 <b>Победитель:</b> Игрок, чьё сообщение выдержало тишину до конца отсчёта\n\n"
        "💰 <b>Награда:</b> 500 Coins + 1 Билет + Бонусная награда"
    )
    await _safe_callback_answer(callback, rules_text, show_alert=True)


async def _action_stop(callback: CallbackQuery, service, chat_id: int) -> None:
    """Handle stop action."""
    if not await is_admin_user(chat_id, callback.from_user.id, callback.bot):
        await _safe_callback_answer(callback, "Только сенсей может остановить", show_alert=True)
        return

    if await service.stop_game(chat_id, bot=callback.bot):
        await _safe_callback_answer(callback, "Остановлено", show_alert=True)
    else:
        await _safe_callback_answer(callback, "Не запущено", show_alert=True)


@router.callback_query(F.data.startswith("banzai:"))
async def cb_banzai_game(callback: CallbackQuery, container: Container):
    """Main handler for all banzai game callbacks."""
    parts = (callback.data or "").split(":")

    if len(parts) < 3:
        await _safe_callback_answer(callback)
        return

    # Handle time operations (banzai:time:add:5:12345)
    if await _handle_time_op(callback, parts, container):
        return
    # Handle reward operations (banzai:reward:add:0.1:12345)
    if await _handle_reward_op(callback, parts, container):
        return

    # Handle standard operations (banzai:action:chat_id)
    try:
        action = parts[1]
        chat_id = int(parts[2])
    except (ValueError, IndexError):
        await _safe_callback_answer(callback)
        return

    if not callback.message or callback.message.chat.id != chat_id:
        await _safe_callback_answer(callback, "Не тот чат", show_alert=True)
        return

    service = container.banzai_service
    await service.set_game_message_id(chat_id, callback.message.message_id)

    # Dispatch by action type
    action_handlers = {
        "refresh": lambda: _action_refresh(callback, service, chat_id),
        "status": lambda: _action_status(callback, service, chat_id),
        "rules": lambda: _action_rules(callback),
        "stop": lambda: _action_stop(callback, service, chat_id),
    }

    handler = action_handlers.get(action)
    if handler:
        await handler()
    else:
        await _safe_callback_answer(callback)