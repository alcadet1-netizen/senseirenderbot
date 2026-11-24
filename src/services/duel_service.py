"""
⚔️ Сервис дуэлей (Sensei Duel Logic).
Refactored to use MongoDB directly instead of SQLAlchemy/UnitOfWork.
"""

import asyncio
import random
import time
import logging
import html
import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any, Union

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter

from src.core.container import Container
from src.core.visuals import Visuals
from src.core.constants import LEVEL_XP_REQUIREMENTS
from src.services.duel_escrow import DuelEscrow, DuelRequestAlreadyUsed
from src.services.bank_ledger import _matched
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

    escrow_id: Optional[str] = None
    settlement_started: bool = False
    settlement_winner: Optional[int] = None
    settlement_reason: str = ""
    winner_id: Optional[int] = None
    payout_confirmed: bool = False
    xp_confirmed: bool = False

    # State
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    accepted: bool = False
    finished: bool = False
    round_num: int = 0

    # Logic
    hits: Dict[int, int] = field(default_factory=dict)  # uid -> hits count
    actions: Dict[int, Dict[str, Optional[str]]] = field(default_factory=dict)
    # Structure: {uid: {"dodge": "dodge_l"|None, "attack": "hit_r"|None}}

    inline_arena: Optional[str] = None
    inline_private: bool = False
    dojo_only: bool = False
    connected: set = field(default_factory=set)
    last_exchange: Optional[dict] = None

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

def _name_from_user(user_doc: Optional[dict], fallback_id: int) -> str:
    # user_doc is a MongoDB document (dict) or None
    if not user_doc:
        return str(fallback_id)
    return user_doc.get("username") or user_doc.get("first_name") or str(fallback_id)

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
        self._closing = False
        self._lifecycle_lock = asyncio.Lock()
        self._recovery_task: Optional[asyncio.Task] = None

        # Get references to services we'll need
        self.user_service = container.user_service
        self.economy_service = container.economy_service

        # Get direct database collections for performance
        self.db = container.mongo_client.database
        self.users = self.db.users
        self.transactions = self.db.transactions
        self.escrow = DuelEscrow(container.mongo_client)

    # --- Core Public Methods ---

    async def start_recovery(self):
        """Retry only already-decided settlements; leave active stakes alone."""
        if self._recovery_task is not None or self._closing:
            return
        self._recovery_task = asyncio.create_task(self._recovery_loop(), name='duel-settlement-recovery')

    async def _recovery_loop(self):
        while True:
            try:
                await self.escrow.recover_decided()
                await self._retry_live_settlements()
            except Exception:
                logger.exception('Duel recovery scan failed; will retry')
            await asyncio.sleep(60)

    async def _retry_live_settlements(self):
        for duel in list(self.duels.values()):
            if not duel.settlement_started or duel.finished:
                continue
            async with duel.lock:
                if not duel.settlement_started or duel.finished:
                    continue
                try:
                    await self._finish_duel(duel, duel.settlement_winner, duel.settlement_reason)
                except Exception:
                    logger.exception('Duel live settlement retry failed: duel=%s', duel.id)

    async def shutdown(self):
        """Refund live escrow under each duel lock before the database closes.

        Reuses durable cancellation settlement, without sending through a closing bot
        session or scheduling new archive tasks. Crash recovery is separate.
        """
        async with self._lifecycle_lock:
            self._closing = True
            pending = list(self.duels.values())
        timers, failures = [], []
        if self._recovery_task is not None:
            self._recovery_task.cancel()
            timers.append(self._recovery_task)
            self._recovery_task = None
            await asyncio.gather(*timers, return_exceptions=True)
            timers.clear()
        for duel in pending:
            async with duel.lock:
                timer = duel.timeout_task
                if isinstance(timer, asyncio.Task) and timer is not asyncio.current_task():
                    timer.cancel()
                    timers.append(timer)
                if not duel.finished:
                    try:
                        if duel.settlement_started:
                            await self.escrow.settle(duel.escrow_id, duel.settlement_winner)
                            duel.finished = True
                        else:
                            await self._cancel_duel(duel, 'Бот перезапускается. Ставки возвращены.', notify=False)
                    except Exception as exc:
                        logger.error('Duel shutdown refund failed: duel=%s type=%s', duel.id, type(exc).__name__)
                        failures.append(exc)
        if timers:
            await asyncio.gather(*timers, return_exceptions=True)
        if failures:
            raise ExceptionGroup('Some duel refunds failed during shutdown', failures)

    def _is_in_active_duel(self, user_id: int) -> bool:
        for duel in self.duels.values():
            if not duel.finished and user_id in (duel.challenger_id, duel.opponent_id):
                return True
        return False

    async def _duel_rejection_after_receipt_check(self, escrow_id, fallback):
        """Prefer a confirmed request receipt over an outdated rejection."""
        try:
            if await self.escrow.escrows.find_one({'_id': escrow_id}):
                return '❜ Этот вызов уже обработан. Повторного списания нет.'
        except Exception:
            logger.exception('Could not recheck duel request after rejection: escrow=%s', escrow_id)
            return f'⚠️ Не удалось проверить вызов. Не повторяйте до проверки. ID: {escrow_id}'
        return fallback

    async def create_duel(self, challenger_id: int, opponent_id: int, bet: int, chat_id: int, bot: Bot, *, request_id: Optional[str] = None) -> Union[Duel, str]:
        # Let an in-flight escrow finish registration before shutdown snapshots it.
        async with self._lifecycle_lock:
            return await self._create_duel(challenger_id, opponent_id, bet, chat_id, bot, request_id=request_id)

    async def _create_duel(self, challenger_id: int, opponent_id: int, bet: int, chat_id: int, bot: Bot, *, request_id: Optional[str] = None) -> Union[Duel, str]:
        if self._closing:
            return "Бот перезапускается. Новые дуэли временно недоступны."
        logger.info("Create duel: challenger=%s opponent=%s bet=%s chat=%s", challenger_id, opponent_id, bet, chat_id)
        if request_id is not None and (not isinstance(request_id, str) or not 1 <= len(request_id) <= 256):
            return '❜ Некорректный идентификатор вызова.'
        # The message key is stable across delivery retries and independent
        # of the process-local short duel number.
        escrow_id = ('duel:' + hashlib.sha256(request_id.encode()).hexdigest()
                     if bet > 0 and request_id else uuid.uuid4().hex if bet > 0 else None)
        if bet > 0 and request_id:
            try:
                previous = await self.escrow.escrows.find_one({'_id': escrow_id})
            except Exception:
                logger.exception('Could not check duel request: escrow=%s', escrow_id)
                return f'⚠️ Не удалось проверить вызов. Не повторяйте до проверки. ID: {escrow_id}'
            if previous:
                return '❜ Этот вызов уже обработан. Повторного списания нет.'
        # 0. Check busy
        if self._is_in_active_duel(challenger_id):
            return "❜ Вы уже участвуете в активной дуэли (или отправили вызов)."
        if self._is_in_active_duel(opponent_id):
            return "❜ Соперник сейчас занят в другой дуэли."

        # 1. Check eligibility
        error = await self._check_eligibility(challenger_id, opponent_id, bet)
        if error:
            if bet > 0 and request_id:
                return await self._duel_rejection_after_receipt_check(escrow_id, error)
            return error

        # Generate the durable key before any money moves; it is independent
        # of the short display ID, which can repeat after a restart.
        did = _pick_duel_id(set(self.duels.keys()))
        aname, adesc, agag = pick_arena()
        # 2. Escrow
        if bet > 0:
            try:
                reserved = await self._escrow_funds(challenger_id, opponent_id, bet, escrow_id, did,
                                                    reject_existing=bool(request_id))
            except DuelRequestAlreadyUsed:
                return '❜ Этот вызов уже обработан. Повторного списания нет.'
            except Exception:
                logger.exception('Duel stake outcome unconfirmed: escrow=%s', escrow_id)
                return f'⚠️ Ставки не подтверждены. Не создавайте повторную дуэль до проверки. ID: {escrow_id}'
            if not reserved:
                logger.info(
                    "Create duel failed (insufficient funds): challenger=%s opponent=%s bet=%s",
                    challenger_id,
                    opponent_id,
                    bet,
                )
                rejection = "❜ Недостаточно средств для ставки."
                if request_id:
                    return await self._duel_rejection_after_receipt_check(escrow_id, rejection)
                return rejection

        # 3. Create
        duel = Duel(
            id=did,
            challenger_id=challenger_id,
            opponent_id=opponent_id,
            bet=bet,
            chat_id=chat_id,
            bot=bot,
            container=self.container,
            escrow_id=escrow_id,
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
            if duel.settlement_started: return "⏳ Результат дуэли подтверждается."
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
                if duel.challenge_message_id:
                    try:
                        await duel.bot.edit_message_reply_markup(chat_id=duel.chat_id, message_id=duel.challenge_message_id, reply_markup=None)
                    except TelegramRetryAfter as e:
                        logger.warning(f"Duel {duel.id}: Hit flood control on accept markup cleanup, waiting {e.retry_after} seconds")
                        await asyncio.sleep(e.retry_after)
                        # Retry once after waiting
                        await duel.bot.edit_message_reply_markup(chat_id=duel.chat_id, message_id=duel.challenge_message_id, reply_markup=None)
                    except TelegramBadRequest as e:
                        logger.warning("Duel %s: accept markup cleanup failed: %s", duel.id, e)
                    except Exception:
                        logger.exception("Duel %s: accept markup cleanup failed critically", duel.id)

                # Start
                if duel.dojo_only:
                    duel.round_deadline_mono = time.monotonic() + 120
                    duel.timeout_task = asyncio.create_task(self._await_dojo_players(duel))
                    return "Принято! Открой /dojo → VS."
                asyncio.create_task(self._start_round(duel))
                return "✅ Принято! Смотрите ЛС."

        return "⚠️ Ошибка."

    async def commit_dojo_move(self, duel_id, uid, round_num, attack, dodge):
        """Publish both secret choices together, never half a move."""
        duel = self.duels.get(duel_id)
        if not duel or not duel.dojo_only or uid not in (duel.challenger_id, duel.opponent_id):
            return 'Это не твой бой.'
        if attack not in HITS or dodge not in DODGES:
            return 'Выбери направление удара и уворота.'
        async with duel.lock:
            if (not duel.accepted or duel.finished or duel.settlement_started or not round_num
                    or duel.round_num != round_num or time.monotonic() >= duel.round_deadline_mono):
                return 'Раунд уже завершён.'
            previous = duel.actions.get(uid, {})
            pair = {'attack': attack, 'dodge': dodge}
            if previous.get('attack') and previous.get('dodge') and previous != pair:
                return 'Ход уже зафиксирован.'
            duel.actions[uid] = pair
            return 'Принято.'

    async def process_move(self, duel_id: int, user_id: int, move: str, *, expected_round=None) -> str:
        # move is 'hit_l', 'hit_r', 'dodge_l', 'dodge_r'
        duel = self.duels.get(duel_id)
        if not duel: return "❜ Дуэль не найдена."

        async with duel.lock:
            if duel.finished: return "❜ Дуэль завершена."
            if duel.settlement_started: return "⏳ Результат дуэли подтверждается."
            if user_id not in (duel.challenger_id, duel.opponent_id): return "❜ Не ваш бой."

            if duel.dojo_only and expected_round is None: return "Управление только в /dojo → VS."
            if duel.dojo_only and all(duel.actions.get(user_id, {}).get(k) for k in ('attack', 'dodge')):
                return "Ход уже зафиксирован."
            if expected_round is not None and (not duel.accepted or not duel.round_num or duel.round_num != expected_round or time.monotonic() >= duel.round_deadline_mono):
                return "Раунд уже сменился."

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

        if duel.dojo_only: return "Управление только в /dojo → VS."
        async with duel.lock:
            if duel.finished: return "❜ Дуэль завершена."
            if duel.settlement_started: return "⏳ Результат дуэли подтверждается."
            if user_id not in (duel.challenger_id, duel.opponent_id): return "❜ Не ваш бой."

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
        if not duel: return "❜ Нет такой дуэли."

        if duel.dojo_only: return "Управление только в /dojo → VS."
        async with duel.lock:
            if duel.finished: return "❜ Уже всё."
            if duel.settlement_started: return "⏳ Результат дуэли подтверждается."
            if user_id not in (duel.challenger_id, duel.opponent_id): return "❜ Не вы."

            winner_id = duel.opponent_id if user_id == duel.challenger_id else duel.challenger_id
            await self._finish_duel(duel, winner_id, f"🏳️ Игрок {user_id} сдался!")
            return "🏳️ Вы сдались."

    # --- Internal Logic ---

    async def _await_dojo_players(self, duel):
        await self._update_arena(duel)
        while not self._closing:
            async with duel.lock:
                if duel.finished or duel.settlement_started:
                    return
                if len(duel.connected) == 2:
                    await self._start_round(duel)
                    return
                if time.monotonic() >= duel.round_deadline_mono:
                    await self._finish_duel(duel, None, 'Подключение не состоялось. Ставки возвращаются.')
                    return
            await asyncio.sleep(1)

    async def _start_round(self, duel: Duel):
        if self._closing or duel.finished or duel.settlement_started:
            return
        duel.round_num += 1
        duel.round_deadline_mono = time.monotonic() + (120 if duel.dojo_only else DUEL_ROUND_TIMEOUT_SEC)

        # Reset actions
        duel.actions[duel.challenger_id] = {"dodge": None, "attack": None}
        duel.actions[duel.opponent_id] = {"dodge": None, "attack": None}

        duel.log_lines.append(f"🔔 Раунд {duel.round_num}")

        await self._update_arena(duel)
        await self._update_control_dm(duel, duel.challenger_id)
        await self._update_control_dm(duel, duel.opponent_id)

        if not self._closing and not duel.finished:
            duel.timeout_task = asyncio.create_task(self._wait_for_round(duel.id, duel.round_num))

    async def _wait_for_round(self, duel_id: int, round_num: int):
        current = self.duels.get(duel_id)
        if current and current.dojo_only:
            while not self._closing:
                async with current.lock:
                    if current.finished or current.settlement_started or current.round_num != round_num:
                        return
                    if self._all_ready(current):
                        await self._resolve_round(current)
                        return
                    if time.monotonic() >= current.round_deadline_mono:
                        await self._finish_duel(current, None, 'Не все действия выбраны. Бой отменён без автохода.')
                        return
                await asyncio.sleep(.25)
            return
        # Tick every second to update timer in arena
        everyone_ready = False

        timed_out = True
        for _ in range(int(DUEL_ROUND_TIMEOUT_SEC)):
            if self.duels.get(duel_id) is None: return
            await asyncio.sleep(1)
            duel = self.duels.get(duel_id)
            if not duel or duel.finished or duel.settlement_started or duel.round_num != round_num: return

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
        if not duel or duel.finished or duel.settlement_started or duel.round_num != round_num: return

        async with duel.lock:
            if duel.finished or duel.settlement_started or duel.round_num != round_num:
                return
            # Auto-fill missing
            for uid in (duel.challenger_id, duel.opponent_id):
                acts = duel.actions[uid]
                if not acts["dodge"]: acts["dodge"] = random.choice(DODGES)
                if not acts["attack"]: acts["attack"] = random.choice(HITS)

            if timed_out:
                duel.log_lines.append("⏰ Время вышло!")
            try:
                await self._resolve_round(duel)
            except Exception:
                logger.exception('Duel round resolution failed: duel=%s', duel.id)

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

        # Only resolved moves are public. Keep a snapshot across the next
        # round reset so Mini App polling cannot lose the final exchange.
        duel.last_exchange = {'round': duel.round_num, 'strikes': [
            {'attack': acts['attack'], 'dodge': target['dodge'], 'hit': success}
            for acts, target, success in ((ch_acts, op_acts, ch_hit_success),
                                           (op_acts, ch_acts, op_hit_success))]}

        # Names
        u_ch_doc = await self.users.find_one({"id": ch})
        u_op_doc = await self.users.find_one({"id": op})
        name_ch = _name_from_user(u_ch_doc, ch)
        name_op = _name_from_user(u_op_doc, op)

        # Log
        lines = []

        # Visual Summary of Move
        #  👤A:  🛡️⬅️ |  ⚔️➡️
        def move_icon(d_move, a_move):
            d_arrow = "⬅️" if d_move and "_l" in d_move else "➡️"
            a_arrow = "⬅️" if a_move and "_l" in a_move else "➡️"
            return f"🛡️{d_arrow}  ⚔️{a_arrow}"

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
            ch_hits = duel.hits.get(duel.challenger_id, 0)
            op_hits = duel.hits.get(duel.opponent_id, 0)
            result_lines = ["🏁 ДУЭЛЬ ЗАВЕРШЕНА"]
            if duel.winner_id in (duel.challenger_id, duel.opponent_id):
                winner_name = c_name if duel.winner_id == duel.challenger_id else o_name
                result_lines.append(f"Победитель: @{winner_name}")
                result_lines.append(f"Счёт: {ch_hits} : {op_hits}")
                if duel.xp_confirmed:
                    result_lines.append("Награда победителю: +50 XP")
                else:
                    result_lines.append("Начисление XP не подтверждено.")
                if duel.bet > 0 and duel.payout_confirmed:
                    result_lines.append(f"Возврат ставки и выигрыш: +{duel.bet * 2} монет")
                elif duel.bet > 0:
                    result_lines.append("Выплата ставки не подтверждена.")
            else:
                result_lines.append("Победитель не определён.")
                result_lines.append(f"Счёт: {ch_hits} : {op_hits}")
                if duel.bet > 0 and duel.payout_confirmed:
                    result_lines.append("Ставки возвращены игрокам.")
            if duel.dojo_only:
                result_lines.extend(line for line in duel.log_lines if line.startswith(("🔔", "🩸", "🔴 Атака", "🔵 Атака", "📊", "Подключение", "Не все действия")))
            log_view = "\n".join(result_lines)
        elif duel.settlement_started:
            log_view = "⏳ Результат дуэли подтверждается. Выплата пока не подтверждена."
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
        elif duel.settlement_started:
             lines.append(Visuals.frame_line_left("⏳ ПРОВЕРКА РЕЗУЛЬТАТА", w))
        elif not duel.accepted:
             lines.append(Visuals.frame_line_left(f"⏳ Ожидание: {left}с", w))
        else:
             # Progress bar for timer
             bar = Visuals.progress_bar(left, 120 if duel.dojo_only else DUEL_ROUND_TIMEOUT_SEC, length=8, style="square")
             lines.append(Visuals.frame_line_left(f"⏳ {bar}", w))
             lines.append(Visuals.frame_line_left(f"Раунд: {duel.round_num} | Ставка: {duel.bet}", w))

             # Readiness indicators (compact)
             c_act = duel.actions.get(duel.challenger_id, {})
             o_act = duel.actions.get(duel.opponent_id, {})
             c_ready = "✅" if (c_act.get("dodge") and c_act.get("attack")) else "💭"
             o_ready = "✅" if (o_act.get("dodge") and o_act.get("attack")) else "💭"
             lines.append(Visuals.frame_line_left(f"Статус:  🔴{c_ready} vs  🔵{o_ready}", w))

        lines.append(Visuals.frame_bottom_left(w))

        frame_text = "\n".join(lines)

        controls_msg = ""
        if duel.accepted and not duel.finished and not duel.settlement_started:
            controls_msg = "\n📩 <b>Управление боем — в ЛС с ботом!</b>\n<i>(Нажмите «Управление» если потеряли чат)</i>"

        if duel.dojo_only and not duel.finished:
            controls_msg = "Открой /dojo → VS. " + ("Ожидаем подключения обоих игроков (2 минуты)." if not duel.round_num else "Выбери уворот и удар.")
        text = (
            f"<pre>{html.escape(frame_text)}</pre>\n"
            f"<i>{html.escape(duel.arena_desc)}</i>\n"
            f"⚠️ {html.escape(duel.arena_gag)}\n"
            f"{controls_msg}\n"
            f"📜 <b>Хроника:</b>\n"
            f"<pre>{html.escape(log_view)}</pre>"
        )

        # Buttons
        kb = None if duel.dojo_only or duel.finished or duel.settlement_started else InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📩 Управление",
                                  callback_data=DuelUtilityCb(id=duel.id, u=0, a='open').pack())]
        ])

        try:
            if duel.inline_arena:
                await duel.bot.edit_message_text(inline_message_id=duel.inline_arena, text=text, parse_mode="HTML")
            elif not duel.arena_message_id:
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
        except TelegramRetryAfter as e:
            logger.warning(f"Duel {duel.id}: Hit flood control on arena update, waiting {e.retry_after} seconds")
            await asyncio.sleep(e.retry_after)
            # Retry once after waiting
            if duel.inline_arena:
                await duel.bot.edit_message_text(inline_message_id=duel.inline_arena, text=text, parse_mode="HTML")
            elif not duel.arena_message_id:
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
        if duel.dojo_only: return
        # Build text
        actions = duel.actions.get(user_id, {})

        # Opponent name
        other_id = duel.opponent_id if user_id == duel.challenger_id else duel.challenger_id
        other_doc = await self.users.find_one({"id": other_id})
        other_name = _name_from_user(other_doc, other_id)

        left = max(0, int(duel.round_deadline_mono - time.monotonic()))

        text = (
            f"<b>⚔️ Дуэль vs {html.escape(other_name)}</b>\n"
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
                InlineKeyboardButton(text="🛡️ Увернуться влево", callback_data=DuelMoveCb(id=did, u=user_id, m='dodge_l').pack()),
                InlineKeyboardButton(text="🛡️ Увернуться вправо", callback_data=DuelMoveCb(id=did, u=user_id, m='dodge_r').pack())
            ],
            [
                InlineKeyboardButton(text="⚔️ Ударить влево", callback_data=DuelMoveCb(id=did, u=user_id, m='hit_l').pack()),
                InlineKeyboardButton(text="⚔️ Ударить вправо", callback_data=DuelMoveCb(id=did, u=user_id, m='hit_r').pack())
            ],
            [
                InlineKeyboardButton(text="🤖 Автоход", callback_data=DuelUtilityCb(id=did, u=user_id, a='auto').pack()),
                InlineKeyboardButton(text="🔄 Сброс", callback_data=DuelUtilityCb(id=did, u=user_id, a='reset').pack())
            ],
            [
                InlineKeyboardButton(text="🏳️ Сдаться", callback_data=DuelSurrenderCb(id=did, u=user_id).pack())
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
        except TelegramRetryAfter as e:
            logger.warning(f"Duel {duel.id}: Hit flood control on control DM update for user {user_id}, waiting {e.retry_after} seconds")
            await asyncio.sleep(e.retry_after)
            # Retry once after waiting
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
            # This method can run while the duel lock is held by a move or
            # utility callback. Re-entering surrender synchronously deadlocks.
            # Let the callback release the lock before resolving the forfeit.
            asyncio.create_task(self._forfeit_after_block(duel.id, user_id))
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e):
                logger.warning(f"Duel {duel.id}: Control update for {user_id} failed: {e}")
                # Fall back to sending a new message
                msg = await duel.bot.send_message(user_id, text, reply_markup=kb, parse_mode="HTML")
                duel.control_message_ids[user_id] = msg.message_id
            else:
                # message not modified, ignore
                pass
        except Exception as e:
            logger.exception(f"Duel {duel.id}: Control update for {user_id} failed critically")

    async def _forfeit_after_block(self, duel_id: int, user_id: int):
        try:
            await self.surrender(duel_id, user_id)
        except Exception:
            logger.exception('Duel forfeit after blocked DM failed: duel=%s user=%s', duel_id, user_id)

    async def _finish_duel(self, duel: Duel, winner_id: Optional[int], reason: str):
        if duel.finished: return
        if getattr(duel, 'room_token', None):
            # Комната — обычная запись в списке; после боя её надо снять,
            # иначе она висит «открытой» и в неё пробуют войти.
            try:
                await self.container.dojo_rooms.sync_result(duel.room_token, duel.id, True)
            except Exception:
                logger.debug('Room close after duel %s failed', duel.id)
        settlement = None
        if duel.bet > 0:
            if duel.settlement_started and duel.settlement_winner != winner_id:
                raise RuntimeError('Duel outcome already decided')
            if not duel.settlement_started:
                duel.settlement_reason = reason
            duel.settlement_started = True
            duel.settlement_winner = winner_id
            try:
                settlement = await self.escrow.settle(duel.escrow_id, winner_id)
                duel.payout_confirmed = True
                duel.xp_confirmed = bool(winner_id is not None and settlement.get('award_version') == 1)
            except Exception:
                logger.exception('Duel payout unconfirmed: duel=%s escrow=%s', duel.id, duel.escrow_id)
                if duel.timeout_task and duel.timeout_task is not asyncio.current_task():
                    duel.timeout_task.cancel()
                try:
                    await self._update_arena(duel)
                except Exception:
                    logger.exception('Failed to show pending duel result: duel=%s', duel.id)
                raise
        duel.winner_id = winner_id
        duel.finished = True

        if duel.timeout_task and duel.timeout_task is not asyncio.current_task():
            duel.timeout_task.cancel()

        loser_id = None
        if winner_id:
            loser_id = duel.opponent_id if winner_id == duel.challenger_id else duel.challenger_id

        duel.log_lines.append(reason)

        # Staked duels now apply XP, stats and katana in escrow settlement.
        # Zero-stake duels retain the existing independent reward path.
        if duel.bet > 0 and winner_id:
            details = settlement.get('result_details') or {}
            winner_name = details.get('winner_name', str(winner_id))
            loser_name = details.get('loser_name', str(loser_id))
            if duel.xp_confirmed and details.get('winner_has_katana'):
                duel.log_lines.append(f"✨ {winner_name} получает +50 XP и +0.01 к катане.")
            elif duel.xp_confirmed:
                duel.log_lines.append(f"✨ {winner_name} получает +50 XP.")
            else:
                duel.log_lines.append('⚠️ Начисление XP не подтверждено.')
            duel.log_lines.append(f"💰 Победитель получает {int(duel.bet * 2)} монет!")
            if details.get('loser_has_katana'):
                duel.log_lines.append(f"💔 {loser_name} теряет -0.01 от катаны.")
            else:
                duel.log_lines.append(f"💔 {loser_name} не имеет катаны для потери.")

        try:
            if not duel.bet and winner_id and loser_id:
                # Get fresh user documents
                winner_doc = await self.users.find_one({"id": winner_id})
                loser_doc = await self.users.find_one({"id": loser_id})

                if winner_doc and loser_doc:
                    coins_reward = float(duel.bet * 2) if duel.bet > 0 else 0.0

                    # Update winner wins and xp using $inc (no document fetch needed for these)
                    xp_update = await self.users.update_one(
                        {"id": winner_id},
                        {"$inc": {"wins": 1, "xp": 50}}
                    )
                    duel.xp_confirmed = _matched(xp_update)
                    if not duel.xp_confirmed:
                        raise RuntimeError('Duel winner XP update missed')

                    # Fetch winner document for katana-related updates and name
                    winner_doc = await self.users.find_one({"id": winner_id})
                    if winner_doc:
                        winner_name = _name_from_user(winner_doc, winner_id)
                        # Update katana length if winner has one
                        if winner_doc.get("has_katana", False):
                            new_katana_length = round((winner_doc.get("katana_length", 0.0) or 0.0) + 0.01, 2)
                            await self.users.update_one(
                                {"id": winner_id},
                                {"$set": {"katana_length": new_katana_length}}
                            )
                            duel.log_lines.append(f"✨ {winner_name} получает +50 XP и +0.01 к катане.")
                        else:
                            duel.log_lines.append(f"✨ {winner_name} получает +50 XP.")
                    else:
                        logger.warning(f"Winner document not found for user {winner_id} in duel {duel.id}. Awarded XP/wins but skipped katana update and name lookup.")
                        duel.log_lines.append(f"✨ Пользователь {winner_id} получает +50 XP (документ не найден).")

                    if coins_reward > 0:
                        duel.log_lines.append(f"💰 Победитель получает {int(coins_reward)} монет!")

                        # The bet payout is credited exactly once below from the
                        # escrow.  This record is the XP/win journal only; an
                        # extra $inc here minted a second copy of every bet.
                        tx_doc = {
                            "user_id": winner_id,
                            "tx_type": "duel_win",
                            "coins_change": 0.0,
                            "xp_change": 50,
                            "description": f"Победа в дуэли #{duel.id} против {loser_id}",
                            "created_at": datetime.now(timezone.utc),
                        }
                        await self.transactions.insert_one(tx_doc)

                    # Update loser losses using $inc (no document fetch needed for this)
                    await self.users.update_one(
                        {"id": loser_id},
                        {"$inc": {"losses": 1}}
                    )

                    # Fetch loser document for katana-related updates and name
                    loser_doc = await self.users.find_one({"id": loser_id})
                    if loser_doc:
                        loser_name = _name_from_user(loser_doc, loser_id)
                        # Update katana length if loser has one
                        if loser_doc.get("has_katana", False):
                            new_katana_length = round(max(0.0, (loser_doc.get("katana_length", 0.0) or 0.0) - 0.01), 2)
                            await self.users.update_one(
                                {"id": loser_id},
                                {"$set": {"katana_length": new_katana_length}}
                            )
                            duel.log_lines.append(f"💔 {loser_name} теряет -0.01 от катаны.")
                        else:
                            duel.log_lines.append(f"💔 {loser_name} не имеет катаны для потери.")
                    else:
                        logger.warning(f"Loser document not found for user {loser_id} in duel {duel.id}. Awarded loss but skipped katana update and name lookup.")
                        duel.log_lines.append(f"💔 Пользователь {loser_id} терпит поражение (документ не найден).")

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
        except Exception as e:
            logger.exception(f"Duel {duel.id}: Error during _finish_duel processing: {e}")

        # Final update
        try:
            await self._update_arena(duel)
        except Exception as e:
            logger.exception(f"Duel {duel.id}: Failed to update arena after finish: {e}")

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
                        text=f"Дуэль #{duel.id} завершена.\n" + html.escape("\n".join(duel.log_lines[-5:])),
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

    async def _cancel_duel(self, duel: Duel, reason: str, *, notify: bool = True):
        if duel.finished: return
        if duel.bet > 0:
            await self.escrow.settle(duel.escrow_id, None)
        duel.finished = True
        if duel.timeout_task and duel.timeout_task is not asyncio.current_task():
            duel.timeout_task.cancel()

        if not notify:
            return

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
        if bet < 300:
            return "❜ Минимальная ставка — 300 монет."

        # Only check balances if there's an actual bet
        if bet > 0:
            if (challenger_doc.get("coins", 0.0) < bet):
                return "❜ У вас недостаточно средств для такой ставки."
            if (opponent_doc.get("coins", 0.0) < bet):
                return "❜ У соперника недостаточно средств для такой ставки."

        return None

    async def _escrow_funds(self, cid: int, oid: int, bet: int, escrow_id: str, duel_id: int, *, reject_existing=False) -> bool:
        return await self.escrow.reserve(escrow_id, cid, oid, bet, duel_id, reject_existing=reject_existing)
