"""
��⚔��️ Сервис дуэлей (Sensei Duel Logic).
Refactored to use MongoDB directly instead of SQLAlchemy/UnitOfWork.
"""

import asyncio
import random
import time
import logging
import html
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any, Union

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from src.core.container import Container
from src.core.visuals import Visuals
from src.core.constants import LEVEL_XP_REQUIREMENTS
from src.services.duel_resources import (
    ARENAS, DODGE_GAGS_L, DODGE_GAGS_R, ATTACK_GAGS_L, ATTACK_GAGS_R,
    HIT_GAGS, MISS_GAGS, DUEL_COOLDOWN_SEC, DUEL_ACCEPT_TIMEOUT_SEC,
    DUEL_ROUND_TIMEOUT_SEC, ARENA_LOG_MAX_LINES,
    DuelDecisionCb, DuelMoveCb, DuelSurrenderCb, DuelUtilityCb
)

logger = logging.getLogger(__name__)

# Constants (internal or from resources)
DODGES = ("dodge_l", "dodge_r")
HITS = ("hit_l", "hit_r")

@dataclass
class Duel:
    id: int
    challenger_id: int
    opponent_id: int
    bet: int
    chat_id: int  # Main arena chat

    bot: Bot
    container: Container

    # State
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    accepted: bool = False
    finished: bool = False
    round_num: int = 0

    # Logic
    hits: Dict[int, int] = field(default_factory=dict)  # uid -> hits count
    actions: Dict[int, Dict[str, Optional[str]]] = field(default_factory=dict)
    # Structure: {uid: {"dodge": "dodge_l"|None, "attack": "hit_r"|None}}

    # Concurrency
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    timeout_task: Optional[asyncio.Task] = None
    round_deadline_mono: float = 0.0

    # Message IDs
    challenge_message_id: Optional[int] = None
    arena_message_id: Optional[int] = None
    control_message_ids: Dict[int, Optional[int]] = field(default_factory=dict) # uid -> msg_id

    # Flavor
    arena_name: str = "Додзё"
    arena_desc: str = "Тишина..."
    arena_gag: str = "..."
    log_lines: List[str] = field(default_factory=list)
    challenger_name: Optional[str] = None
    opponent_name: Optional[str] = None

    def __post_init__(self):
        self.hits[self.challenger_id] = 0
        self.hits[self.opponent_id] = 0

# ===== Utilities =====

def _pick_duel_id(existing_ids: set) -> int:
    # Try generous random first
    for _ in range(10):
        did = int(time.time() * 1000) % 10_000_000
        did = did * 10 + random.randint(0, 9)
        if did not in existing_ids:
            return did
    # Fallback
    did = random.randint(1_000_000, 99_999_999)
    while did in existing_ids:
        did = random.randint(1_000_000, 99_999_999)
    return did

def pick_arena() -> tuple[str, str, str]:
    return random.choice(ARENAS)

def dir_word(move: Optional[str]) -> str:
    if not move: return "—"
    return "влево" if "_l" in move else "вправо"

def dir_arrow(move: Optional[str]) -> str:
    if not move: return "?"
    return "��⬅��️" if "_l" in move else "��➡��️"

def _name_from_user(user_doc: Optional[dict], fallback_id: int) -> str:
    # user_doc is a MongoDB document (dict) or None
    if not user_doc:
        return str(fallback_id)
    return user_doc.get("username") or user_doc.get("first_name") or str(fallback_id)

def narrate_dodge(name: str, dodge: str) -> str:
    gag = random.choice(DODGE_GAGS_L if dodge.endswith("_l") else DODGE_GAGS_R)
    return f"���🏃 @{name} {gag} {dir_arrow(dodge)}"

def narrate_attack(name: str, attack: str) -> str:
    gag = random.choice(ATTACK_GAGS_L if attack.endswith("_l") else ATTACK_GAGS_R)
    return f"��⚔��️ @{name} {gag} {dir_arrow(attack)}"

def narrate_outcome(attacker: str, hit: bool) -> str:
    return f"���🩸 @{attacker} {random.choice(HIT_GAGS if hit else MISS_GAGS)}"

# ===== Service =====

class DuelService:
    def __init__(self, container: Container):
        self.container = container
        self.duels: Dict[int, Duel] = {} # int ID

        # Get references to services we'll need
        self.user_service = container.user_service
        self.economy_service = container.economy_service

        # Get direct database collections for performance
        self.db = container.mongo_client.database
        self.users = self.db.users
        self.transactions = self.db.transactions

    # --- Core Public Methods ---

    def _is_in_active_duel(self, user_id: int) -> bool:
        for duel in self.duels.values():
            if not duel.finished and user_id in (duel.challenger_id, duel.opponent_id):
                return True
        return False

    async def create_duel(self, challenger_id: int, opponent_id: int, bet: int, chat_id: int, bot: Bot) -> Union[Duel, str]:
        logger.info("Create duel: challenger=%s opponent=%s bet=%s chat=%s", challenger_id, opponent_id, bet, chat_id)
        # 0. Check busy
        if self._is_in_active_duel(challenger_id):
            return "❜ Вы уже участвуете в активной дуэли (или отправили вызов)."
        if self._is_in_active_duel(opponent_id):
            return "❜ Соперник сейчас занят в другой дуэли."

        # 1. Check eligibility
        error = await self._check_eligibility(challenger_id, opponent_id, bet)
        if error: return error

        # 2. Escrow
        if bet > 0:
            if not await self._escrow_funds(challenger_id, opponent_id, bet):
                logger.info(
                    "Create duel failed (insufficient funds): challenger=%s opponent=%s bet=%s",
                    challenger_id,
                    opponent_id,
                    bet,
                )
                return "❜ Недостаточно средств для ставки."

        # 3. Create
        did = _pick_duel_id(set(self.duels.keys()))
        aname, adesc, agag = pick_arena()

        duel = Duel(
            id=did,
            challenger_id=challenger_id,
            opponent_id=opponent_id,
            bet=bet,
            chat_id=chat_id,
            bot=bot,
            container=self.container,
            arena_name=aname,
            arena_desc=adesc,
            arena_gag=agag
        )
        self.duels[did] = duel
        logger.info("Duel created: id=%s challenger=%s opponent=%s bet=%s", did, challenger_id, opponent_id, bet)

        # 4. Start Accept Timer
        duel.timeout_task = asyncio.create_task(self._wait_for_accept(did))

        return duel

    async def process_decision(self, duel_id: int, user_id: int, decision: str) -> str:
        duel = self.duels.get(duel_id)
        if not duel: return "❜ Дуэль не найдена."

        async with duel.lock:
            if duel.finished: return "❜ Дуэль завершена."
            if duel.accepted: return "✅ Уже идет."

            if decision == 'x':
                if user_id in (duel.challenger_id, duel.opponent_id):
                    await self._cancel_duel(duel, "❜ Дуэль отклонена.")
                    return "Отклонено."
                return "❜ Вы не участник."

            if decision == 'a':
                if user_id != duel.opponent_id: return "❜ Это не вам."

                duel.accepted = True
                if duel.timeout_task: duel.timeout_task.cancel()

                # Cleanup accept buttons
                try:
                    await duel.bot.edit_message_reply_markup(duel.chat_id, duel.challenge_message_id, reply_markup=None)
                except TelegramBadRequest as e:
                    logger.warning("Duel %s: accept markup cleanup failed: %s", duel.id, e)
                except Exception:
                    logger.exception("Duel %s: accept markup cleanup failed critically", duel.id)

                # Start
                asyncio.create_task(self._start_round(duel))
                return "✅ Принято! Смотрите ЛС."

        return "⚠��️ Ошибка."

    async def process_move(self, duel_id: int, user_id: int, move: str) -> str:
        # move is 'hit_l', 'hit_r', 'dodge_l', 'dodge_r'
        duel = self.duels.get(duel_id)
        if not duel: return "❜ Дуэль не найдена."

        async with duel.lock:
            if duel.finished: return "❜ Дуэль завершена."
            if user_id not in (duel.challenger_id, duel.opponent_id): return "❜ Не ваш бой."

            # Update action
            actions = duel.actions.setdefault(user_id, {"dodge": None, "attack": None})

            if "hit" in move:
                actions["attack"] = move
            elif "dodge" in move:
                actions["dodge"] = move

            # Update PM
            await self._update_control_dm(duel, user_id)

            return "Принято."

    async def process_utility(self, duel_id: int, user_id: int, action: str) -> str:
        duel = self.duels.get(duel_id)
        if not duel: return "❜ Дуэль не найдена."

        # 'open' doesn't need lock usually, but safe to have.
        # 'auto' and 'reset' modify state so need lock.

        async with duel.lock:
            if duel.finished: return "❜ Дуэль завершена."
            if user_id not in (duel.challenger_id, duel.opponent_id): return "❜ Не ваш бой."

            if action == 'open':
                await self._update_control_dm(duel, user_id)
                return "���📩 Панель отправлена в ЛС."

            if action == 'auto':
                actions = duel.actions.setdefault(user_id, {"dodge": None, "attack": None})
                if not actions["dodge"]: actions["dodge"] = random.choice(DODGES)
                if not actions["attack"]: actions["attack"] = random.choice(HITS)
                await self._update_control_dm(duel, user_id)
                return "���🤖 Автоход сделан."

            if action == 'reset':
                duel.actions[user_id] = {"dodge": None, "attack": None}
                await self._update_control_dm(duel, user_id)
                return "���🔄 Ход сброшен."

            return "��❓ Неизвестное действие."

    async def surrender(self, duel_id: int, user_id: int) -> str:
        duel = self.duels.get(duel_id)
        if not duel: return "❜ Нет такой дуэли."

        async with duel.lock:
            if duel.finished: return "❜ Уже всё."
            if user_id not in (duel.challenger_id, duel.opponent_id): return "❜ Не вы."

            winner_id = duel.opponent_id if user_id == duel.challenger_id else duel.challenger_id
            await self._finish_duel(duel, winner_id, f"���🏳��️ Игрок {user_id} сдался!")
            return "���🏳��️ Вы сдались."

    # --- Internal Logic ---

    async def _start_round(self, duel: Duel):
        duel.round_num += 1
        duel.round_deadline_mono = time.monotonic() + DUEL_ROUND_TIMEOUT_SEC

        # Reset actions
        duel.actions[duel.challenger_id] = {"dodge": None, "attack": None}
        duel.actions[duel.opponent_id] = {"dodge": None, "attack": None}

        duel.log_lines.append(f"��🔔 <b>Раунд {duel.round_num}</b>")

        await self._update_arena(duel)
        await self._update_control_dm(duel, duel.challenger_id)
        await self._update_control_dm(duel, duel.opponent_id)

        duel.timeout_task = asyncio.create_task(self._wait_for_round(duel.id, duel.round_num))

    async def _wait_for_round(self, duel_id: int, round_num: int):
        # Tick every second to update timer in arena
        everyone_ready = False

        timed_out = True
        for _ in range(int(DUEL_ROUND_TIMEOUT_SEC)):
            if self.duels.get(duel_id) is None: return
            await asyncio.sleep(1)
            duel = self.duels.get(duel_id)
            if not duel or duel.finished or duel.round_num != round_num: return

            # Update timer in arena
            await self._update_arena(duel)

            # Update timer in PMs (every second as requested)
            await self._update_control_dm(duel, duel.challenger_id)
            await self._update_control_dm(duel, duel.opponent_id)

            # Check if everyone ready
            if self._all_ready(duel):
                timed_out = False
                break

        # Final wait if needed
        if timed_out:
            remain = duel.round_deadline_mono - time.monotonic()
            if remain > 0:
                await asyncio.sleep(remain)

        duel = self.duels.get(duel_id)
        if not duel or duel.finished or duel.round_num != round_num: return

        async with duel.lock:
            # Auto-fill missing
            for uid in (duel.challenger_id, duel.opponent_id):
                acts = duel.actions[uid]
                if not acts["dodge"]: acts["dodge"] = random.choice(DODGES)
                if not acts["attack"]: acts["attack"] = random.choice(HITS)

            if timed_out:
                duel.log_lines.append("��⏰ Время вышло!")
            await self._resolve_round(duel)

    def _all_ready(self, duel: Duel) -> bool:
        for uid in (duel.challenger_id, duel.opponent_id):
            a = duel.actions.get(uid, {})
            if not a.get("dodge") or not a.get("attack"):
                return False
        return True

    async def _resolve_round(self, duel: Duel):
        # Calculate results
        ch = duel.challenger_id
        op = duel.opponent_id

        ch_acts = duel.actions[ch]
        op_acts = duel.actions[op]

        # Hit Logic: Attacker Hit vs Defender Dodge
        # ch hit if: ch_attack != op_dodge (different directions)
        # op hit if: op_attack != ch_dodge

        # Directions: hit_l vs dodge_l -> SAME -> MISS
        # hit_l vs dodge_r -> DIFF -> HIT

        def get_dir(s): return s.split('_')[1] if s else ''

        ch_hit_success = get_dir(ch_acts["attack"]) != get_dir(op_acts["dodge"])
        op_hit_success = get_dir(op_acts["attack"]) != get_dir(ch_acts["dodge"])

        if ch_hit_success: duel.hits[ch] += 1
        if op_hit_success: duel.hits[op] += 1

        # Names
        u_ch_doc = await self.users.find_one({"id": ch})
        u_op_doc = await self.users.find_one({"id": op})
        name_ch = _name_from_user(u_ch_doc, ch)
        name_op = _name_from_user(u_op_doc, op)

        # Log
        lines = []

        # Visual Summary of Move
        # �� 👤A: �� 🛡��️��⬅��️ | �� ⚔��️��➡��️
        def move_icon(d_move, a_move):
            d_arrow = "��⬅��️" if d_move and "_l" in d_move else "��➡��️"
            a_arrow = "��⬅��️" if a_move and "_l" in a_move else "��➡��️"
            return f"���🛡��️{d_arrow} �� ⚔��️{a_arrow}"

        lines.append(f"���🔴 {name_ch}: {move_icon(ch_acts['dodge'], ch_acts['attack'])}")
        lines.append(f"���🔵 {name_op}: {move_icon(op_acts['dodge'], op_acts['attack'])}")

        lines.append(narrate_dodge(name_ch, ch_acts["dodge"]))
        lines.append(narrate_dodge(name_op, op_acts["dodge"]))
        lines.append(narrate_attack(name_ch, ch_acts["attack"]))
        lines.append(narrate_attack(name_op, op_acts["attack"]))

        # Outcome Visual
        res_ch = "���🩸 ПОПАДАНИЕ!" if ch_hit_success else "���💨 ПРОМАХ!"
        res_op = "���🩸 ПОПАДАНИЕ!" if op_hit_success else "���💨 ПРОМАХ!"

        lines.append(f"���🔴 Атака {name_ch}: {res_ch}")
        lines.append(f"���🔵 Атака {name_op}: {res_op}")

        lines.append(narrate_outcome(name_ch, ch_hit_success))
        lines.append(narrate_outcome(name_op, op_hit_success))
        lines.append(f"���📊 Счёт: {duel.hits[ch]} : {duel.hits[op]}")

        duel.log_lines.extend(lines)

        # Separator for next round in log
        duel.log_lines.append("�〰��️�〰��️�〰��️�〰��️�〰��️�〰��️�〰��️�〰��️")

        await self._update_arena(duel)

        # Win Check
        finished = (duel.hits[ch] >= 2) or (duel.hits[op] >= 2) or (duel.round_num >= 3)

        if finished:
            winner = None
            if duel.hits[ch] > duel.hits[op]: winner = ch
            elif duel.hits[op] > duel.hits[ch]: winner = op
            else:
                # Tie breaker or Random? User snippet: random if tie
                winner = random.choice([ch, op])
                duel.log_lines.append("��⚖��️ Судья закрыл глаза и ткнул случайно пальцем в победителя.")

            await self._finish_duel(duel, winner, "���🏆 Победа!")
        else:
            await self._start_round(duel)

    # --- Rendering & Updates ---

    async def _update_arena(self, duel: Duel):
        # Build text
        # Fetch fresh user data just in case
        if not duel.challenger_name:
            c_doc = await self.users.find_one({"id": duel.challenger_id})
            duel.challenger_name = _name_from_user(c_doc, duel.challenger_id)
        if not duel.opponent_name:
            o_doc = await self.users.find_one({"id": duel.opponent_id})
            duel.opponent_name = _name_from_user(o_doc, duel.opponent_id)

        c_name = duel.challenger_name
        o_name = duel.opponent_name

        left = max(0, int(duel.round_deadline_mono - time.monotonic())) if duel.accepted else DUEL_ACCEPT_TIMEOUT_SEC

        if duel.finished:
            log_view = "\n".join(duel.log_lines) if duel.log_lines else "..."
        else:
            # Show full log always, as requested by user ("лог в чате полный всех трех раундов")
            # Telegram limit is 4096, 3 rounds should fit (~50 lines max).
            log_view = "\n".join(duel.log_lines) if duel.log_lines else "..."

        # === Visuals Construction ===
        w = 32
        lines = [Visuals.frame_top_left(w)]

        # Header
        lines.append(Visuals.frame_line_left(f"���🏟��️ {duel.arena_name}", w))
        lines.append(Visuals.frame_separator_left(w))

        # Player 1
        hp_c = 2 - duel.hits.get(duel.challenger_id, 0)
        hp_c_str = "��❤��️" * hp_c + "���🖤" * (2 - hp_c)
        lines.append(Visuals.frame_line_left(f"���🔴 {c_name}", w))
        lines.append(Visuals.frame_line_left(f"HP: {hp_c_str}", w))

        # Player 2
        lines.append(Visuals.frame_separator_left(w))
        hp_o = 2 - duel.hits.get(duel.opponent_id, 0)
        hp_o_str = "��❤��️" * hp_o + "���🖤" * (2 - hp_o)
        lines.append(Visuals.frame_line_left(f"���🔵 {o_name}", w))
        lines.append(Visuals.frame_line_left(f"HP: {hp_o_str}", w))

        lines.append(Visuals.frame_separator_left(w))

        # Status / Timer
        if duel.finished:
             lines.append(Visuals.frame_line_left("���🏁 ДУЭЛ�Ь ЗАВЕРШЕНА", w))
        elif not duel.accepted:
             lines.append(Visuals.frame_line_left(f"��⏳ Ожидание: {left}с", w))
        else:
             # Progress bar for timer
             bar = Visuals.progress_bar(left, DUEL_ROUND_TIMEOUT_SEC, length=8, style="square")
             lines.append(Visuals.frame_line_left(f"��⏳ {bar}", w))
             lines.append(Visuals.frame_line_left(f"Раунд: {duel.round_num} | Ставка: {duel.bet}", w))

             # Readiness indicators (compact)
             c_act = duel.actions.get(duel.challenger_id, {})
             o_act = duel.actions.get(duel.opponent_id, {})
             c_ready = "✅" if (c_act.get("dodge") and c_act.get("attack")) else "���💭"
             o_ready = "✅" if (o_act.get("dodge") and o_act.get("attack")) else "���💭"
             lines.append(Visuals.frame_line_left(f"Статус: �� 🔴{c_ready} vs �� 🔵{o_ready}", w))

        lines.append(Visuals.frame_bottom_left(w))

        frame_text = "\n".join(lines)

        controls_msg = ""
        if duel.accepted and not duel.finished:
            controls_msg = "\n���📩 <b>Управление боем — в ЛС с ботом!</b>\n<i>(Нажмите «Управление» если потеряли чат)</i>"

        text = (
            f"<pre>{frame_text}</pre>\n"
            f"<i>{duel.arena_desc}</i>\n"
            f"⚠��️ {duel.arena_gag}\n"
            f"{controls_msg}\n"
            f"���📜 <b>Хроника:</b>\n"
            f"<pre>{log_view}</pre>"
        )

        # Buttons
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="���📩 Управление",
                    callback_data=DuelUtilityCb(id=duel.id, u=0, a='open').pack()
                )
            ]
        ])

        try:
            if not duel.arena_message_id:
                msg = await duel.bot.send_message(duel.chat_id, text, reply_markup=kb, parse_mode="HTML")
                duel.arena_message_id = msg.message_id
            else:
                await duel.bot.edit_message_text(
                    chat_id=duel.chat_id,
                    message_id=duel.arena_message_id,
                    text=text,
                    reply_markup=kb,
                    parse_mode="HTML"
                )
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e):
                logger.warning(f"Duel {duel.id}: Arena update failed: {e}")
        except Exception as e:
            logger.exception(f"Duel {duel.id}: Arena update failed critically")

    async def _update_control_dm(self, duel: Duel, user_id: int):
        # Build text
        actions = duel.actions.get(user_id, {})

        # Opponent name
        other_id = duel.opponent_id if user_id == duel.challenger_id else duel.challenger_id
        other_doc = await self.users.find_one({"id": other_id})
        other_name = _name_from_user(other_doc, other_id)

        left = max(0, int(duel.round_deadline_mono - time.monotonic()))

        text = (
            f"<b>��⚔��️ Дуэль vs {other_name}</b>\n"
            f"Раунд: {duel.round_num}, Время: {left}с\n"
            f"--------------------\n"
            f"<b>Ваш ход:</b>\n"
            f"Уворот: {dir_word(actions.get('dodge'))} {dir_arrow(actions.get('dodge'))}\n"
            f"Атака: {dir_word(actions.get('attack'))} {dir_arrow(actions.get('attack'))}\n"
            f"--------------------\n"
            f"<i>Выберите уворот и атаку.</i>"
        )

        # Build keyboard
        did = duel.id
        kb_list = [
            [
                InlineKeyboardButton(text="���🛡��️ Увернуться влево", callback_data=DuelMoveCb(id=did, u=user_id, m='dodge_l').pack()),
                InlineKeyboardButton(text="���🛡��️ Увернуться вправо", callback_data=DuelMoveCb(id=did, u=user_id, m='dodge_r').pack())
            ],
            [
                InlineKeyboardButton(text="��⚔��️ Ударить влево", callback_data=DuelMoveCb(id=did, u=user_id, m='hit_l').pack()),
                InlineKeyboardButton(text="��⚔��️ Ударить вправо", callback_data=DuelMoveCb(id=did, u=user_id, m='hit_r').pack())
            ],
            [
                InlineKeyboardButton(text="���🤖 Автоход", callback_data=DuelUtilityCb(id=did, u=user_id, a='auto').pack()),
                InlineKeyboardButton(text="���🔄 Сброс", callback_data=DuelUtilityCb(id=did, u=user_id, a='reset').pack())
            ],
            [
                InlineKeyboardButton(text="���🏳��️ Сдаться", callback_data=DuelSurrenderCb(id=did, u=user_id).pack())
            ]
        ]
        kb = InlineKeyboardMarkup(inline_keyboard=kb_list)

        # Send/Edit
        msg_id = duel.control_message_ids.get(user_id)
        try:
            if not msg_id:
                msg = await duel.bot.send_message(user_id, text, reply_markup=kb, parse_mode="HTML")
                duel.control_message_ids[user_id] = msg.message_id
            else:
                await duel.bot.edit_message_text(
                    chat_id=user_id,
                    message_id=msg_id,
                    text=text,
                    reply_markup=kb,
                    parse_mode="HTML"
                )
        except TelegramForbiddenError:
            # User blocked bot, auto-surrender?
            logger.warning(f"User {user_id} blocked bot during duel {duel.id}")
            # This will trigger surrender from the other side
            await self.surrender(duel.id, user_id)
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e):
                logger.warning(f"Duel {duel.id}: Control update for {user_id} failed: {e}")
                # Fall back to sending a new message
                msg = await duel.bot.send_message(user_id, text, reply_markup=kb, parse_mode="HTML")
                duel.control_message_ids[user_id] = msg.message_id
        except Exception as e:
            logger.exception(f"Duel {duel.id}: Control update for {user_id} failed critically")

    async def _finish_duel(self, duel: Duel, winner_id: Optional[int], reason: str):
        if duel.finished: return
        duel.finished = True

        if duel.timeout_task:
            duel.timeout_task.cancel()

        loser_id = None
        if winner_id:
            loser_id = duel.opponent_id if winner_id == duel.challenger_id else duel.challenger_id

        duel.log_lines.append(f"<b>{reason}</b>")

        if winner_id and loser_id:
            # Get fresh user documents
            winner_doc = await self.users.find_one({"id": winner_id})
            loser_doc = await self.users.find_one({"id": loser_id})

            if winner_doc and loser_doc:
                coins_reward = float(duel.bet * 2) if duel.bet > 0 else 0.0

                # Update winner
                winner_wins = winner_doc.get("wins", 0) + 1
                winner_xp = winner_doc.get("xp", 0) + 50
                winner_katana_length = winner_doc.get("katana_length", 0.0)

                winner_update = {
                    "wins": winner_wins,
                    "xp": winner_xp,
                }

                if winner_doc.get("has_katana", False):
                    winner_katana_length = round((winner_katana_length or 0.0) + 0.01, 2)
                    winner_update["katana_length"] = winner_katana_length

                await self.users.update_one(
                    {"id": winner_id},
                    {"$set": winner_update}
                )

                winner_name = _name_from_user(winner_doc, winner_id)
                duel.log_lines.append(f"��✨ {winner_name} получает +50 XP и +0.01 к катане.")

                if coins_reward > 0:
                    await self.users.update_one(
                        {"id": winner_id},
                        {"$inc": {"coins": coins_reward}}
                    )
                    duel.log_lines.append(f"���💰 Победитель получает {int(coins_reward)} монет!")

                    # Create transaction for winner's winnings
                    tx_doc = {
                        "user_id": winner_id,
                        "tx_type": "duel_win",
                        "coins_change": coins_reward,
                        "xp_change": 50,
                        "description": f"Победа в дуэли #{duel.id} против {loser_id}",
                        "created_at": datetime.now(timezone.utc),
                    }
                    await self.transactions.insert_one(tx_doc)

                # Update loser
                loser_losses = loser_doc.get("losses", 0) + 1
                loser_katana_length = loser_doc.get("katana_length", 0.0)

                loser_update = {
                    "losses": loser_losses,
                }

                if loser_doc.get("has_katana", False):
                    loser_katana_length = round(max(0.0, (loser_katana_length or 0.0) - 0.01), 2)
                    loser_update["katana_length"] = loser_katana_length

                await self.users.update_one(
                    {"id": loser_id},
                    {"$set": loser_update}
                )

                loser_name = _name_from_user(loser_doc, loser_id)
                duel.log_lines.append(f"���💔 {loser_name} теряет -0.01 от катаны.")

                # Create transaction for loser's loss (if any coins were lost)
                # Actually, coins are handled via the escrow system below

                # Create transaction records for XP changes
                winner_tx_doc = {
                    "user_id": winner_id,
                    "tx_type": "duel_win",
                    "xp_change": 50,
                    "coins_change": 0,  # Coins handled separately
                    "description": f"Победа в дуэли #{duel.id} (XP only)",
                    "created_at": datetime.now(timezone.utc),
                }
                await self.transactions.insert_one(winner_tx_doc)

                loser_tx_doc = {
                    "user_id": loser_id,
                    "tx_type": "duel_loss",
                    "xp_change": 0,
                    "coins_change": 0,
                    "description": f"Поражение в дуэли #{duel.id}",
                    "created_at": datetime.now(timezone.utc),
                }
                await self.transactions.insert_one(loser_tx_doc)

                logger.info(
                    "Duel finished: id=%s winner=%s loser=%s bet=%s reason=%s",
                    duel.id,
                    winner_id,
                    loser_id,
                    duel.bet,
                    reason,
                )

        # Handle escrow/refund of bets
        if duel.bet > 0:
            if winner_id and loser_id:
                # Transfer bet*2 from escrow to winner
                await self.users.update_one(
                    {"id": winner_id},
                    {"$inc": {"coins": float(duel.bet * 2)}}
                )

                # Create transaction for the bet transfer
                tx_doc = {
                    "user_id": winner_id,
                    "tx_type": "duel_bet_payout",
                    "coins_change": float(duel.bet * 2),
                    "xp_change": 0,
                    "description": f"Выигрыш ставки в дуэли #{duel.id}",
                    "created_at": datetime.now(timezone.utc),
                }
                await self.transactions.insert_one(tx_doc)
            else:
                # Refund both players if no winner (shouldn't happen in practice, but safe)
                await self.users.update_one(
                    {"id": duel.challenger_id},
                    {"$inc": {"coins": float(duel.bet)}}
                )
                await self.users.update_one(
                    {"id": duel.opponent_id},
                    {"$inc": {"coins": float(duel.bet)}}
                )

                # Create refund transactions
                for uid in (duel.challenger_id, duel.opponent_id):
                    tx_doc = {
                        "user_id": uid,
                        "tx_type": "duel_bet_refund",
                        "coins_change": float(duel.bet),
                        "xp_change": 0,
                        "description": f"Возврат ставки в дуэли #{duel.id}",
                        "created_at": datetime.now(timezone.utc),
                    }
                    await self.transactions.insert_one(tx_doc)

        # Final update
        await self._update_arena(duel)

        # Cleanup PMs
        for uid in (duel.challenger_id, duel.opponent_id):
            mid = duel.control_message_ids.get(uid)
            if mid:
                try:
                    # Get final user documents for the message
                    final_doc = await self.users.find_one({"id": uid})
                    final_name = _name_from_user(final_doc, uid) if final_doc else f"User {uid}"

                    await duel.bot.edit_message_text(
                        chat_id=uid,
                        message_id=mid,
                        text=f"Дуэль #{duel.id} завершена.\n" + "\n".join(duel.log_lines[-5:]),
                        reply_markup=None,
                        parse_mode="HTML"
                    )
                except TelegramBadRequest as e:
                    logger.warning("Duel %s: final PM update failed for %s: %s", duel.id, uid, e)
                except TelegramForbiddenError:
                    logger.warning("Duel %s: final PM forbidden for %s", duel.id, uid)
                except Exception:
                    logger.exception("Duel %s: final PM update failed critically for %s", duel.id, uid)

        # Remove from active duels after a delay
        asyncio.create_task(self._archive_duel(duel.id))

    async def _cancel_duel(self, duel: Duel, reason: str):
        if duel.finished: return
        duel.finished = True

        if duel.timeout_task:
            duel.timeout_task.cancel()

        # Refund
        if duel.bet > 0:
            # Refund both players
            await self.users.update_one(
                {"id": duel.challenger_id},
                {"$inc": {"coins": float(duel.bet)}}
            )
            await self.users.update_one(
                {"id": duel.opponent_id},
                {"$inc": {"coins": float(duel.bet)}}
            )

            # Create refund transactions
            for uid in (duel.challenger_id, duel.opponent_id):
                tx_doc = {
                    "user_id": uid,
                    "tx_type": "duel_bet_refund",
                    "coins_change": float(duel.bet),
                    "xp_change": 0,
                    "description": f"Возврат ставки дуэли #{duel.id}",
                    "created_at": datetime.now(timezone.utc),
                }
                await self.transactions.insert_one(tx_doc)

            logger.info("Duel canceled with refund: id=%s bet=%s reason=%s", duel.id, duel.bet, reason)

        # Update messages
        try:
            await duel.bot.edit_message_text(
                chat_id=duel.chat_id,
                message_id=duel.challenge_message_id,
                text=reason,
                reply_markup=None
            )
        except TelegramBadRequest as e:
            logger.warning("Duel %s: cancel chat message update failed: %s", duel.id, e)
        except Exception:
            logger.exception("Duel %s: cancel chat message update failed critically", duel.id)

        # Remove from active duels
        asyncio.create_task(self._archive_duel(duel.id))

    async def _archive_duel(self, duel_id: int):
        await asyncio.sleep(60) # Keep it around for a bit for any late queries
        self.duels.pop(duel_id, None)
        logger.info(f"Archived duel {duel_id}")

    async def _wait_for_accept(self, duel_id: int):
        await asyncio.sleep(DUEL_ACCEPT_TIMEOUT_SEC)
        duel = self.duels.get(duel_id)
        if duel and not duel.accepted and not duel.finished:
            async with duel.lock:
                await self._cancel_duel(duel, "��⏰ Время вышло.")

    async def _check_eligibility(self, cid: int, oid: int, bet: int) -> Optional[str]:
        if cid == oid:
            return "❜ Нельзя вызвать самого себя."

        # Check if users exist
        challenger_doc = await self.users.find_one({"id": cid})
        opponent_doc = await self.users.find_one({"id": oid})

        if not opponent_doc:
            return "❜ Соперник не найден в базе."
        if not challenger_doc:
            return "❜ Вы не найдены в базе."

        # Note: Cooldown check disabled as get_last_duel_time method doesn't exist
        # TODO: Implement duel cooldown tracking if needed

        # Bet checks - allow bet = 0 (no bet duel)
        if bet < 0:
            return "❜ Ставка не может быть отрицательной."
        if bet != 0 and bet < 300:  # Only check minimum if bet > 0
            return "❜ Минимальная ставка — 300 монет."

        # Only check balances if there's an actual bet
        if bet > 0:
            if (challenger_doc.get("coins", 0.0) < bet):
                return "❜ У вас недостаточно средств для такой ставки."
            if (opponent_doc.get("coins", 0.0) < bet):
                return "❜ У соперника недостаточно средств для такой ставки."

        return None

    async def _escrow_funds(self, cid: int, oid: int, bet: int) -> bool:
        # Use a lock to prevent race conditions during escrow
        lock_key = f"duel_escrow:{min(cid, oid)}:{max(cid, oid)}"
        # We'll use a simple locking mechanism - in production we'd use something more robust
        # For now, we'll do the check and update in a way that minimizes race conditions

        challenger_doc = await self.users.find_one({"id": cid})
        opponent_doc = await self.users.find_one({"id": oid})

        if not challenger_doc or not opponent_doc:
            logger.info("Escrow failed (user missing): c=%s o=%s", cid, oid)
            return False

        challenger_coins = challenger_doc.get("coins", 0.0)
        opponent_coins = opponent_doc.get("coins", 0.0)

        if challenger_coins < bet or opponent_coins < bet:
            logger.info(
                "Escrow failed (insufficient): c=%s c_coins=%s o=%s o_coins=%s bet=%s",
                cid,
                challenger_coins,
                oid,
                opponent_coins,
                bet,
            )
            return False

        # Deduct bets from both users
        await self.users.update_one(
            {"id": cid},
            {"$inc": {"coins": -float(bet)}}
        )
        await self.users.update_one(
            {"id": oid},
            {"$inc": {"coins": -float(bet)}}
        )

        # Create transaction records for the escrow
        for uid in (cid, oid):
            tx_doc = {
                "user_id": uid,
                "tx_type": "duel_escrow",
                "coins_change": -float(bet),
                "xp_change": 0,
                "description": f"Ставка в дуэли",
                "created_at": datetime.now(timezone.utc),
            }
            await self.transactions.insert_one(tx_doc)

        logger.info("Escrow success: c=%s o=%s bet=%s", cid, oid, bet)
        return True