"""
⚔️ Обработчик битвы с боссом.
"""

import asyncio
import logging
import random
import time

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from src.bot.filters import AdminFilter
from src.core.constants import BOSS_COOLDOWN_MINUTES, BOSSES
from src.core.container import Container
from src.core.visuals import Visuals

import logging
logger = logging.getLogger(__name__)


async def safe_answer(callback: CallbackQuery, text: str = None, show_alert: bool = False):
    try:
        await callback.answer(text, show_alert=show_alert)
    except TelegramBadRequest as e:
        if "query is too old" in str(e):
            return
        raise e
    except (TelegramNetworkError, Exception) as e:
        if "ServerDisconnectedError" in str(e) or "Connection" in str(e):
            return
        raise e

async def delete_message_delayed(message: Message, delay: int):
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception:
        pass

router = Router(name="boss_commands")


def get_boss_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚔️ Атаковать!", callback_data="hit_boss")]
    ])

def render_boss_caption(state: dict, last_action: str = None) -> str:
    """Генерация красивого HTML сообщения босса."""
    boss_config = BOSSES[state["boss_id"]]
    hp = max(0, state["hp"])
    max_hp = state["max_hp"]

    w = 30

    def fit(text: str) -> str:
        text = str(text)
        max_len = max(0, w - 2)
        if len(text) <= max_len:
            return text
        return text[: max(0, max_len - 1)] + "…"

    lines = [
        Visuals.frame_top_left(w),
        Visuals.frame_line_left(fit(f"👹 {boss_config['name']}"), w),
        Visuals.frame_separator_left(w),
    ]

    intro = state.get("intro")
    if intro:
        lines.append(Visuals.frame_line_left(fit(f"🗣 {intro}"), w))

    # HP Logic
    percent = int((hp / max_hp) * 100) if max_hp > 0 else 0

    hp_emoji = "💚"
    if percent <= 20:
        hp_emoji = "❤️"
    elif percent <= 50:
        hp_emoji = "💛"

    bar = Visuals.progress_bar(hp, max_hp, length=10, style="block")

    lines.append(Visuals.frame_line_left(fit(f"{hp_emoji} {bar} {percent}%"), w))
    lines.append(Visuals.frame_line_left(fit(f"   {hp}/{max_hp} HP"), w))

    # Status
    status = "Норма"
    weakness_until = state.get("weakness_until", 0)
    is_weak = time.time() < weakness_until

    if is_weak:
        status = "😵 УЯЗВИМ! (x2 УРОН)"
    elif percent <= 30:
        status = "🤬 ЯРОСТЬ!"
    elif percent <= 50:
        status = "😠 Ранен"

    phase = "I"
    if percent <= 10:
        phase = "IV"
    elif percent <= 25:
        phase = "III"
    elif percent <= 50:
        phase = "II"
    lines.append(Visuals.frame_line_left(fit(f"📊 Фаза {phase}: {status}"), w))

    # Combo Streak
    combo_count = state.get("combo_count", 0)
    if combo_count > 1:
        lines.append(Visuals.frame_line_left(fit(f"🔥 COMBO: x{combo_count}!"), w))

    lines.append(Visuals.frame_separator_left(w))

    # Stats
    reward = Visuals._fmt_coins(boss_config.get('coins_reward', 0))
    lines.append(Visuals.frame_line_left(fit(f"💰 Награда: {reward}"), w))
    dmg = f"{boss_config['damage_range'][0]}-{boss_config['damage_range'][1]}"
    lines.append(Visuals.frame_line_left(fit(f"⚔️ Урон: {dmg}"), w))
    lines.append(Visuals.frame_line_left(fit(f"⏱ Кулдаун: {BOSS_COOLDOWN_MINUTES}м"), w))
    lines.append(Visuals.frame_line_left(fit("⚡ Ульта: /ulta"), w))

    if state.get("deadline"):
        remaining = int(state["deadline"] - time.time())
        if remaining > 0:
            lines.append(Visuals.frame_line_left(fit(f"⏳ {remaining // 60} мин."), w))
        else:
            lines.append(Visuals.frame_line_left(fit("⏳ Время вышло..."), w))

    hits = list((state.get("hits") or {}).values())
    if hits:
        top = sorted(hits, key=lambda x: x.get("dmg", 0), reverse=True)[:3]
        medals = ["🥇", "🥈", "🥉"]
        lines.append(Visuals.frame_separator_left(w))
        lines.append(Visuals.frame_line_left(fit("🏆 Топ урона:"), w))
        for i, t in enumerate(top):
            name = Visuals.escape((t.get("name") or "")[:10])
            dmg_val = int(t.get("dmg", 0) or 0)
            lines.append(Visuals.frame_line_left(fit(f"{medals[i]} {name}: {dmg_val}"), w))

    # Battle Log
    battle_log = state.get("battle_log", [])
    if battle_log:
        lines.append(Visuals.frame_separator_left(w))
        lines.append(Visuals.frame_line_left(fit("📝 Ход битвы:"), w))
        for entry in battle_log[-6:]: # Show last 6
             icon = "💥"
             dmg_text = f"-{entry['dmg']}"

             if entry.get("evaded"):
                 icon = "💨"
                 dmg_text = "ПРОМАХ!"
             elif entry.get("is_weakness"):
                 icon = "🎯"
             elif entry.get("is_ult"):
                 icon = "⚡"
             elif entry.get("crit"):
                 icon = "🩸"

             user_name_raw = entry.get('name') or ''
             if len(user_name_raw) > 10:
                 user_name_raw = user_name_raw[:9] + "…"
             user_name = Visuals.escape(user_name_raw)

             log_line = f"{icon} {user_name}: {dmg_text}"
             lines.append(Visuals.frame_line_left(fit(log_line), w))

    lines.append(Visuals.frame_bottom_left(w))

    caption = "<pre>\n" + "\n".join(lines) + "\n</pre>"

    if last_action:
        caption += f"\n{last_action}"

    return caption

async def launch_boss(
    bot, chat_id, boss_id, container, duration=None, reward_settings=None
):
    boss_service = container.boss_service

    state = await boss_service.start_boss(
        boss_id, duration_hours=duration, reward_settings=reward_settings
    )

    # Image
    image_path = await boss_service.get_boss_image(boss_id)
    caption = render_boss_caption(state)

    msg = None
    if image_path:
        msg = await bot.send_photo(
            chat_id=chat_id,
            photo=FSInputFile(image_path),
            caption=caption,
            parse_mode="HTML",
            reply_markup=get_boss_keyboard()
        )
    else:
        msg = await bot.send_message(
            chat_id=chat_id,
            text=caption,
            parse_mode="HTML",
            reply_markup=get_boss_keyboard()
        )

    if msg:
        await boss_service.set_message_data(chat_id, msg.message_id, has_photo=bool(image_path))
        # Pin the boss message
        try:
            await bot.pin_chat_message(chat_id=chat_id, message_id=msg.message_id, disable_notification=True)
        except Exception as e:
            # If pinning fails (e.g., no rights), log but don't stop the boss launch
            logger.warning(f"Failed to pin boss message in chat {chat_id}: {e}")

from aiogram.fsm.context import FSMContext
from src.bot.handlers.boss_editor import BossEditorFSM

@router.message(Command("senseiboss"), AdminFilter())
async def sensei_boss(message: Message, command: CommandObject, container: Container, state: FSMContext):
    boss_service = container.boss_service

    # Check if boss exists
    current_state = await boss_service.get_state()
    if current_state and not current_state.get("is_dead") and not current_state.get("is_expired") and current_state.get("hp", 0) > 0:
        await message.answer("⚠️ Бой уже идет!")
        return

    if message.chat.type != "private":
        await message.answer("⚠️ Настройка босса доступна только в ЛС.")
        return

    await state.set_state(BossEditorFSM.choosing_action)
    # TODO: Send the actual keyboard with options
    await message.answer("Добро пожаловать в редактор боссов! (в разработке)")


@router.message(Command("killboss"), AdminFilter())
async def kill_boss(message: Message, container: Container):
    """Принудительно убить босса (без наград)."""
    boss_service = container.boss_service

    state = await boss_service.get_state()
    if not state or state.get("is_dead") or state.get("is_expired"):
        await message.answer("⚠️ Активного босса нет.")
        return

    await boss_service.stop_boss()
    await message.answer(
        "💀 <b>Босс был убит Сенсеем с одного удара.</b>\n❌ Битва остановлена, награды не выданы.",
        parse_mode="HTML"
    )



@router.message(F.text.lower().in_({"файт", "fight", "атака", "attack", "бить", "hit"}))
async def cmd_fight(message: Message, container: Container):
    state = await container.boss_service.get_state()
    if not state or state.get("is_dead") or state.get("is_expired") or state.get("hp", 0) <= 0:
        return
    try:
        await message.delete()
    except Exception:
        pass
    await process_boss_attack(message, container, is_ult=False)

@router.message(F.text.lower().in_({"ульта", "ult", "ultra", "ultimate", "/ulta"}))
async def cmd_ult(message: Message, container: Container):
    state = await container.boss_service.get_state()
    if not state or state.get("is_dead") or state.get("is_expired") or state.get("hp", 0) <= 0:
        return
    try:
        await message.delete()
    except Exception:
        pass
    await process_boss_attack(message, container, is_ult=True)

async def update_boss_message(bot, chat_id, message_id, has_photo, text, reply_markup=None):
    """Редактирует сообщение босса по ID."""
    try:
        if has_photo:
            await bot.edit_message_caption(
                chat_id=chat_id,
                message_id=message_id,
                caption=text,
                parse_mode="HTML",
                reply_markup=reply_markup
            )
        else:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                parse_mode="HTML",
                reply_markup=reply_markup
            )
    except Exception as e:
        if "message is not modified" not in str(e):
            pass # Log error?

async def process_boss_attack(event: CallbackQuery | Message, container: Container, is_ult: bool):
    """
    Unified handler for boss attacks (Hit & Ult).
    Supports both CallbackQuery (buttons) and Message (text commands).
    """
    boss_service = container.boss_service
    economy_service = container.economy_service

    user = event.from_user
    user_id = user.id
    is_callback = isinstance(event, CallbackQuery)

    # Get user data for katana
    user_data = await container.user_service.get_or_create(
        user_id=user_id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        is_bot=user.is_bot or False,
    )
    user_db = user_data["user"]

    if not user_db.get("has_katana", False):
        msg = "🚫 У тебя нет катаны! (Нужен предмет 'katana')"
        if is_callback:
            return await safe_answer(event, msg, show_alert=True)
        else:
            # Silent fail for text commands if no boss, but here we don't know if boss exists yet.
            # But usually we shouldn't spam.
            return

    katana_length = user_db.get("katana_length", 0.0)

    # Check minimum level requirement (from source bot)
    player_level = container.level_service.get_level(user_db.get("xp", 0))
    min_level = 5
    if player_level < min_level:
        msg = f"🚫 Минимальный уровень для участия в битве с боссом — {min_level}."
        if is_callback:
            return await safe_answer(event, msg, show_alert=True)
        else:
            sent = await event.answer(msg)
            asyncio.create_task(delete_message_delayed(sent, 3))
            return

    # Calculate BASE damage
    base_damage = random.randint(10, 20)
    crit_bonus = int(katana_length * 0.5)
    damage = base_damage + crit_bonus

    try:
        # result returns: BossAttackResult object
        result_obj = await boss_service.attack_boss(user_id, user.first_name, damage, is_ult=is_ult)

        state = result_obj.state
        result = result_obj.result_type
        actual_dmg = result_obj.actual_damage
        event_type = result_obj.event

    except ValueError as e:
        # Cooldown or requirements
        err_msg = str(e)

        # Check for Ult Cooldown to apply special notification
        if "Ульта на перезарядке" in err_msg:
            # "Уведомление ульта на перезарядке появляется с именем того ктовызывал на 5 секунд и исчезает"
            msg_text = f"⚠️ {user.first_name}, {err_msg}"

            sent_msg = None
            if is_callback:
                await safe_answer(event) # Close loading state
                sent_msg = await event.message.answer(msg_text)
            else:
                sent_msg = await event.answer(msg_text)

            if sent_msg:
                asyncio.create_task(delete_message_delayed(sent_msg, 5))
            return

        msg = f"⚠️ {err_msg}"
        if is_callback:
            return await safe_answer(event, msg, show_alert=True)
        else:
            sent = await event.answer(msg)
            asyncio.create_task(delete_message_delayed(sent, 3))
            return

    if not state:
        msg = "❌ Босс уже мёртв!"
        if is_callback:
            return await safe_answer(event, msg, show_alert=True)
        else:
            return # Silent if no boss

    # Prepare message update data
    chat_id = state.get("chat_id")
    message_id = state.get("message_id")
    has_photo = state.get("has_photo", False)

    if not chat_id or not message_id:
        # Fallback for old bosses without saved message info
        if is_callback:
            chat_id = event.message.chat.id
            message_id = event.message.message_id
            has_photo = bool(event.message.photo)
        else:
            # Cannot update message if we don't know where it is
            return

    if result == "expired":
        # Handle expiration penalty
        participants = list(state["hits"].keys())
        await economy_service.process_boss_loss(participants, 100.0)

        msg = "⏰ Время вышло! Босс сбежал!"
        if is_callback:
            await safe_answer(event, msg, show_alert=True)

        await update_boss_message(
            event.bot, chat_id, message_id, has_photo,
            "❌ <b>Босс сбежал!</b>\nВремя истекло. Все участники потеряли 100 монет.\n💰 Монеты ушли в банк Сенсея.",
            reply_markup=None
        )
        return

    if result == "dead":
        msg = "❌ Босс уже мёртв!"
        if is_callback:
            return await safe_answer(event, msg, show_alert=True)
        return

    if result == "evaded":
        msg = "💨 Босс увернулся от атаки!"
        if is_callback:
             await safe_answer(event, msg, show_alert=True)
        else:
             m = await event.answer(msg)
             await asyncio.sleep(2)
             try:
                 await m.delete()
             except Exception:
                 pass

        # Update message to show "Miss" in log
        caption = render_boss_caption(state, last_action=None)
        await update_boss_message(event.bot, chat_id, message_id, has_photo, caption, reply_markup=get_boss_keyboard())
        return

    # Result is "hit" or "killed"
    boss_config = BOSSES[state["boss_id"]]

    # Get hit stats for feedback
    user_key = str(user_id)
    user_stats = state["hits"].get(user_key, {})
    hit_count = user_stats.get("count", 0)
    user_total_dmg = user_stats.get("dmg", 0)
    combo_count = result_obj.combo_count

    # Handle events
    if event_type == "hp_75":
        await update_boss_message(
            event.bot,
            chat_id,
            message_id,
            has_photo,
            render_boss_caption(state, "👁️ <b>БОСС ЗАМЕТИЛ ТЕБЯ.</b>"),
            reply_markup=get_boss_keyboard(),
        )
        msg = await event.bot.send_message(chat_id, "👁️ <b>БОСС ПРОСНУЛСЯ.</b>\nКто первый дойдёт до MVP?", parse_mode="HTML")
        asyncio.create_task(delete_message_delayed(msg, 5))

    elif event_type == "hp_50":
        await update_boss_message(
            event.bot,
            chat_id,
            message_id,
            has_photo,
            render_boss_caption(state, "⚠️ <b>БОСС В ЯРОСТИ! (HP < 50%)</b>"),
            reply_markup=get_boss_keyboard(),
        )
        msg = await event.bot.send_message(chat_id, "⚠️ <b>ЯРОСТЬ!</b>\nТемп растёт. COMBO решает.", parse_mode="HTML")
        asyncio.create_task(delete_message_delayed(msg, 5))

    elif event_type == "hp_25":
        await update_boss_message(
            event.bot,
            chat_id,
            message_id,
            has_photo,
            render_boss_caption(state, "🩸 <b>ФИНАЛЬНАЯ ФАЗА! (HP < 25%)</b>"),
            reply_markup=get_boss_keyboard(),
        )
        msg = await event.bot.send_message(chat_id, "🩸 <b>ФИНАЛЬНАЯ ФАЗА.</b>\nНе дай ему уйти!", parse_mode="HTML")
        asyncio.create_task(delete_message_delayed(msg, 5))

    elif event_type == "hp_10":
        await update_boss_message(
            event.bot,
            chat_id,
            message_id,
            has_photo,
            render_boss_caption(state, "🔥 <b>ПОСЛЕДНИЙ РЫВОК! (HP < 10%)</b>"),
            reply_markup=get_boss_keyboard(),
        )
        msg = await event.bot.send_message(chat_id, "🔥 <b>10% HP!</b>\nСейчас решит один удар.", parse_mode="HTML")
        asyncio.create_task(delete_message_delayed(msg, 5))

    elif event_type == "weakness_started":
        await update_boss_message(
            event.bot,
            chat_id,
            message_id,
            has_photo,
            render_boss_caption(state, "😵 <b>БОСС ПОТЕРЯЛ РАВНОВЕСИЕ! (x2 УРОН)</b>"),
            reply_markup=get_boss_keyboard(),
        )
        msg = await event.bot.send_message(chat_id, "😵 <b>БОСС УЯЗВИМ!</b>\nНаносите двойной урон в течение 15 секунд!", parse_mode="HTML")
        asyncio.create_task(delete_message_delayed(msg, 5))

    # Prepare messages
    action_type = "УЛЬТА" if is_ult else "удар"

    alert_text = f"💥 -{actual_dmg} HP! (Всего: {user_total_dmg})"
    if combo_count > 1:
        alert_text = f"🔥 COMBO x{combo_count}! " + alert_text

    if is_ult:
        alert_text = f"✨ CRITICAL! 💥 УЛЬТА! -{actual_dmg} HP! (Всего: {user_total_dmg})"
    else:
        # Critical visual for normal hits if damage is high (e.g. > 15)
        if actual_dmg > 18: # Base max is around 20 + katana
             alert_text = f"⚡ CRITICAL! -{actual_dmg} HP!"

        # Show progress towards ult for normal hits
        from src.core.constants import BOSS_ULT_REQUIRED_HITS
        if hit_count < BOSS_ULT_REQUIRED_HITS:
            alert_text += f"\n(Ульта: {hit_count}/{BOSS_ULT_REQUIRED_HITS})"
        else:
             alert_text += "\n(Ульта готова!)"

        # --- xRocket Reward Logic ---
        if actual_dmg >= 20:
            user_level = container.level_service.get_level(user_db.get("xp", 0))
            if user_level >= 5:
                # Dynamic Settings
                reward_settings = await boss_service.get_reward_settings()

                # Check chance
                if random.random() < reward_settings["drop_chance"]:
                    reward_amount = round(random.uniform(reward_settings["reward_min"], reward_settings["reward_max"]), 4)

                    # Check pool
                    if await boss_service.check_pool_availability(reward_amount):
                        try:
                            success = await container.xrocket_service.transfer(user_id, "TONCOIN", reward_amount)
                            if success:
                                await boss_service.increment_pool_used(reward_amount)
                                alert_text += f"\n💎 <b>LUCKY HIT!</b> +{reward_amount} TON (xRocket)"

                                # Public notification
                                notification_text = f"💎 {user.first_name} выбил <b>{reward_amount} TON</b> с Босса!"
                                msg = await event.bot.send_message(chat_id, notification_text, parse_mode="HTML")
                                asyncio.create_task(delete_message_delayed(msg, 10))
                        except Exception as e:
                            # Log error but don't fail the attack
                            pass

    if is_callback:
        await safe_answer(event, alert_text)
    else:
        # Optionally reply to user for text command?
        # User said "react only if there is a boss".
        # Maybe a short reply "💥 -X HP" is good.
        # Message is deleted so we must use answer (send new message) instead of reply
        msg = await event.answer(alert_text)
        # Auto-delete hit confirmation to keep chat clean (optional but good for spam)
        # But for now just fix the error
        try:
             # Wait a bit and delete the hit confirmation?
             # Or just leave it? User asked for "Text commands for fighting now auto-delete to keep chat clean"
             # The COMMAND is deleted. The RESPONSE might be annoying if it stays.
             # Let's delete it after 3 seconds.
             await asyncio.sleep(3)
             await msg.delete()
        except Exception:
             pass

    if result == "killed":
        # Distribute rewards
        coins_reward = boss_config.get("coins_reward", 0)
        participants = list(state["hits"].keys())

        distribution_result = await economy_service.distribute_boss_reward(participants, float(coins_reward))

        reward_text = f"🎁 Награда: {boss_config['reward']}"
        if distribution_result["success"] and distribution_result["total_distributed"] > 0:
            per_user = distribution_result["reward_per_user"]
            reward_text += f"\n💰 {Visuals._fmt_coins(distribution_result['total_distributed'])} монет разделено между {distribution_result['count']} участниками ({Visuals._fmt_coins(per_user)} каждому) из банка Сенсея!"
        elif coins_reward > 0:
            reward_text += "\n⚠️ Банк Сенсея пуст! Монеты не выплачены."

        hit_desc = f"Последний удар ({action_type})"

        # --- LEADERBOARD ---
        leaderboard = await boss_service.get_leaderboard(limit=3)
        lb_text = "\n\n🏆 <b>MVP Битвы:</b>"
        medals = ["🥇", "🥈", "🥉"]
        for idx, entry in enumerate(leaderboard):
            medal = medals[idx] if idx < 3 else "🎖"
            lb_text += f"\n{medal} {Visuals.escape(entry['name'])}: {entry['dmg']} урона"

        final_text = f"🏆 <b>Босс повержен!</b>\n\n💀 {hit_desc}: {Visuals.escape(user.first_name)}\n{reward_text}{lb_text}"

        await update_boss_message(
            event.bot, chat_id, message_id, has_photo,
            final_text,
            reply_markup=None
        )

        # Victory notification
        await event.bot.send_message(
            chat_id=chat_id,
            text=f"🎉 <b>ПОБЕДА!</b>\nБосс <b>{boss_config['name']}</b> был уничтожен!\n\n{reward_text}",
            parse_mode="HTML"
        )
        return

    # Update message if not killed
    # Log is now inside the frame, so we don't need last_hit_text appended below
    caption = render_boss_caption(state, last_action=None)
    await update_boss_message(event.bot, chat_id, message_id, has_photo, caption, reply_markup=get_boss_keyboard())

@router.callback_query(F.data == "hit_boss")
async def hit_boss(callback: CallbackQuery, container: Container):
    await process_boss_attack(callback, container, is_ult=False)
