"""
Редактор боссов для админов.
"""
from aiogram import F, Router
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from src.core.container import Container
from src.core.constants import BOSSES
from src.bot.presenters.boss_presenter import BossPresenter

router = Router(name="boss_editor")


class BossEditorCallback(CallbackData, prefix="boss_edit"):
    action: str
    value: str | None = None


class BossEditorFSM(StatesGroup):
    choosing_action = State()
    setting_reward_pool = State()
    setting_ton_chance = State()
    choosing_boss = State()
    setting_duration = State()
    choosing_chat = State()


def get_editor_keyboard(settings: dict):
    buttons = [
        [InlineKeyboardButton(text="👹 Выбрать Босса", callback_data=BossEditorCallback(action="choose_boss").pack())],
        [
            InlineKeyboardButton(text="💰 Пул наград", callback_data=BossEditorCallback(action="set_reward").pack()),
            InlineKeyboardButton(text=f"{settings.get('reward_min', 0)}-{settings.get('reward_max', 0)} GRAM", callback_data=BossEditorCallback(action="noop").pack())
        ],
        [
            InlineKeyboardButton(text="🎲 Шанс GRAM", callback_data=BossEditorCallback(action="set_ton_chance").pack()),
            InlineKeyboardButton(text=f"{settings.get('drop_chance', 0) * 100:.1f}%", callback_data=BossEditorCallback(action="noop").pack())
        ],
        [InlineKeyboardButton(text="⏱ Длительность", callback_data=BossEditorCallback(action="menu_duration").pack())],
        [InlineKeyboardButton(text="💬 Выбрать чат", callback_data=BossEditorCallback(action="menu_chat").pack())],
        [InlineKeyboardButton(text="▶️ Старт", callback_data=BossEditorCallback(action="start").pack())]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_duration_keyboard():
    """Get keyboard for duration selection."""
    buttons = [
        [
            InlineKeyboardButton(text="1 час", callback_data=BossEditorCallback(action="set_duration", value="1").pack()),
            InlineKeyboardButton(text="2 часа", callback_data=BossEditorCallback(action="set_duration", value="2").pack()),
            InlineKeyboardButton(text="6 часов", callback_data=BossEditorCallback(action="set_duration", value="6").pack()),
        ],
        [
            InlineKeyboardButton(text="12 часов", callback_data=BossEditorCallback(action="set_duration", value="12").pack()),
            InlineKeyboardButton(text="24 часа", callback_data=BossEditorCallback(action="set_duration", value="24").pack()),
            InlineKeyboardButton(text="3 дня", callback_data=BossEditorCallback(action="set_duration", value="72").pack()),
        ],
        [
            InlineKeyboardButton(text="1 неделя", callback_data=BossEditorCallback(action="set_duration", value="168").pack()),
            InlineKeyboardButton(text="∞ Бесконечно", callback_data=BossEditorCallback(action="set_duration", value="0").pack()),
            InlineKeyboardButton(text="✏️ Ввести вручную", callback_data=BossEditorCallback(action="input_duration").pack()),
        ],
        [InlineKeyboardButton(text="🔙 Назад", callback_data=BossEditorCallback(action="noop").pack())]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_chat_keyboard(container: Container):
    """Get keyboard for chat selection."""
    buttons = []
    allowed_chats = container.settings.allowed_chats
    if allowed_chats:
        for chat_id in allowed_chats:
            buttons.append([InlineKeyboardButton(
                text=f"Чат {chat_id}",
                callback_data=BossEditorCallback(action="set_chat", value=str(chat_id)).pack()
            )])
    else:
        buttons.append([InlineKeyboardButton(
            text="Нет настроенных чатов",
            callback_data=BossEditorCallback(action="noop").pack()
        )])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data=BossEditorCallback(action="noop").pack())])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def show_editor(message: Message, container: Container, state: FSMContext):
    """Show the boss editor interface."""
    data = await state.get_data()
    boss_id = data.get("boss_id")
    duration_hours = data.get("duration_hours")

    settings = await container.boss_service.get_reward_settings()

    text = (
        f"🛠️ <b>РЕДАКТОР БОССА</b>\n\n"
        f"Выберите действие для настройки босса:\n"
    )

    if boss_id:
        boss_name = BOSSES.get(boss_id, {}).get("name", "Неизвестный босс")
        text += f"👹 Текущий босс: <b>{boss_name}</b>\n"
    if duration_hours is not None:
        duration_text = f"{duration_hours} часов" if duration_hours > 0 else "бесконечно"
        text += f"⏱ Продолжительность: {duration_text}\n"
    # Show target chat info
    allowed_chats = container.settings.allowed_chats
    if allowed_chats:
        # Use selected chat if set, otherwise use first allowed chat as default
        target_chat_id = data.get("target_chat_id") or allowed_chats[0]
        text += f"💬 Чат для запуска: {target_chat_id}\n"
    else:
        text += f"⚠️ Чат не настроен! Добавьте ALLOWED_CHATS в .env\n"
    text += "\n"

    await message.answer(
        text,
        reply_markup=get_editor_keyboard(settings),
        parse_mode="HTML"
    )


@router.callback_query(BossEditorCallback.filter(F.action == "set_reward"), BossEditorFSM.choosing_action)
async def on_set_reward(query: CallbackQuery, state: FSMContext):
    await query.message.edit_text("Введите новый диапазон наград в формате: min max (например, 0.1 0.5)")
    await state.set_state(BossEditorFSM.setting_reward_pool)


@router.callback_query(BossEditorCallback.filter(F.action == "choose_boss"), BossEditorFSM.choosing_action)
async def on_choose_boss(query: CallbackQuery, state: FSMContext):
    """Handle choose boss button - show boss selection menu."""
    await state.set_state(BossEditorFSM.choosing_boss)
    from src.domain.boss.resources import get_boss_list_keyboard
    await query.message.edit_text(
        "👹 <b>Выберите Босса:</b>",
        parse_mode="HTML",
        reply_markup=get_boss_list_keyboard()
    )
    await query.answer()


@router.callback_query(BossEditorCallback.filter(F.action == "set_boss"), BossEditorFSM.choosing_boss)
async def on_set_boss(query: CallbackQuery, container: Container, state: FSMContext):
    """Handle boss selection from the list."""
    # Parse the callback data to get the boss_id
    # The callback data should be in format: boss_edit:set_boss:<boss_id>
    try:
        parts = query.data.split(":")
        if len(parts) != 3:
            await query.answer(f"❌ Неверный формат callback данных: {query.data}", show_alert=True)
            return
        _, action, boss_id = parts
        await state.update_data(boss_id=boss_id)

        # Get boss name for confirmation
        from src.core.constants import BOSSES
        boss_name = BOSSES.get(boss_id, {}).get("name", "Неизвестный босс")

        await state.set_state(BossEditorFSM.choosing_action)
        await show_editor(query.message, container, state)
        await query.answer(f"✅ Выбран босс: {boss_name}")
    except Exception as e:
        await query.answer(f"❌ Ошибка при выборе босса: {e}", show_alert=True)


@router.message(BossEditorFSM.setting_reward_pool)
async def on_reward_set(message: Message, container: Container, state: FSMContext):
    try:
        min_val, max_val = map(float, message.text.split())
        if min_val > max_val:
            min_val, max_val = max_val, min_val

        await container.boss_service.update_setting("reward_min", min_val)
        await container.boss_service.update_setting("reward_max", max_val)

        await message.answer(f"✅ Диапазон награды установлен: {min_val} - {max_val} GRAM")

    except (ValueError, TypeError):
        await message.answer("⚠️ Неверный формат. Введите два числа через пробел.")

    await state.set_state(BossEditorFSM.choosing_action)
    await show_editor(message, container, state)


@router.callback_query(BossEditorCallback.filter(F.action == "set_ton_chance"), BossEditorFSM.choosing_action)
async def on_set_ton_chance(query: CallbackQuery, state: FSMContext):
    await query.message.edit_text("Введите новый шанс выпадения TON (от 0.0 до 1.0)")
    await state.set_state(BossEditorFSM.setting_ton_chance)


@router.message(BossEditorFSM.setting_ton_chance)
async def on_ton_chance_set(message: Message, container: Container, state: FSMContext):
    try:
        val = float(message.text)
        if not 0 <= val <= 1:
            raise ValueError("Значение должно быть между 0.0 и 1.0")

        await container.boss_service.update_setting("drop_chance", val)
        await message.answer(f"✅ Шанс выпадения GRAM установлен: {val * 100:.1f}%")

    except (ValueError, TypeError):
        await message.answer("⚠️ Неверный формат. Введите число от 0.0 до 1.0")

    await state.set_state(BossEditorFSM.choosing_action)
    await show_editor(message, container, state)


@router.callback_query(BossEditorCallback.filter(F.action == "start"), BossEditorFSM.choosing_action)
async def on_start_boss(query: CallbackQuery, container: Container, state: FSMContext):
    """Handle start button - show duration selection or launch if already set."""
    data = await state.get_data()
    boss_id = data.get("boss_id")
    duration = data.get("duration_hours")

    if not boss_id:
        await query.answer("⚠️ Сначала выберите босса!", show_alert=True)
        return

    # If duration not set, show duration selection
    if duration is None:
        await state.set_state(BossEditorFSM.setting_duration)
        await query.message.edit_text(
            "⏱ <b>Выберите продолжительность босса:</b>\n\n"
            "Выберите время жизни босса перед запуском:",
            parse_mode="HTML",
            reply_markup=get_duration_keyboard()
        )
        await query.answer()
        return

    # Duration is set, proceed with launch
    data = await state.get_data()
    target_chat_id = data.get("target_chat_id")

    # Use selected chat or fallback to first allowed chat
    allowed_chats = container.settings.allowed_chats
    if not target_chat_id and allowed_chats:
        target_chat_id = allowed_chats[0]
    elif not target_chat_id:
        await query.answer(
            "❌ Не настроены разрешенные чаты. Добавьте ALLOWED_CHATS в .env файл",
            show_alert=True
        )
        return

    try:
        reward_settings = await container.boss_service.get_reward_settings()
        from src.bot.handlers.boss_commands import launch_boss
        # Запуск босса с выбранными параметрами
        # Проверяем, что все параметры переданы correctly
        launch_params = {
            'bot': query.bot,
            'chat_id': target_chat_id,
            'boss_id': boss_id,
            'container': container,
            'duration': duration,
            'reward_settings': reward_settings
        }
        await launch_boss(**launch_params)
        await query.message.edit_text(
            f"✅ Босс <b>{BOSSES[boss_id]['name']}</b> успешно призван в чат {target_chat_id}!\n"
            f"⏱ Продолжительность: {duration} часов"
        )
        await state.clear()
    except Exception as e:
        await query.answer(f"❌ Ошибка при запуске босса: {e}", show_alert=True)


@router.message(BossEditorFSM.choosing_action)
async def handle_initial_editor_message(message: Message, container: Container, state: FSMContext):
    await show_editor(message, container, state)


# Duration selection handlers
@router.callback_query(BossEditorCallback.filter(F.action == "menu_duration"), BossEditorFSM.choosing_action)
async def on_menu_duration(query: CallbackQuery, state: FSMContext):
    """Handle duration menu button - show duration selection."""
    await state.set_state(BossEditorFSM.setting_duration)
    await query.message.edit_text(
        "⏱ <b>Выберите продолжительность босса:</b>\n\n"
        "Выберите время жизни босса перед запуском:",
        parse_mode="HTML",
        reply_markup=get_duration_keyboard()
    )
    await query.answer()


@router.callback_query(BossEditorCallback.filter(F.action == "set_duration"), BossEditorFSM.setting_duration)
async def on_set_duration(query: CallbackQuery, container: Container, state: FSMContext):
    """Handle duration selection from predefined options."""
    try:
        parts = query.data.split(":")
        if len(parts) != 3:
            await query.answer(f"❌ Неверный формат callback данных: {query.data}", show_alert=True)
            return
        _, action, value = parts
        duration = int(value)
        await state.update_data(duration_hours=duration if duration > 0 else None)

        # Go back to main editor
        await state.set_state(BossEditorFSM.choosing_action)
        await show_editor(query.message, container, state)
        duration_text = f"{duration} часов" if duration > 0 else "бесконечно"
        await query.answer(f"✅ Продолжительность установлена: {duration_text}")
    except ValueError as e:
        await query.answer(f"❌ Ошибка в значении продолжительности: {e}", show_alert=True)
    except Exception as e:
        await query.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.message(BossEditorFSM.setting_duration)
async def on_duration_input(message: Message, container: Container, state: FSMContext):
    """Handle manual duration input."""
    try:
        duration = int(message.text.strip())
        if duration < 0:
            await message.answer("⚠️ Продолжительность не может быть отрицательной")
            return

        await state.update_data(duration_hours=duration if duration > 0 else None)
        await state.set_state(BossEditorFSM.choosing_action)
        await show_editor(message, container, state)

        duration_text = f"{duration} часов" if duration > 0 else "бесконечно"
        await message.answer(f"✅ Продолжительность установлена: {duration_text}")
    except ValueError:
        await message.answer("⚠️ Введите корректное число часов")


# Helper for input duration state
@router.callback_query(BossEditorCallback.filter(F.action == "input_duration"), BossEditorFSM.choosing_action)
async def on_input_duration(query: CallbackQuery, state: FSMContext):
    """Handle manual duration input request."""
    await state.set_state(BossEditorFSM.setting_duration)
    await query.message.edit_text(
        "✏️ <b>Введите продолжительность в часах:</b>\n\n"
        "• 0 - бесконечно\n"
        "• 1-168 - конкретное количество часов\n"
        "• Например: 2 для 2 часов, 24 для 1 дня",
        parse_mode="HTML"
    )
    await query.answer()


# Chat selection handlers
@router.callback_query(BossEditorCallback.filter(F.action == "menu_chat"), BossEditorFSM.choosing_action)
async def on_menu_chat(query: CallbackQuery, container: Container, state: FSMContext):
    """Handle chat menu button - show chat selection."""
    await state.set_state(BossEditorFSM.choosing_chat)
    await query.message.edit_text(
        "💬 <b>Выберите чат для запуска босса:</b>\n\n"
        "Выберите чат, в котором будет запущен босс:",
        parse_mode="HTML",
        reply_markup=get_chat_keyboard(container)
    )
    await query.answer()


@router.callback_query(BossEditorCallback.filter(F.action == "set_chat"), BossEditorFSM.choosing_chat)
async def on_set_chat(query: CallbackQuery, container: Container, state: FSMContext):
    """Handle chat selection."""
    try:
        parts = query.data.split(":")
        if len(parts) != 3:
            await query.answer(f"❌ Неверный формат callback данных: {query.data}", show_alert=True)
            return
        _, action, value = parts
        chat_id = int(value)
        await state.update_data(target_chat_id=chat_id)

        # Go back to main editor
        await state.set_state(BossEditorFSM.choosing_action)
        await show_editor(query.message, container, state)
        await query.answer(f"✅ Чат установлен: {chat_id}")
    except ValueError as e:
        await query.answer(f"❌ Ошибка в значении чата: {e}", show_alert=True)
    except Exception as e:
        await query.answer(f"❌ Ошибка: {e}", show_alert=True)


# Back button handlers
@router.callback_query(BossEditorCallback.filter(F.action == "noop"), BossEditorFSM.setting_duration)
async def on_duration_back(query: CallbackQuery, container: Container, state: FSMContext):
    """Handle back button from duration selection."""
    await state.set_state(BossEditorFSM.choosing_action)
    await show_editor(query.message, container, state)
    await query.answer()


@router.callback_query(BossEditorCallback.filter(F.action == "noop"), BossEditorFSM.choosing_chat)
async def on_chat_back(query: CallbackQuery, container: Container, state: FSMContext):
    """Handle back button from chat selection."""
    await state.set_state(BossEditorFSM.choosing_action)
    await show_editor(query.message, container, state)
    await query.answer()


@router.callback_query(F.data == "boss_edit:back", BossEditorFSM.choosing_boss)
async def on_boss_list_back(query: CallbackQuery, container: Container, state: FSMContext):
    """Handle back button from boss list selection."""
    await state.set_state(BossEditorFSM.choosing_action)
    await show_editor(query.message, container, state)
    await query.answer()