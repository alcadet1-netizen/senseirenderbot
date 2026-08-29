"""
👹 Сервис для битв с боссами.
"""

import json
import logging
import os
import random
import time
import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any, Union

from src.core.config import settings
from src.core.constants import (
    BOSS_COOLDOWN_MINUTES,
    BOSS_ULT_COOLDOWN_HOURS,
    BOSS_ULT_REQUIRED_HITS,
    BOSSES,
)
from src.infra.mongo.client import MongoClient

logger = logging.getLogger(__name__)

BOSS_INTROS = (
    "Ты слышишь шаги в темноте...",
    "Арена дрожит. Кто-то смотрит на тебя.",
    "Ого, он большой. Ты маленький. Математика не в твою пользу.",
    "Помню этого парня. Он был меньше. И добрее. И живее.",
    "Босс выглядит злым. Может, ему просто нужны друзья?",
    "У него катана больше тебя. Это нормально. Нет, не нормально.",
    "Я читал о нём в легендах. Там не упоминали этот запах.",
    "Он смотрит на тебя как на закуску. Потому что ты — закуска.",
    "Босс не моргает. Уже пять минут. Это странно.",
    "Вижу у него шрамы. Значит, его можно ранить! Теоретически.",
    "Его аура... мощная. Или это у меня давление.",
    "Бей его в слабое место! Какое? Узнаешь. Если выживешь.",
    "У каждого босса есть паттерн. Найди его. Желательно до смерти.",
    "Главное — не паникуй. Я уже паникую за двоих.",
    "Уворачивайся от красных атак. Или синих. Я дальтоник.",
    "Когда он замахивается — беги. Куда? Неважно. Просто беги.",
    "Следи за его левой рукой. Или правой. Или за обеими. Удачи.",
    "Атакуй, когда он открыт! Он никогда не открыт? Импровизируй.",
    "Держи дистанцию! Но не слишком. Но и не близко. Ты понял.",
    "Босс телеграфирует удары. Азбукой Морзе. Ты ведь знаешь азбуку?",
    "Просто делай то, что я делал в молодости. Что именно? Выживал.",
    "Отличное уклонение! В смысле, босс отлично уклонился.",
    "Ты попал! В воздух рядом с ним. Почти!",
    "Он потерял 1% здоровья! Осталось... ой.",
    "Продолжай! Ещё 459 таких ударов — и он упадёт!",
    "Босс злится. Это хорошо! Нет, это плохо. Очень плохо.",
    "Я вижу, ты выбрал тактику 'получать урон лицом'. Смело.",
    "Твоя катана касается его! О, это он касается тебя. Мечом.",
    "Фаза два! Это плохо. Есть фаза три? Не хочу знать.",
    "Он заряжает ульту! Прячься! Куда? Хороший вопрос!",
    "Ты танцуешь с боссом. Он ведёт. Ты летишь в стену.",
    "Говорят, он убивает взглядом. Проверять не будем.",
    "Его катана из метеорита. Твоя — из магазина.",
    "Он победил тысячу воинов. Ты будешь тысяча первым! В списке жертв.",
    "Босс тренируется сто лет. Ты — сто секунд. Почти одинаково.",
    "Его удар сносит горы. Ты даже не гора.",
    "Легенды говорят, он не спит. Потому что ему не нужно.",
    "Он сразил моего сенсея. И его сенсея. И сенсея его сенсея.",
    "У босса нет слабостей. Кроме одной. Какой? Ищу уже сорок лет.",
    "Его броня из драконьей чешуи. Твоя — из надежды.",
    "Он называет себя богом. После этого боя поймёшь почему.",
    "Ты справишься! Это не ложь. Это... оптимизм.",
    "Я бы помог, но... нет, не буду врать. Не хочу.",
    "Верю в тебя! Поставил на тебя три монетки. Зря, наверное.",
    "Это хороший босс. Для него. Не для тебя.",
    "Ты почти попал! Если бы целился на два метра левее.",
    "Технически ты ещё жив. Технически.",
    "Босс не такой страшный. Шучу. Он хуже.",
    "Я видел, как ты сражаешься. Босс тоже видел. Он рад.",
    "Это не поражение — это урок. Дорогой урок. Кровавый урок.",
    "Ты делаешь прогресс! Он всё ещё убивает тебя, но медленнее.",
    "У босса болит колено. Слух. Не проверял.",
    "Говорят, он боится щекотки. Попробуй. Нет, не пробуй.",
    "Его слабость — самоуверенность. И огромный меч. Меч — не слабость.",
    "Атакуй после его комбо! Какой комбо? Двадцатиударный.",
    "Вроде он хромает. Нет, это походка. Грозная походка.",
    "Слышал, он плохо видит слева. Или справа. Или это другой босс.",
    "Найди его ахиллесову пяту! У него есть пята? Не уверен.",
    "Босс устаёт после ульты! На полсекунды. Успеешь?",
    "Он открывается после рывка. Потом закрывается. Навсегда. Для тебя.",
    "Критическое место — голова. Достать её — проблема.",
    "Запах пороха и пота. Бой начинается.",
    "Сенсей молчит. Босс улыбается.",
    "Ставки сделаны. Катаны наголо.",
)


@dataclass
class BossAttackResult:
    state: dict | None
    result_type: str  # "hit", "killed", "expired", "dead", "evaded"
    actual_damage: int
    event: str | None = None  # "hp_50" etc.
    is_dodge: bool = False
    combo_count: int = 0
    is_weakness: bool = False
    is_crit: bool = False


class BossService:
    """Сервис управления боссами."""

    def __init__(self, mongo_client: MongoClient):
        self.mongo_client = mongo_client
        self.db = mongo_client.database
        # Collections
        self.boss_state = self.db.boss_state  # Stores a single document for the current boss state
        self.boss_ult_cooldowns = self.db.boss_ult_cooldowns  # Stores user ult cooldowns
        self.boss_settings = self.db.boss_settings  # Stores reward settings
        # For locking, we'll use a simple asyncio.Lock assuming single instance.
        # If multiple instances are needed, we should implement a distributed lock via MongoDB.
        self._lock = asyncio.Lock()

        # Defaults
        self.DEFAULT_DROP_CHANCE = 0.05
        self.DEFAULT_REWARD_MIN = 0.006
        self.DEFAULT_REWARD_MAX = 0.02
        self.DEFAULT_POOL_LIMIT = 1.0  # GRAM

        # Ensure indexes
        asyncio.create_task(self._ensure_indexes())

    async def _ensure_indexes(self):
        """Ensure necessary indexes exist."""
        try:
            # Ult cooldowns: index on user_id for fast lookup
            await self.boss_ult_cooldowns.create_index("user_id")
            # Boss state: we expect only one document, no index needed
            # Boss settings: expect one document
        except Exception as e:
            logger.warning(f"Failed to ensure indexes: {e}")

    # --- Helper methods to load/save state ---

    async def _get_boss_state_doc(self) -> Optional[Dict]:
        """Fetch the boss state document."""
        return await self.boss_state.find_one()

    async def _save_boss_state_doc(self, state: Dict):
        """Save the boss state document (upsert)."""
        await self.boss_state.update_one(
            {},
            {"$set": state},
            upsert=True
        )

    async def _get_settings_doc(self) -> Dict:
        """Fetch the settings document, providing defaults if missing."""
        doc = await self.boss_settings.find_one()
        if not doc:
            # Insert default settings
            default_doc = {
                "drop_chance": self.DEFAULT_DROP_CHANCE,
                "reward_min": self.DEFAULT_REWARD_MIN,
                "reward_max": self.DEFAULT_REWARD_MAX,
                "pool_limit": self.DEFAULT_POOL_LIMIT,
                "pool_used": 0.0
            }
            await self.boss_settings.insert_one(default_doc)
            return default_doc
        return doc

    async def _save_settings_doc(self, settings_dict: Dict):
        """Save the settings document (upsert)."""
        await self.boss_settings.update_one(
            {},
            {"$set": settings_dict},
            upsert=True
        )

    # --- Public API ---

    async def get_reward_settings(self) -> dict:
        """Получить настройки наград."""
        doc = await self._get_settings_doc()
        return {
            "drop_chance": float(doc.get("drop_chance", self.DEFAULT_DROP_CHANCE)),
            "reward_min": float(doc.get("reward_min", self.DEFAULT_REWARD_MIN)),
            "reward_max": float(doc.get("reward_max", self.DEFAULT_REWARD_MAX)),
            "pool_limit": float(doc.get("pool_limit", self.DEFAULT_POOL_LIMIT)),
            "pool_used": float(doc.get("pool_used", 0.0))
        }

    async def update_setting(self, key: str, value: float):
        """Обновить настройку."""
        await self.boss_settings.update_one(
            {},
            {"$set": {key: value}}
        )

    async def check_pool_availability(self, amount: float) -> bool:
        """Проверить, достаточно ли средств в пуле."""
        settings = await self.get_reward_settings()
        return settings["pool_used"] + amount <= settings["pool_limit"]

    async def increment_pool_used(self, amount: float):
        """Увеличить счетчик использованного пула."""
        await self.boss_settings.update_one(
            {},
            {"$inc": {"pool_used": amount}}
        )

    async def reset_pool(self):
        """Сбросить счетчик пула."""
        await self.boss_settings.update_one(
            {},
            {"$set": {"pool_used": 0.0}}
        )

    async def get_state(self) -> dict | None:
        """Получить текущее состояние битвы."""
        return await self._get_boss_state_doc()

    async def save_state(self, state: dict):
        """Сохранить состояние."""
        await self._save_boss_state_doc(state)

    async def start_boss(
        self,
        boss_id: str,
        duration_hours: float | None = None,
        reward_settings: dict | None = None,
    ) -> dict:
        """Запустить нового босса."""
        if boss_id not in BOSSES:
            raise ValueError(f"Unknown boss: {boss_id}")

        if reward_settings:
            await self.boss_settings.update_one(
                {},
                {"$set": {
                    "drop_chance": reward_settings.get("drop_chance", self.DEFAULT_DROP_CHANCE),
                    "reward_min": reward_settings.get("reward_min", self.DEFAULT_REWARD_MIN),
                    "reward_max": reward_settings.get("reward_max", self.DEFAULT_REWARD_MAX),
                    "pool_limit": reward_settings.get("reward_pool", self.DEFAULT_POOL_LIMIT),
                    "pool_used": 0.0,  # Reset pool on new boss
                }}
            )

        boss_config = BOSSES[boss_id]

        deadline = None
        if duration_hours:
            deadline = time.time() + duration_hours * 3600

        state = {
            "_id": "boss_state",  # Fixed ID to ensure single document
            "boss_id": boss_id,
            "hp": boss_config["hp"],
            "max_hp": boss_config["hp"],
            "start_time": time.time(),
            "deadline": deadline,
            "intro": random.choice(BOSS_INTROS),
            "hits": {},      # user_id -> {"name": str, "dmg": int, "count": int}
            "cooldowns": {}, # user_id -> timestamp (for normal hits)
            "battle_log": [], # list of {"name": str, "dmg": int, "is_ult": bool, "crit": bool}
            "combo_count": 0,
            "last_combo_time": 0.0,
            "weakness_until": 0.0,
            "is_dead": False,
            "is_expired": False,
            "notified_10": False,
            "notified_25": False,
            "notified_50": False,
            "notified_75": False,
            "updated_at": datetime.now(timezone.utc)
        }

        await self._save_boss_state_doc(state)
        return state

    async def set_message_data(self, chat_id: int, message_id: int, has_photo: bool = False):
        """Сохранить ID сообщения с боссом."""
        # We'll store this in the boss state document for simplicity
        state = await self._get_boss_state_doc()
        if state:
            state["chat_id"] = chat_id
            state["message_id"] = message_id
            state["has_photo"] = has_photo
            state["updated_at"] = datetime.now(timezone.utc)
            await self._save_boss_state_doc(state)

    async def stop_boss(self):
        """Остановить (убить) текущего босса принудительно."""
        state = await self._get_boss_state_doc()
        if state:
            state["hp"] = 0
            state["is_dead"] = True
            state["updated_at"] = datetime.now(timezone.utc)
            await self._save_boss_state_doc(state)

    async def attack_boss(self, user_id: int, user_name: str, damage: int, is_ult: bool = False) -> BossAttackResult:
        """
        Нанести удар или ульту по боссу.
        """
        # Use a lock to prevent race conditions
        async with self._lock:
            state = await self._get_boss_state_doc()
            if not state:
                return BossAttackResult(None, "dead", 0)

            if state.get("is_dead") or state.get("is_expired"):
                return BossAttackResult(state, "dead", 0)

            # Check expiration
            if state.get("deadline") and time.time() > state["deadline"]:
                state["is_expired"] = True
                state["updated_at"] = datetime.now(timezone.utc)
                await self._save_boss_state_doc(state)
                return BossAttackResult(state, "expired", 0)

            now = time.time()
            user_key = str(user_id)

            # --- Ult Checks ---
            if is_ult:
                user_stats = state["hits"].get(user_key, {})
                hit_count = user_stats.get("count", 0)

                if hit_count < BOSS_ULT_REQUIRED_HITS:
                    # We need to return an error; we'll raise ValueError as before but catch it?
                    # The original raised ValueError. We'll do the same.
                    raise ValueError(f"Нужно еще {BOSS_ULT_REQUIRED_HITS - hit_count} ударов для ульты!")

                # Check global ult cooldown
                last_ult_doc = await self.boss_ult_cooldowns.find_one({"user_id": user_key})
                last_ult = last_ult_doc.get("last_ult", 0) if last_ult_doc else 0

                if now - last_ult < BOSS_ULT_COOLDOWN_HOURS * 3600:
                    remaining = int(BOSS_ULT_COOLDOWN_HOURS * 3600 - (now - last_ult))
                    minutes = remaining // 60
                    seconds = remaining % 60
                    raise ValueError(f"Ульта на перезарядке: {minutes} мин. {seconds} сек.")

                damage = damage * 5
            else:
                # --- Normal Hit Checks ---
                last_hit = state["cooldowns"].get(user_key, 0)
                if now - last_hit < BOSS_COOLDOWN_MINUTES * 60:
                    remaining = int(BOSS_COOLDOWN_MINUTES * 60 - (now - last_hit))
                    raise ValueError(f"Кулдаун: {remaining} сек.")

            # --- Evasion Mechanic ---
            # Boss has a chance to evade attacks (except ultimates)
            is_evaded = False
            is_weakness_active = False  # Initialize for evasion case
            if not is_ult and random.random() < 0.10:
                is_evaded = True
                actual_damage = 0
                # When evaded, we skip weakness and combo
            else:
                # --- Weakness Mechanic (Apply) ---
                is_weakness_active = False
                weakness_until = state.get("weakness_until", 0)
                if now < weakness_until:
                    is_weakness_active = True
                    damage = int(damage * 2.0)

                # --- Global Combo Mechanic ---
                combo_window = 10.0  # seconds
                last_combo = state.get("last_combo_time", 0)
                combo_count = state.get("combo_count", 0)

                if now - last_combo < combo_window:
                    combo_count += 1
                else:
                    combo_count = 1  # Reset or Start new

                # Cap combo multiplier at 2.0x (approx 50 hits)
                combo_multiplier = 1.0 + (min(combo_count, 50) * 0.02)

                state["combo_count"] = combo_count
                state["last_combo_time"] = now

                # Apply Combo Multiplier
                damage = int(damage * combo_multiplier)

                # Apply damage
                current_hp = state["hp"]
                max_hp = state["max_hp"]
                actual_damage = min(current_hp, damage)
                state["hp"] -= actual_damage

            # Check thresholds
            event = None
            new_hp_percent = (state["hp"] / max_hp) * 100

            if new_hp_percent <= 10 and not state.get("notified_10"):
                state["notified_10"] = True
                event = "hp_10"
            elif new_hp_percent <= 25 and not state.get("notified_25"):
                state["notified_25"] = True
                event = "hp_25"
            elif new_hp_percent <= 50 and not state.get("notified_50"):
                state["notified_50"] = True
                event = "hp_50"
            elif new_hp_percent <= 75 and not state.get("notified_75"):
                state["notified_75"] = True
                event = "hp_75"

            # --- Weakness Mechanic (Trigger) ---
            # 5% chance to trigger weakness if not active
            if not is_weakness_active and not is_ult and not event:
                if random.random() < 0.05:
                    state["weakness_until"] = now + 15.0
                    event = "weakness_started"

            # Record hit
            if user_key not in state["hits"]:
                state["hits"][user_key] = {"name": user_name, "dmg": 0, "count": 0}

            # Ensure count exists (migration)
            if "count" not in state["hits"][user_key]:
                state["hits"][user_key]["count"] = 0

            state["hits"][user_key]["dmg"] += actual_damage
            state["hits"][user_key]["count"] += 1
            state["hits"][user_key]["name"] = user_name

            # Update battle log
            log_entry = {
                "name": user_name,
                "dmg": actual_damage,
                "is_ult": is_ult,
                "crit": actual_damage > 18 and not is_ult,  # Simple heuristic for crit
                "evaded": is_evaded,
                "is_weakness": is_weakness_active
            }
            current_log = state.get("battle_log", [])
            current_log.append(log_entry)
            state["battle_log"] = current_log[-6:]  # Keep last 6

            # Update cooldowns
            if is_ult:
                await self.boss_ult_cooldowns.update_one(
                    {"user_id": user_key},
                    {"$set": {"last_ult": now}},
                    upsert=True
                )
            else:
                state["cooldowns"][user_key] = now

            result_type = "hit"
            if state["hp"] <= 0:
                state["hp"] = 0
                state["is_dead"] = True
                result_type = "killed"

            state["updated_at"] = datetime.now(timezone.utc)
            await self._save_boss_state_doc(state)

            return BossAttackResult(
                state,
                result_type,
                actual_damage,
                event,
                combo_count=combo_count,
                is_weakness=is_weakness_active
            )

    async def get_leaderboard(self, limit: int = 3) -> list[dict]:
        """Получить топ дамагеров текущего босса."""
        state = await self._get_boss_state_doc()
        if not state or not state.get("hits"):
            return []

        hits = state["hits"].values()
        # Sort by damage desc
        sorted_hits = sorted(hits, key=lambda x: x.get("dmg", 0), reverse=True)
        return sorted_hits[:limit]

    async def get_boss_image(self, boss_id: str) -> str | None:
        """Получить путь к случайной картинке босса."""
        if boss_id not in BOSSES:
            return None

        folder_rel = BOSSES[boss_id]["folder"]
        folder_path = settings.BASE_DIR / folder_rel

        if not folder_path.exists():
            return None

        images = [
            f for f in os.listdir(folder_path)
            if f.lower().endswith(('.jpg', '.png', '.gif', '.webp'))
        ]

        if images:
            return str(folder_path / random.choice(images))
        return None

    def get_hp_bar(self, current: int, maximum: int, length: int = 10) -> str:
        """Полоска HP."""
        if maximum <= 0:
            return "⬛" * length
        percent = current / maximum
        filled = int(percent * length)
        filled = max(0, min(length, filled))
        return "🟥" * filled + "⬛" * (length - filled)