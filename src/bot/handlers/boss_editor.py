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


def get_editor_keyboard(settings: dict):
    buttons = [
        [InlineKeyboardButton(text="👹 Выбрать Босса", callback_data=BossEditorCallback(action="choose_boss").pack())],
        [
            InlineKeyboardButton(text="💰 Пул наград", callback_data=BossEditorCallback(action="set_reward").pack()),
            InlineKeyboardButton(text=f"{settings.get('reward_min', 0)}-{settings.get('reward_max', 0)} TON", callback_data=BossEditorCallback(action="noop").pack())
        ],
        [
            InlineKeyboardButton(text="🎲 Шанс TON", callback_data=BossEditorCallback(action="set_ton_chance").pack()),
            InlineKeyboardButton(text=f"{settings.get('drop_chance', 0) * 100:.1f}%", callback_data=BossEditorCallback(action="noop").pack())
        ],
        [InlineKeyboardButton(text="▶️ Старт", callback_data=BossEditorCallback(action="start").pack())]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def show_editor(message: Message, container: Container, state: FSMContext):
    """Show the boss editor interface."""
    data = await state.get_data()
    boss_id = data.get("boss_id")

    settings = await container.boss_service.get_reward_settings()

    text = (
        f"🛠️ <b>РЕДАКТОР БОССА</b>\n\n"
        f"Выберите действие для настройки босса:\n"
    )

    if boss_id:
        boss_name = BOSSES.get(boss_id, {}).get("name", "Неизвестный босс")
        text += f"👹 Текущий босс: <b>{boss_name}</b>\n\n"

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
async def on_set_boss(query: CallbackQuery, state: FSMContext):
    """Handle boss selection from the list."""
    # Parse the callback data to get the boss_id
    # The callback data should be in format: boss_edit:set_boss:<boss_id>
    try:
        _, action, boss_id = query.data.split(":")
        await state.update_data(boss_id=boss_id)

        # Get boss name for confirmation
        from src.core.constants import BOSSES
        boss_name = BOSSES.get(boss_id, {}).get("name", "Неизвестный босс")

        await state.set_state(BossEditorFSM.choosing_action)
        await show_editor(query.message, query.message._bot, state)  # type: ignore
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

        await message.answer(f"✅ Диапазон награды установлен: {min_val} - {max_val} TON")

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
        await message.answer(f"✅ Шанс выпадения TON установлен: {val * 100:.1f}%")

    except (ValueError, TypeError):
        await message.answer("⚠️ Неверный формат. Введите число от 0.0 до 1.0")

    await state.set_state(BossEditorFSM.choosing_action)
    await show_editor(message, container, state)


@router.callback_query(BossEditorCallback.filter(F.action == "start"), BossEditorFSM.choosing_action)
async def on_start_boss(query: CallbackQuery, container: Container, state: FSMContext):
    data = await state.get_data()
    boss_id = data.get("boss_id")

    if not boss_id:
        await query.answer("⚠️ Сначала выберите босса!", show_alert=True)
        return

    target_chat_id = container.settings.allowed_chats[0] if container.settings.allowed_chats else -1002098194464

    try:
        reward_settings = await container.boss_service.get_reward_settings()
        from src.bot.handlers.boss_commands import launch_boss
        await launch_boss(query.bot, target_chat_id, boss_id, container, reward_settings=reward_settings)
        await query.message.edit_text(f"✅ Босс <b>{BOSSES[boss_id]['name']}</b> успешно призван в чат {target_chat_id}!")
        await state.clear()
    except Exception as e:
        await query.answer(f"❌ Ошибка при запуске босса: {e}", show_alert=True)


@router.message(BossEditorFSM.choosing_action)
async def handle_initial_editor_message(message: Message, container: Container, state: FSMContext):
    await show_editor(message, container, state)