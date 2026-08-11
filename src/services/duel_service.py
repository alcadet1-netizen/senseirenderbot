"""
⚔️ Сервис дуэлей (Sensei Duel Logic).
Refactored to match the "Best of Both" requirements:
- Dual-action rounds (Attack + Dodge selection).
- Rich Arena flavor and logging.
- PM-based controls with live updates.
- Int-based IDs for user friendliness.
"""

import asyncio
import random
import time
import logging
import html
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, List, Any, Union

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from src.core.container import Container
from src.core.visuals import Visuals
from src.core.constants import LEVEL_XP_REQUIREMENTS
from src.infra.database.models import TransactionType
from src.infra.database.uow import UnitOfWork
from src.domain.repositories import UserRepository, TransactionRepository
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
    created_at: datetime = field(default_factory=datetime.now)
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
    return "⬅️" if "_l" in move else "➡️"

def _name_from_user(u: Optional[Any], fallback_id: int) -> str:
    # u is a User model or dict
    if not u: return str(fallback_id)
    # Check if u is SQLAlchemy model or dict
    if isinstance(u, dict):
        return u.get("username") or u.get("first_name") or str(fallback_id)
    return getattr(u, "username", None) or getattr(u, "first_name", None) or str(fallback_id)

def narrate_dodge(name: str, dodge: str) -> str:
    gag = random.choice(DODGE_GAGS_L if dodge.endswith("_l") else DODGE_GAGS_R)
    return f"🏃 @{name} {gag} {dir_arrow(dodge)}"

def narrate_attack(name: str, attack: str) -> str:
    gag = random.choice(ATTACK_GAGS_L if attack.endswith("_l") else ATTACK_GAGS_R)
    return f"⚔️ @{name} {gag} {dir_arrow(attack)}"

def narrate_outcome(attacker: str, hit: bool) -> str:
    return f"🩸 @{attacker} {random.choice(HIT_GAGS if hit else MISS_GAGS)}"

# ===== Service =====

class DuelService:
    def __init__(self, container: Container):
        self.container = container
        self.duels: Dict[int, Duel] = {} # int ID

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
            return "❌ Вы уже участвуете в активной дуэли (или отправили вызов)."
        if self._is_in_active_duel(opponent_id):
            return "❌ Соперник сейчас занят в другой дуэли."

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
                return "❌ Недостаточно средств для ставки."

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
        if not duel: return "❌ Дуэль не найдена."
        
        async with duel.lock:
            if duel.finished: return "❌ Дуэль завершена."
            if duel.accepted: return "✅ Уже идет."
            
            if decision == 'x':
                if user_id in (duel.challenger_id, duel.opponent_id):
                    await self._cancel_duel(duel, "❌ Дуэль отклонена.")
                    return "Отклонено."
                return "❌ Вы не участник."
                
            if decision == 'a':
                if user_id != duel.opponent_id: return "❌ Это не вам."
                
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
        
        return "⚠️ Ошибка."

    async def process_move(self, duel_id: int, user_id: int, move: str) -> str:
        # move is 'hit_l', 'hit_r', 'dodge_l', 'dodge_r'
        duel = self.duels.get(duel_id)
        if not duel: return "❌ Дуэль не найдена."
        
        async with duel.lock:
            if duel.finished: return "❌ Дуэль завершена."
            if user_id not in (duel.challenger_id, duel.opponent_id): return "❌ Не ваш бой."
            
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
        if not duel: return "❌ Дуэль не найдена."

        # 'open' doesn't need lock usually, but safe to have.
        # 'auto' and 'reset' modify state so need lock.
        
        async with duel.lock:
            if duel.finished: return "❌ Дуэль завершена."
            if user_id not in (duel.challenger_id, duel.opponent_id): return "❌ Не ваш бой."

            if action == 'open':
                await self._update_control_dm(duel, user_id)
                return "📩 Панель отправлена в ЛС."

            if action == 'auto':
                actions = duel.actions.setdefault(user_id, {"dodge": None, "attack": None})
                if not actions["dodge"]: actions["dodge"] = random.choice(DODGES)
                if not actions["attack"]: actions["attack"] = random.choice(HITS)
                await self._update_control_dm(duel, user_id)
                return "🤖 Автоход сделан."

            if action == 'reset':
                duel.actions[user_id] = {"dodge": None, "attack": None}
                await self._update_control_dm(duel, user_id)
                return "🔄 Ход сброшен."

            return "❓ Неизвестное действие."

    async def surrender(self, duel_id: int, user_id: int) -> str:
        duel = self.duels.get(duel_id)
        if not duel: return "❌ Нет такой дуэли."
        
        async with duel.lock:
            if duel.finished: return "❌ Уже всё."
            if user_id not in (duel.challenger_id, duel.opponent_id): return "❌ Не вы."
            
            winner_id = duel.opponent_id if user_id == duel.challenger_id else duel.challenger_id
            await self._finish_duel(duel, winner_id, f"🏳️ Игрок {user_id} сдался!")
            return "🏳️ Вы сдались."

    # --- Internal Logic ---

    async def _start_round(self, duel: Duel):
        duel.round_num += 1
        duel.round_deadline_mono = time.monotonic() + DUEL_ROUND_TIMEOUT_SEC
        
        # Reset actions
        duel.actions[duel.challenger_id] = {"dodge": None, "attack": None}
        duel.actions[duel.opponent_id] = {"dodge": None, "attack": None}
        
        duel.log_lines.append(f"🔔 <b>Раунд {duel.round_num}</b>")

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
                duel.log_lines.append("⏰ Время вышло!")
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
        uow = UnitOfWork(self.container.session_factory)
        async with uow:
            ur = UserRepository(uow.session)
            u_ch = await ur.get_by_id(ch)
            u_op = await ur.get_by_id(op)
            name_ch = _name_from_user(u_ch, ch)
            name_op = _name_from_user(u_op, op)

        # Log
        lines = []
        
        # Visual Summary of Move
        # 👤A: 🛡️⬅️ | ⚔️➡️
        def move_icon(d_move, a_move):
            d_arrow = "⬅️" if d_move and "_l" in d_move else "➡️"
            a_arrow = "⬅️" if a_move and "_l" in a_move else "➡️"
            return f"🛡️{d_arrow} ⚔️{a_arrow}"

        lines.append(f"🔴 {name_ch}: {move_icon(ch_acts['dodge'], ch_acts['attack'])}")
        lines.append(f"🔵 {name_op}: {move_icon(op_acts['dodge'], op_acts['attack'])}")

        lines.append(narrate_dodge(name_ch, ch_acts["dodge"]))
        lines.append(narrate_dodge(name_op, op_acts["dodge"]))
        lines.append(narrate_attack(name_ch, ch_acts["attack"]))
        lines.append(narrate_attack(name_op, op_acts["attack"]))
        
        # Outcome Visual
        res_ch = "🩸 ПОПАДАНИЕ!" if ch_hit_success else "💨 ПРОМАХ!"
        res_op = "🩸 ПОПАДАНИЕ!" if op_hit_success else "💨 ПРОМАХ!"
        
        lines.append(f"🔴 Атака {name_ch}: {res_ch}")
        lines.append(f"🔵 Атака {name_op}: {res_op}")

        lines.append(narrate_outcome(name_ch, ch_hit_success))
        lines.append(narrate_outcome(name_op, op_hit_success))
        lines.append(f"📊 Счёт: {duel.hits[ch]} : {duel.hits[op]}")
        
        duel.log_lines.extend(lines)
        
        # Separator for next round in log
        duel.log_lines.append("〰️〰️〰️〰️〰️〰️〰️〰️")
        
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
                duel.log_lines.append("⚖️ Судья закрыл глаза и ткнул случайно пальцем в победителя.")
                
            await self._finish_duel(duel, winner, "🏆 Победа!")
        else:
            await self._start_round(duel)

    # --- Rendering & Updates ---

    async def _update_arena(self, duel: Duel):
        # Build text
        uow = UnitOfWork(self.container.session_factory)
        async with uow:
            ur = UserRepository(uow.session)
            # Fetch fresh just in case, but use cached if available to save DB?
            # Actually we need names.
            if not duel.challenger_name:
                c = await ur.get_by_id(duel.challenger_id)
                duel.challenger_name = _name_from_user(c, duel.challenger_id)
            if not duel.opponent_name:
                o = await ur.get_by_id(duel.opponent_id)
                duel.opponent_name = _name_from_user(o, duel.opponent_id)
            
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
        lines.append(Visuals.frame_line_left(f"🏟️ {duel.arena_name}", w))
        lines.append(Visuals.frame_separator_left(w))
        
        # Player 1
        hp_c = 2 - duel.hits.get(duel.challenger_id, 0)
        hp_c_str = "❤️" * hp_c + "🖤" * (2 - hp_c)
        lines.append(Visuals.frame_line_left(f"🔴 {c_name}", w))
        lines.append(Visuals.frame_line_left(f"HP: {hp_c_str}", w))
        
        # Player 2
        lines.append(Visuals.frame_separator_left(w))
        hp_o = 2 - duel.hits.get(duel.opponent_id, 0)
        hp_o_str = "❤️" * hp_o + "🖤" * (2 - hp_o)
        lines.append(Visuals.frame_line_left(f"🔵 {o_name}", w))
        lines.append(Visuals.frame_line_left(f"HP: {hp_o_str}", w))
        
        lines.append(Visuals.frame_separator_left(w))
        
        # Status / Timer
        if duel.finished:
             lines.append(Visuals.frame_line_left("🏁 ДУЭЛЬ ЗАВЕРШЕНА", w))
        elif not duel.accepted:
             lines.append(Visuals.frame_line_left(f"⏳ Ожидание: {left}с", w))
        else:
             # Progress bar for timer
             bar = Visuals.progress_bar(left, DUEL_ROUND_TIMEOUT_SEC, length=8, style="square")
             lines.append(Visuals.frame_line_left(f"⏳ {bar}", w))
             lines.append(Visuals.frame_line_left(f"Раунд: {duel.round_num} | Ставка: {duel.bet}", w))
             
             # Readiness indicators (compact)
             c_act = duel.actions.get(duel.challenger_id, {})
             o_act = duel.actions.get(duel.opponent_id, {})
             c_ready = "✅" if (c_act.get("dodge") and c_act.get("attack")) else "💭"
             o_ready = "✅" if (o_act.get("dodge") and o_act.get("attack")) else "💭"
             lines.append(Visuals.frame_line_left(f"Статус: 🔴{c_ready} vs 🔵{o_ready}", w))

        lines.append(Visuals.frame_bottom_left(w))
        
        frame_text = "\n".join(lines)
        
        controls_msg = ""
        if duel.accepted and not duel.finished:
            controls_msg = "\n📩 <b>Управление боем — в ЛС с ботом!</b>\n<i>(Нажмите «Управление» если потеряли чат)</i>"

        text = (
            f"<pre>{frame_text}</pre>\n"
            f"<i>{duel.arena_desc}</i>\n"
            f"⚠️ {duel.arena_gag}\n"
            f"{controls_msg}\n"
            f"📜 <b>Хроника:</b>\n"
            f"<pre>{log_view}</pre>"
        )
        
        # Buttons
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📩 Управление",
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
        other_name = duel.opponent_name if user_id == duel.challenger_id else duel.challenger_name
        
        left = max(0, int(duel.round_deadline_mono - time.monotonic()))
        
        text = (
            f"<b>⚔️ Дуэль vs {other_name}</b>\n"
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
                InlineKeyboardButton(text="🛡️ Увернуться влево", callback_data=DuelMoveCb(did=did, mv='dodge_l').pack()),
                InlineKeyboardButton(text="🛡️ Увернуться вправо", callback_data=DuelMoveCb(did=did, mv='dodge_r').pack())
            ],
            [
                InlineKeyboardButton(text="⚔️ Ударить влево", callback_data=DuelMoveCb(did=did, mv='hit_l').pack()),
                InlineKeyboardButton(text="⚔️ Ударить вправо", callback_data=DuelMoveCb(did=did, mv='hit_r').pack())
            ],
            [
                InlineKeyboardButton(text="🤖 Автоход", callback_data=DuelUtilityCb(did=did, act='auto').pack()),
                InlineKeyboardButton(text="🔄 Сброс", callback_data=DuelUtilityCb(did=did, act='reset').pack())
            ],
            [
                InlineKeyboardButton(text="🏳️ Сдаться", callback_data=DuelSurrenderCb(did=did).pack())
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
            uow = UnitOfWork(self.container.session_factory)
            async with uow:
                ur = UserRepository(uow.session)
                tr = TransactionRepository(uow.session)

                winner = await ur.get_for_update(winner_id)
                loser = await ur.get_for_update(loser_id)

                coins_reward = float(duel.bet * 2) if duel.bet > 0 else 0.0

                if winner:
                    winner.wins += 1
                    winner.xp += 50
                    if getattr(winner, "has_katana", False):
                        winner.katana_length = round((winner.katana_length or 0.0) + 0.01, 2)
                    winner_name = _name_from_user(winner, winner_id)
                    duel.log_lines.append(f"✨ {winner_name} получает +50 XP и +0.01 к катане.")

                    if coins_reward > 0:
                        winner.coins += coins_reward
                        duel.log_lines.append(f"💰 Победитель получает {int(coins_reward)} монет!")

                    await tr.create(
                        user_id=winner_id,
                        tx_type=TransactionType.DUEL_WIN,
                        xp_change=50,
                        coins_change=coins_reward,
                        description=f"Победа в дуэли #{duel.id} против {loser_id}",
                    )

                if loser:
                    loser.losses += 1
                    if getattr(loser, "has_katana", False):
                        loser.katana_length = round(max(0.0, (loser.katana_length or 0.0) - 0.01), 2)
                    loser_name = _name_from_user(loser, loser_id)
                    duel.log_lines.append(f"💔 {loser_name} теряет -0.01 от катаны.")

                await uow.commit()
            logger.info(
                "Duel finished: id=%s winner=%s loser=%s bet=%s reason=%s",
                duel.id,
                winner_id,
                loser_id,
                duel.bet,
                reason,
            )

        # Final update
        await self._update_arena(duel)
        
        # Cleanup PMs
        for uid in (duel.challenger_id, duel.opponent_id):
            mid = duel.control_message_ids.get(uid)
            if mid:
                try:
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
            uow = UnitOfWork(self.container.session_factory)
            async with uow:
                ur = UserRepository(uow.session)
                tr = TransactionRepository(uow.session)
                
                c = await ur.get_for_update(duel.challenger_id)
                o = await ur.get_for_update(duel.opponent_id)

                if c:
                    c.coins += float(duel.bet)
                    await tr.create(
                        user_id=duel.challenger_id,
                        tx_type=TransactionType.REFUND,
                        coins_change=float(duel.bet),
                        description=f"Возврат ставки дуэли #{duel.id}",
                    )
                if o:
                    o.coins += float(duel.bet)
                    await tr.create(
                        user_id=duel.opponent_id,
                        tx_type=TransactionType.REFUND,
                        coins_change=float(duel.bet),
                        description=f"Возврат ставки дуэли #{duel.id}",
                    )
                await uow.commit()
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
                await self._cancel_duel(duel, "⏰ Время вышло.")

    async def _check_eligibility(self, cid: int, oid: int, bet: int) -> Optional[str]:
        if cid == oid:
            return "❌ Нельзя вызвать самого себя."
        
        uow = UnitOfWork(self.container.session_factory)
        async with uow:
            ur = UserRepository(uow.session)
            
            challenger = await ur.get_by_id(cid)
            opponent = await ur.get_by_id(oid)
            
            if not opponent:
                return "❌ Соперник не найден в базе."
            if not challenger:
                return "❌ Вы не найдены в базе."
            
            # Note: Cooldown check disabled as get_last_duel_time method doesn't exist
            # TODO: Implement duel cooldown tracking if needed
            
            # Bet checks - allow bet = 0 (no bet duel)
            if bet < 0:
                return "❌ Ставка не может быть отрицательной."
            if bet != 0 and bet < 300:  # Only check minimum if bet > 0
                return "❌ Минимальная ставка — 300 монет."
            
            # Only check balances if there's an actual bet
            if bet > 0:
                if (challenger.coins or 0.0) < bet:
                    return "❌ У вас недостаточно средств для такой ставки."
                if (opponent.coins or 0.0) < bet:
                    return "❌ У соперника недостаточно средств для такой ставки."
        
        return None

    async def _escrow_funds(self, cid: int, oid: int, bet: int) -> bool:
        uow = UnitOfWork(self.container.session_factory)
        async with uow:
            ur = UserRepository(uow.session)
            tr = TransactionRepository(uow.session)

            c = await ur.get_for_update(cid)
            o = await ur.get_for_update(oid)
            if not c or not o:
                logger.info("Escrow failed (user missing): c=%s o=%s", cid, oid)
                return False

            if (c.coins or 0.0) < bet or (o.coins or 0.0) < bet:
                logger.info(
                    "Escrow failed (insufficient): c=%s c_coins=%s o=%s o_coins=%s bet=%s",
                    cid,
                    c.coins,
                    oid,
                    o.coins,
                    bet,
                )
                return False

            c.coins -= float(bet)
            o.coins -= float(bet)

            await tr.create(
                user_id=cid,
                tx_type=TransactionType.DUEL_BET,
                coins_change=-float(bet),
                description=f"Ставка в дуэли против {oid}",
            )
            await tr.create(
                user_id=oid,
                tx_type=TransactionType.DUEL_BET,
                coins_change=-float(bet),
                description=f"Ставка в дуэли против {cid}",
            )

            await uow.commit()
        logger.info("Escrow success: c=%s o=%s bet=%s", cid, oid, bet)
        return True
