"""
🎮 Сервис для игры БАНЗАЙ (Кто последний напишет перед тишиной).
Адаптирован для работы с MongoDB вместо Redis.
"""

import asyncio
import html
import time
import logging
import random
from typing import Optional, Dict, Set, Tuple, List
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError
from src.infra.mongo.client import MongoClient
from src.services.chat_activity_service import ChatActivityService
from src.services.lottery_service import LotteryService
from src.services.economy_service import EconomyService
from src.services.xrocket_service import XRocketService
from src.bot.presenters.banzai_presenter import BanzaiPresenter
from src.core.visuals import Visuals
from datetime import datetime, timezone
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

logger = logging.getLogger(__name__)

# Сколько последних ходов показываем в окне игры. Список уникален по игрокам
# и ограничен, иначе окно растёт бесконечно и тянет историю всей партии.
CONTENDERS_LIMIT = 12

# Приз за победу. Выплачивается из SenseiBank; если банк не покрывает,
# игрок остаётся с билетом и GRAM-наградой, но без монет.
BANZAI_PRIZE_COINS = 500.0

# Сколько длительностей партии допустимо «пережить» в простое. Всё, что старше,
# при рестарте считается брошенным и закрывается, а не доигрывается.
MAX_STALE_MULTIPLIER = 3


class BanzaiService:
    """Сервис для игры БАНЗАЙ с хранением состояния в MongoDB."""

    def __init__(
        self,
        mongo_client: MongoClient,
        chat_activity_service: ChatActivityService,
        lottery_service: LotteryService,
        economy_service: EconomyService,
        xrocket_service: XRocketService | None = None,
    ):
        self.mongo_client = mongo_client
        self.db: AsyncIOMotorDatabase = mongo_client.database
        self.chat_activity_service = chat_activity_service
        self.lottery_service = lottery_service
        self.economy_service = economy_service
        self.xrocket_service = xrocket_service
        self._workers: Dict[int, asyncio.Task] = {}
        self._last_ui_text: Dict[int, str] = {}
        self._last_ui_edit_ts: Dict[int, float] = {}
        self._last_taunt_ts: Dict[int, float] = {}
        self._user_display_cache: Dict[int, tuple[str, float]] = {}
        # Кому уже отправляли напоминание в ЛС в текущей партии. Держим в
        # памяти: перебор раундов не должен превращаться в поток сообщений,
        # а лишний запрос в Mongo на каждое сообщение в чате не нужен.
        self._dm_notified: Dict[int, Set[int]] = {}
        # Track deletion tasks to avoid garbage collection warnings (Python 3.10+)
        self._deletion_tasks: Dict[int, Set[asyncio.Task]] = {}

        # Collections
        self.banzai_games = self.db.banzai_games
        self.banzai_chat_activity = self.db.banzai_chat_activity
        # Уникальный индекс (chat_id, round) делает отправку оклика атомарной:
        # вставка второго документа за тот же раунд падает с DuplicateKeyError.
        self.banzai_callouts = self.db.banzai_callouts
        self.banzai_results = self.db.banzai_results

        # Ensure indexes
        asyncio.create_task(self._ensure_indexes())

    async def update_user_activity(self, chat_id: int, user_id: int, is_bot: bool = False) -> None:
        """Отмечает сообщение игрока в чате для игры БАНЗАЙ.

        Боты — не игроки: их сообщения не занимают место в «Последних ходах»,
        не попадают в счётчик «Люди» и не сбрасывают таймер тишины, иначе
        приветствие бота само сбивает отсчёт.

        ``silence_round`` — номер раунда тишины; растёт при каждом сбросе
        таймера. К нему привязана отправка предупреждения за минуту, поэтому
        после «перебил» оклик приходит заново, а в рамках одного раунда —
        строго один раз.
        """
        if is_bot:
            return

        now_ts = int(time.time())

        # Раньше эти две записи шли строго друг за другом, и каждое сообщение
        # в чате ждало два раунда к Mongo до того, как бот начинал отвечать.
        # Коллекции разные, поэтому bulk_write их не объединит, но отправлять
        # их параллельно можно: задержка одна вместо двух.
        await asyncio.gather(
            self.banzai_chat_activity.insert_one({
                "chat_id": chat_id,
                "user_id": user_id,
                "timestamp": now_ts,
            }),
            # Сбрасываем таймер и открываем новый раунд тишины. Номер раунда
            # увеличиваем атомарно ($inc), чтобы два одновременных сообщения не
            # получили один и тот же номер: иначе оклик «осталась минута» мог
            # бы не прийти после перебоя в одном из них.
            self.banzai_games.find_one_and_update(
                {"_id": chat_id, "active": True},
                {
                    "$set": {"last_activity": now_ts, "one_minute_callout_done": False},
                    "$inc": {"resets": 1, "silence_round": 1},
                    "$addToSet": {"reset_makers": user_id}
                },
            ),
        )

    async def _ensure_indexes(self):
        """Создать необходимые индексы в MongoDB."""
        try:
            # Индекс для banzai_games: _id (chat_id) уже является первичным ключом
            # Индекс для banzai_chat_activity: compound index на (chat_id, timestamp) для быстрого поиска
            await self.banzai_chat_activity.create_index(
                [("chat_id", 1), ("timestamp", -1)]
            )
            # TTL индекс для автоматического удаления старых записей активности (24 часа)
            await self.banzai_chat_activity.create_index(
                "timestamp",
                expireAfterSeconds=24 * 60 * 60
            )
            # Один оклик «осталась минута» на чат и раунд тишины.
            await self.banzai_callouts.create_index(
                [("chat_id", 1), ("round", 1)],
                unique=True,
            )
            # Страховка: если очистка при остановке не отработала (падение
            # процесса), старые претензии сами уедут через двое суток.
            await self.banzai_callouts.create_index(
                "created_at",
                expireAfterSeconds=48 * 60 * 60,
            )
            # История игр: быстрый поиск по чату и по игроку.
            await self.banzai_results.create_index([("chat_id", 1), ("finished_at", -1)])
            await self.banzai_results.create_index([("winner_id", 1), ("finished_at", -1)])
        except Exception as e:
            logger.warning(f"Не удалось создать индексы для banzai collections: {e}")

    def _active_key(self, chat_id: int) -> str:
        """Ключ для проверки активной игры (оставляем для совместимости, но не используем)."""
        return f"banzai:{chat_id}:active"

    def _duration_key(self, chat_id: int) -> str:
        return f"banzai:{chat_id}:duration"

    def _started_at_key(self, chat_id: int) -> str:
        return f"banzai:{chat_id}:started_at"

    def _reward_ton_key(self, chat_id: int) -> str:
        return f"banzai:{chat_id}:reward_ton"

    def _last_activity_key(self, chat_id: int) -> str:
        return f"chat:{chat_id}:last_activity"

    def _active_users_key(self, chat_id: int) -> str:
        return f"chat:{chat_id}:active_users"

    def _resets_key(self, chat_id: int) -> str:
        return f"banzai:{chat_id}:resets"

    def _resets_users_key(self, chat_id: int) -> str:
        """Redis SET с уникальными ID пользователей, сделавшими хотя бы один сброс."""
        return f"banzai:{chat_id}:resets_users"

    def _message_id_key(self, chat_id: int) -> str:
        return f"banzai:{chat_id}:message_id"

    async def start_game(self, chat_id: int, bot: Bot, duration_minutes: int = 10, reward_ton: float = 0.0) -> bool:
        """Запускает игру БАНЗАЙ в чате. Использует MongoDB для хранения состояния."""
        target = getattr(bot, 'game_chat_id', None)
        if target is not None and chat_id != target:
            return False
        # Проверяем, не активна ли уже игра
        existing = await self.banzai_games.find_one({"_id": chat_id})
        if existing and existing.get("active", False):
            return False

        now_ts = int(time.time())

        # Инициализируем документ игры
        game_doc = {
            "_id": chat_id,
            "active": True,
            "duration_minutes": duration_minutes,
            "started_at": now_ts,
            "reward_ton": float(reward_ton),
            "resets": 0,
            "last_activity": now_ts,
            "message_id": None,
            "reset_makers": [],  # Список уникальных пользователей, сделавших сброс
            "one_minute_callout_done": False,
            "silence_round": 0,
            "last_taunt_ts": 0,
        }

        await self.banzai_games.replace_one(
            {"_id": chat_id},
            game_doc,
            upsert=True
        )

        # Очищаем старые записи активности и претензий на оклик для этого
        # чата: раунд тишины начинается заново с нуля, иначе старая претензия
        # заблокировала бы предупреждение за минуту в новой игре.
        await self.banzai_chat_activity.delete_many({"chat_id": chat_id})
        await self.banzai_callouts.delete_many({"chat_id": chat_id})
        self._dm_notified.pop(chat_id, None)

        # Запускаем воркер
        if chat_id in self._workers:
            self._workers[chat_id].cancel()

        # Инициализируем отслеживание задач удаления для этого чата
        if chat_id not in self._deletion_tasks:
            self._deletion_tasks[chat_id] = set()

        task = asyncio.create_task(self._game_worker(chat_id, bot, duration_minutes))
        self._workers[chat_id] = task

        # Небольшая задержка, чтобы убедиться, что воркер запустился успешно
        # Это предотвращает ситуацию, когда start_game() возвращает True,
        # но воркер немедленно падает из-за ошибки инициализации
        try:
            await asyncio.sleep(0.1)  # Даем воркеру время на инициализацию
            # Проверяем, что задача всё ещё выполняется (не завершилась с ошибкой)
            if task.done():
                # Если задача завершилась, проверяем, не была ли она отменена или завершилась с исключением
                if task.cancelled():
                    logger.warning(f"Banzai worker for chat {chat_id} was cancelled during startup")
                elif task.exception():
                    logger.warning(f"Banzai worker for chat {chat_id} failed during startup: {task.exception()}")
                # В любом случае, если задача завершилась, игра не запустилась успешно
                # Очищаем и возвращаем False
                if chat_id in self._workers:
                    del self._workers[chat_id]
                if chat_id in self._deletion_tasks:
                    self._cleanup_deletion_tasks(chat_id)
                return False
            # Дополнительная проверка: убеждаемся, что документ игры всё ещё существует и активен
            game = await self.banzai_games.find_one({"_id": chat_id})
            if not game or not game.get("active", False):
                logger.warning(f"Banzai game document for chat {chat_id} was removed during worker startup")
                return False
        except Exception as e:
            logger.warning(f"Error during Banzai worker startup verification: {e}")
            # Если что-то пошло не так во время проверки, считаем запуск неудачным
            if chat_id in self._workers:
                del self._workers[chat_id]
            if chat_id in self._deletion_tasks:
                self._cleanup_deletion_tasks(chat_id)
            return False

        return True

    async def update_duration(self, chat_id: int, new_minutes: int) -> bool:
        """Обновляет продолжительность игры."""
        result = await self.banzai_games.update_one(
            {"_id": chat_id, "active": True},
            {"$set": {"duration_minutes": new_minutes}}
        )
        return result.modified_count > 0

    async def update_reward(self, chat_id: int, new_reward: float) -> bool:
        """Обновляет награду игры."""
        result = await self.banzai_games.update_one(
            {"_id": chat_id, "active": True},
            {"$set": {"reward_ton": float(new_reward)}}
        )
        return result.modified_count > 0

    async def stop_game(self, chat_id: int, bot: Bot | None = None) -> bool:
        """Останавливает игру вручную."""
        # Получаем статус игры перед остановкой
        game = await self.banzai_games.find_one({"_id": chat_id})
        if not game or not game.get("active", False):
            return False

        if bot is not None:
            # Обновляем интерфейс перед остановкой
            status = await self.get_status(chat_id)
            duration_minutes = int(status.get("duration_minutes") or 10)
            await self._update_game_interface(
                chat_id=chat_id,
                bot=bot,
                remaining_seconds=0,
                duration_minutes=duration_minutes,
                leader_name="-",
                is_finished=True,
                winner_name="Остановлен сенсеем",
                force=True,
                silence_seconds=0,
            )

        # Отменяем воркер
        if chat_id in self._workers:
            self._workers[chat_id].cancel()
            del self._workers[chat_id]

        # Удаляем документ игры и связанные данные
        await self.banzai_games.delete_one({"_id": chat_id})
        await self.banzai_chat_activity.delete_many({"chat_id": chat_id})
        await self.banzai_callouts.delete_many({"chat_id": chat_id})

        # Очищаем кэш интерфейса и открепляем сообщение
        message_id = await self.get_game_message_id(chat_id)
        if message_id and bot is not None:
            await self.unpin_game_message(chat_id, message_id, bot)

        self._last_ui_text.pop(chat_id, None)
        self._last_ui_edit_ts.pop(chat_id, None)
        self._last_taunt_ts.pop(chat_id, None)
        self._dm_notified.pop(chat_id, None)
        if chat_id in self._deletion_tasks:
            self._cleanup_deletion_tasks(chat_id)

        return True

    async def is_active(self, chat_id: int) -> bool:
        """Проверяет, активна ли игра в чате."""
        game = await self.banzai_games.find_one({"_id": chat_id})
        return bool(game and game.get("active", False))

    async def get_status(self, chat_id: int) -> Dict[str, object]:
        """Возвращает текущий статус игры."""
        game = await self.banzai_games.find_one({"_id": chat_id})
        if not game:
            return {
                "active": 0,
                "duration_minutes": 10,
                "started_at": None,
                "last_activity": None,
                "last_user_id": None,
                "last_user_ts": None,
                "reward_ton": 0.0,
                "resets": 0,
            }

        active = 1 if game.get("active", False) else 0
        duration_minutes = game.get("duration_minutes", 10)
        started_at = game.get("started_at")
        last_activity = game.get("last_activity")
        reward_ton = game.get("reward_ton", 0.0)
        resets = game.get("resets", 0)

        # Последний ход строго текущей партии: без ограничения по started_at
        # лидером считался бы тот, кто писал ещё до запуска игры.
        last_user_id, last_user_ts = await self._get_last_user_and_ts(
            chat_id, since_ts=started_at
        )

        return {
            "active": active,
            "duration_minutes": duration_minutes,
            "started_at": started_at,
            "last_activity": last_activity,
            "last_user_id": last_user_id,
            "last_user_ts": last_user_ts,
            "reward_ton": reward_ton,
            "resets": resets,
        }

    async def restore_workers(self, bot: Bot) -> int:
        """Восстанавливает активные игры после перезапуска бота.

        Партия могла пережить простой дольше своей длительности: пока бот
        лежал, тишина в чате «шла». Без пересчёта такая игра завершилась бы
        мгновенно на первом же тике, отдав победу случайному игроку. Поэтому
        слишком старые партии честно закрываются, а окно и таймер остальных
        сдвигаются к моменту рестарта.
        """
        restored = 0
        now = int(time.time())
        try:
            async for game in self.banzai_games.find({"active": True}):
                chat_id = game["_id"]
                target = getattr(bot, 'game_chat_id', None)
                if target is not None and chat_id != target:
                    # Preserve old games for operator review, but don't resume
                    # their timers or settle rewards in disallowed groups.
                    continue
                if chat_id in self._workers and not self._workers[chat_id].done():
                    continue

                duration_minutes = int(game.get("duration_minutes") or 10)
                started_at = game.get("started_at")
                if started_at:
                    age = now - int(started_at)
                    if age > duration_minutes * 60 * MAX_STALE_MULTIPLIER:
                        await self.banzai_games.delete_one({"_id": chat_id})
                        await self.banzai_chat_activity.delete_many({"chat_id": chat_id})
                        await self.banzai_callouts.delete_many({"chat_id": chat_id})
                        logger.info(
                            "Banzai in chat %s is stale (%ss old), dropped instead of restored",
                            chat_id, age,
                        )
                        continue

                # Перезапуск не должен выглядеть как мгновенная победа:
                # отодвигаем старт партии к текущему моменту, чтобы отсчёт
                # тишины пошёл заново и у игроков было время на реакцию.
                await self.banzai_games.update_one(
                    {"_id": chat_id},
                    {"$set": {"started_at": now, "last_activity": now,
                              "one_minute_callout_done": False}},
                )

                task = asyncio.create_task(self._game_worker(chat_id, bot, duration_minutes))
                self._workers[chat_id] = task
                restored += 1
        except Exception as e:
            logger.error(f"Не удалось восстановить работников Banzai: {e}", exc_info=True)
        return restored

    def get_game_keyboard(self, chat_id: int, active: bool = True, is_private: bool = False) -> InlineKeyboardMarkup:
        """Возвращает клавиатуру для игры."""
        return BanzaiPresenter.get_game_keyboard(chat_id, active=active, is_private=is_private)

    async def _get_user_display(self, chat_id: int, bot: Bot, user_id: int) -> str:
        """Получает отображаемое имя пользователя с кэшированием."""
        now = time.time()
        cached = self._user_display_cache.get(user_id)
        if cached and cached[1] > now:
            return cached[0]

        display = await BanzaiPresenter.get_user_display(bot, chat_id, user_id)
        self._user_display_cache[user_id] = (display, now + 6 * 3600)  # Кэш на 6 часов
        return display

    def _get_user_display_cached(self, user_id: int) -> str:
        """Получает кэшированное отображаемое имя пользователя."""
        cached = self._user_display_cache.get(user_id)
        if cached and cached[1] > time.time():
            return cached[0]
        return f"User {user_id}"

    async def get_live_state(self, chat_id: int, bot: Bot) -> Dict[str, object]:
        """Возвращает живое состояние игры для обновления интерфейса."""
        status = await self.get_status(chat_id)
        if not status.get("active"):
            return {"active": 0}

        now = int(time.time())
        duration_minutes = int(status.get("duration_minutes") or 10)
        duration_seconds = duration_minutes * 60
        started_at_ts = int(status.get("started_at") or now)
        last_activity_ts = status.get("last_activity")
        if isinstance(last_activity_ts, (int, float)):
            last_activity_ts = int(last_activity_ts)
        else:
            last_activity_ts = None

        last_time = max(float(last_activity_ts or started_at_ts), float(started_at_ts))
        silence_duration = max(0, int(time.time() - last_time))
        remaining_seconds = max(0, duration_seconds - int(silence_duration))

        # Общее время игры с момента запуска (не сбрасывается при сбросе тишины)
        elapsed_seconds = max(0, now - started_at_ts)

        leader_id = status.get("last_user_id")
        leader_ts = status.get("last_user_ts")
        if leader_id and leader_ts and started_at_ts is not None and int(leader_ts) < started_at_ts:
            leader_id = None

        leader_name = "Никто"
        if leader_id:
            leader_name = await self._get_user_display(chat_id, bot, int(leader_id))

        # Последний ход каждого участника текущей игры. Раньше здесь тянулась
        # вся история сообщений с начала партии — на живом чате это тысячи
        # документов каждые 6 секунд. Агрегация отдаёт по одному документу на
        # игрока, а лимит ограничивает её фиксированным окном.
        contenders: List[Tuple[int, int]] = []
        try:
            cursor = self.banzai_chat_activity.aggregate([
                {"$match": {
                    "chat_id": chat_id,
                    "timestamp": {"$gte": started_at_ts},
                    "is_bot": {"$ne": True},
                }},
                {"$sort": {"timestamp": -1}},
                {"$group": {
                    "_id": "$user_id",
                    "ts": {"$first": "$timestamp"},
                }},
                {"$sort": {"ts": -1}},
                {"$limit": CONTENDERS_LIMIT},
            ])
            async for doc in cursor:
                contenders.append((doc["_id"], doc["ts"]))
        except Exception as e:
            logger.debug(f"Ошибка при получении contendors: {e}")
            contenders = []

        contenders = list(reversed(contenders))  # От старых к новым для отображения
        # Забаненные не должны светиться в «Последних ходах»: они уже не игроки.
        banned = await self._banned_user_ids([uid for uid, _ in contenders])
        rendered_contenders: List[Tuple[str, int]] = [
            (self._get_user_display_cached(uid), ts)
            for uid, ts in contenders
            if uid not in banned
        ]

        return {
            "active": 1,
            "duration_minutes": duration_minutes,
            "remaining_seconds": remaining_seconds,
            "elapsed_seconds": elapsed_seconds,
            "silence_seconds": silence_duration,
            "leader_name": leader_name,
            "contenders": rendered_contenders,
            "reward_ton": status.get("reward_ton") or 0.0,
            "resets_count": status.get("resets") or 0,
            "reset_makers_count": len(await self._get_reset_makers(chat_id)),
        }

    async def _get_reset_makers(self, chat_id: int) -> List[int]:
        """Получает список уникальных пользователей, сделавших сброс."""
        game = await self.banzai_games.find_one({"_id": chat_id})
        if not game:
            return []
        return game.get("reset_makers", [])

    async def refresh_window(self, chat_id: int, bot: Bot, force: bool = False) -> bool:
        """Обновляет интерфейс игры в чате."""
        status = await self.get_status(chat_id)
        if not status.get("active"):
            return False
        state = await self.get_live_state(chat_id, bot)
        await self._update_game_interface(
            chat_id=chat_id,
            bot=bot,
            remaining_seconds=int(state.get("remaining_seconds") or 0),
            duration_minutes=int(state.get("duration_minutes") or 10),
            leader_name=str(state.get("leader_name") or "-"),
            is_finished=False,
            force=force,
            silence_seconds=int(state.get("silence_seconds") or 0),
        )
        return True

    async def set_game_message_id(self, chat_id: int, message_id: int):
        """Сохраняет ID сообщения игры."""
        await self.banzai_games.update_one(
            {"_id": chat_id},
            {"$set": {"message_id": message_id}}
        )

    async def get_game_message_id(self, chat_id: int) -> Optional[int]:
        """Получает ID сообщения игры."""
        game = await self.banzai_games.find_one({"_id": chat_id})
        return game.get("message_id") if game else None

    async def pin_game_message(self, chat_id: int, message_id: int, bot: Bot) -> bool:
        """Закрепляет сообщение игры в чате."""
        try:
            await bot.pin_chat_message(chat_id, message_id, disable_notification=True)
            logger.debug(f"Пinned Banzai message {message_id} in chat {chat_id}")
            return True
        except Exception as e:
            logger.debug(f"Failed to pin Banzai message in chat {chat_id}: {e}")
            return False

    async def unpin_game_message(self, chat_id: int, message_id: int, bot: Bot) -> bool:
        """Открепляет сообщение игры в чате."""
        try:
            await bot.unpin_chat_message(chat_id, message_id)
            logger.debug(f"Unpinned Banzai message {message_id} in chat {chat_id}")
            return True
        except Exception as e:
            logger.debug(f"Failed to unpin Banzai message in chat {chat_id}: {e}")
            return False

    async def _game_worker(self, chat_id: int, bot: Bot, duration_minutes: int):
        """Основной рабочий цикл игры."""
        logger.info(f"🚨 Banzai worker started for chat {chat_id}")
        active_key = f"banzai:{chat_id}:active"  # Для логов, не используем в MongoDB
        duration_seconds = duration_minutes * 60

        started_at_ts = None
        started_at_raw = await self.banzai_games.find_one({"_id": chat_id}, {"started_at": 1})
        if started_at_raw and "started_at" in started_at_raw:
            started_at_ts = started_at_raw["started_at"]
        if started_at_ts is None:
            started_at_ts = int(time.time())

        last_known_leader_id = None
        last_known_leader_name = "Никто"
        prev_activity_ts = None
        tick_counter = 0
        update_interval = 3  # Обновлять каждые 3 цикла (6 сек вместо 10)

        try:
            while True:
                # Проверяем, активна ли игра (каждые 2 секунды)
                await asyncio.sleep(2)
                tick_counter += 1

                # Проверяем активность игры в MongoDB
                game = await self.banzai_games.find_one({"_id": chat_id})
                if not game or not game.get("active", False):
                    break

                # Обновляем продолжительность из MongoDB (если изменилась)
                duration_raw = game.get("duration_minutes")
                if duration_raw is not None and duration_raw != duration_minutes:
                    duration_minutes = int(duration_raw)
                    duration_seconds = duration_minutes * 60

                # Получаем последнюю активность из игры (обновляется в update_user_activity)
                last_activity_ts = game.get("last_activity")
                if last_activity_ts is None:
                    last_activity_ts = started_at_ts

                # Текущий лидер — строго среди ходов этой партии.
                current_leader_id, current_leader_ts = await self._get_last_user_and_ts(
                    chat_id, since_ts=started_at_ts
                )

                # Обновляем предыдущий timestamp активности для обнаружения сброса
                if last_activity_ts:
                    prev_activity_ts = last_activity_ts

                # Вычисляем оставшееся время: silenz считается с момента последней активности,
                # но если последняя активность до начала игры, то засчитываем с начала игры
                if last_activity_ts < started_at_ts:
                    effective_last_ts = started_at_ts
                else:
                    effective_last_ts = last_activity_ts
                silence_duration = time.time() - effective_last_ts
                remaining_seconds = max(0, duration_seconds - int(silence_duration))
                # Обновляем кэш имени лидера при изменении
                if current_leader_id != last_known_leader_id:
                    # Новый Король!
                    if current_leader_id and last_known_leader_id is not None:
                        # Отправляем миглющее уведомление (анти-спам)
                        try:
                            now_ts = time.time()
                            last_taunt_ts = self._last_taunt_ts.get(chat_id, 0)
                            if now_ts - last_taunt_ts > 15:  # Минимум 15 секунд между сообщениями
                                display = await self._get_user_display(chat_id, bot, int(current_leader_id))
                                taunt = random.choice(Visuals.TAUNTS)  # Используем taunts из visuals
                                msg = await bot.send_message(
                                    chat_id,
                                    f"⚡ <b>{html.escape(display)}</b> {taunt}",
                                    parse_mode="HTML"
                                )
                                self._last_taunt_ts[chat_id] = now_ts
                                delete_task = asyncio.create_task(
                                    self._delete_later(bot, chat_id, msg.message_id, 5)
                                )
                                self._add_deletion_task(chat_id, delete_task)
                        except Exception as e:
                            logger.debug(f"Ошибка при отправке taunt: {e}")

                    last_known_leader_id = current_leader_id
                    if current_leader_id:
                        last_known_leader_name = await self._get_user_display(chat_id, bot, int(current_leader_id))
                    else:
                        last_known_leader_name = "Никто"

                # Уведомление за минуту — до обновления окна: иначе последний
                # кадр успевает показать точный остаток и слепой финал ломается.
                last_minute = 0 < remaining_seconds <= 60
                if last_minute:
                    await self._send_one_minute_callout(chat_id, bot, started_at_ts)

                # Периодически обновляем интерфейс. В последнюю минуту окно
                # замирает: победа должна зависеть от выдержки, а не от того,
                # кто точнее смотрит на таймер.
                if tick_counter % update_interval == 0 and not last_minute:
                    elapsed_seconds = max(0, int(time.time()) - started_at_ts)
                    await self._update_game_interface(
                        chat_id=chat_id,
                        bot=bot,
                        remaining_seconds=remaining_seconds,
                        duration_minutes=duration_minutes,
                        leader_name=last_known_leader_name,
                        is_finished=False,
                        silence_seconds=silence_duration,
                        elapsed_seconds=elapsed_seconds,
                    )

                # Проверяем на завершение игры по времени
                if silence_duration > duration_seconds:
                    await self._finish_game(chat_id, bot, duration_minutes)
                    break

        except asyncio.CancelledError:
            logger.info(f"Banzai worker cancelled for chat {chat_id}")
        except Exception as e:
            logger.error(f"Error in Banzai worker: {e}", exc_info=True)
        finally:
            # Очистка при завершении воркера
            await self.banzai_games.delete_one({"_id": chat_id})
            await self.banzai_chat_activity.delete_many({"chat_id": chat_id})

            if chat_id in self._workers:
                del self._workers[chat_id]
            self._last_ui_text.pop(chat_id, None)
            self._last_ui_edit_ts.pop(chat_id, None)
            self._last_taunt_ts.pop(chat_id, None)

            # Отменяем все ожидающие задачи удаления
            self._cleanup_deletion_tasks(chat_id)

    def _add_deletion_task(self, chat_id: int, task: asyncio.Task) -> None:
        """Добавляет задачу в отслеживание для последующей очистки."""
        if chat_id not in self._deletion_tasks:
            self._deletion_tasks[chat_id] = set()

        self._deletion_tasks[chat_id].add(task)
        task.add_done_callback(lambda t: self._deletion_tasks[chat_id].discard(t))

    def _cleanup_deletion_tasks(self, chat_id: int) -> None:
        """Отменяет и очищает все задачи удаления для чата."""
        if chat_id in self._deletion_tasks:
            for task in self._deletion_tasks[chat_id]:
                if not task.done():
                    task.cancel()
            del self._deletion_tasks[chat_id]

    async def _delete_later(self, bot: Bot, chat_id: int, message_id: int, delay: int):
        """Удаляет сообщение через указанную задержку."""
        await asyncio.sleep(delay)
        try:
            await bot.delete_message(chat_id, message_id)
        except Exception:
            pass  # Игнорируем ошибки удаления (сообщение уже удалено и т.д.)

    async def _update_game_interface(
        self,
        chat_id: int,
        bot: Bot,
        remaining_seconds: int,
        duration_minutes: int,
        leader_name: str,
        is_finished: bool = False,
        winner_name: str = None,
        force: bool = False,
        silence_seconds: int | None = None,
        elapsed_seconds: int | None = None,
    ):
        """Обновляет интерфейс игры в чате."""
        msg_id = await self.get_game_message_id(chat_id)
        if not msg_id:
            return

        # Получаем текущую награду и счетчик сбросов
        reward_ton = 0.0
        try:
            rt = await self.banzai_games.find_one({"_id": chat_id}, {"reward_ton": 1})
            if rt and "reward_ton" in rt:
                reward_ton = float(rt["reward_ton"])
        except Exception:
            pass

        resets_count = 0
        try:
            resets_doc = await self.banzai_games.find_one({"_id": chat_id}, {"resets": 1})
            if resets_doc and "resets" in resets_doc:
                resets_count = int(resets_doc["resets"])
        except Exception:
            pass

        # Получаем уникальное количество создателей сбросов
        reset_makers_count = len(await self._get_reset_makers(chat_id))

        # Получаем список contendors для визуального отображения
        contenders = []
        if not is_finished:
            state = await self.get_live_state(chat_id, bot)
            contenders = state.get("contenders", [])
            silence_seconds = int(state.get("silence_seconds") or 0)
        else:
            silence_seconds = None

        # --- Визуальное представление ---
        now = time.time()
        last_edit = self._last_ui_edit_ts.get(chat_id)
        if last_edit is not None and not force and now - last_edit < 6:
            return

        # Используем Presenter для рендеринга интерфейса
        text = BanzaiPresenter.render_game_interface(
            remaining_seconds,
            duration_minutes,
            leader_name,
            is_finished,
            winner_name,
            reward_ton,
            resets_count,
            participants_count=len(contenders) if contenders else 0,
            reset_makers_count=reset_makers_count,
            contenders=contenders,
            silence_seconds=silence_seconds,
            elapsed_seconds=elapsed_seconds,
        )

        kb = self.get_game_keyboard(chat_id, active=not is_finished, is_private=False)

        prev_text = self._last_ui_text.get(chat_id)
        if prev_text == text and not force:
            return

        try:
            await bot.edit_message_text(
                text=text,
                chat_id=chat_id,
                message_id=msg_id,
                parse_mode="HTML",
                reply_markup=kb
            )
            self._last_ui_text[chat_id] = text
            self._last_ui_edit_ts[chat_id] = time.time()
        except Exception as e:
            logger.debug(f"Error updating game interface in chat {chat_id}: {e}")
            return

    async def _get_last_user_and_ts(
        self, chat_id: int, since_ts: Optional[int] = None
    ) -> Tuple[Optional[int], Optional[int]]:
        """Последний *живой* игрок и время его сообщения.

        Пропускаем:
        * ботов — их сообщения не ходы, иначе бот стал бы королём;
        * забаненных в боте — иначе забаненный уносил бы 500 Coin и билет.

        ``since_ts`` ограничивает поиск текущей игрой: без него последним
        «игроком» мог оказаться тот, кто писал ещё до старта партии.
        """
        try:
            query: dict = {"chat_id": chat_id, "is_bot": {"$ne": True}}
            if since_ts is not None:
                query["timestamp"] = {"$gte": int(since_ts)}
            cursor = self.banzai_chat_activity.find(query).sort("timestamp", -1).limit(25)
            async for latest in cursor:
                if latest.get("is_bot"):
                    continue
                user_id = latest["user_id"]
                if await self._is_banned(user_id):
                    continue
                return user_id, latest["timestamp"]
        except Exception:
            pass

        return None, None

    async def _banned_user_ids(self, user_ids: List[int]) -> Set[int]:
        """Один запрос вместо проверки каждого игрока по отдельности."""
        ids = {int(uid) for uid in user_ids if uid is not None}
        if not ids:
            return set()
        try:
            cursor = self.db.users.find(
                {"id": {"$in": list(ids)}, "is_banned": True}, {"id": 1}
            )
            return {int(doc["id"]) for doc in await cursor.to_list(length=None)}
        except Exception:
            return set()

    async def _is_banned(self, user_id: int) -> bool:
        """Забанен ли игрок в боте (отсутствующий профиль — не бан)."""
        try:
            profile = await self.db.users.find_one(
                {"id": int(user_id)}, {"is_banned": 1}
            )
            return bool((profile or {}).get("is_banned"))
        except Exception:
            return False

    async def _send_one_minute_callout(self, chat_id: int, bot: Bot, started_at_ts: int) -> None:
        """Отправляет уведомление за одну минуту до конца игры.

        Оклик привязан к раунду тишины (``silence_round``), а не к игре
        целиком: каждый новый раунд — новый оклик. Внутри раунда он строго
        один: претензия на отправку занимается атомарной вставкой в
        ``banzai_callouts`` с уникальным индексом (chat_id, round), поэтому
        два воркера не пришлют два одинаковых предупреждения.
        """
        game = await self.banzai_games.find_one({"_id": chat_id})
        if not game or not game.get("active", False):
            return
        if game.get("one_minute_callout_done", False):
            return

        round_no = int(game.get("silence_round") or 0)
        try:
            await self.banzai_callouts.insert_one({
                "chat_id": chat_id,
                "round": round_no,
                "created_at": int(time.time()),
            })
        except DuplicateKeyError:
            # Оклик за этот раунд уже забрал другой воркер.
            await self.banzai_games.update_one(
                {"_id": chat_id},
                {"$set": {"one_minute_callout_done": True}}
            )
            return

        last_user_id, last_user_ts = await self._get_last_user_and_ts(
            chat_id, since_ts=started_at_ts
        )
        if not last_user_id or not last_user_ts:
            # Действительного лидера нет — оклик отправлять некому, но раунд
            # считаем отработанным, чтобы не долбить чат пустыми окликами.
            await self.banzai_games.update_one(
                {"_id": chat_id},
                {"$set": {"one_minute_callout_done": True}}
            )
            return

        mention = None
        try:
            member = await bot.get_chat_member(chat_id, int(last_user_id))
            user = member.user
            if user.username:
                mention = f"@{user.username}"
            else:
                safe_name = html.escape(user.full_name)
                mention = f'<a href="tg://user?id={user.id}">{safe_name}</a>'
        except Exception:
            mention = f"User {last_user_id}"

        await self.banzai_games.update_one(
            {"_id": chat_id},
            {"$set": {"one_minute_callout_done": True}}
        )

        text = BanzaiPresenter.render_one_minute_callout(mention)
        try:
            await bot.send_message(chat_id, text, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Failed to send Banzai 1-minute callout: {e}")

        # Напоминание в личку — только тем, кто реально играет в этой партии.
        await self._notify_participants_dm(chat_id, bot, started_at_ts, last_user_id)

    async def _record_result(
        self, *, chat_id: int, winner_id: Optional[int],
        duration_minutes: int, started_at_ts: Optional[int],
    ) -> None:
        """Сохраняет итог партии для истории и статистики игроков."""
        now = int(time.time())
        await self.banzai_results.insert_one({
            "chat_id": chat_id,
            "winner_id": int(winner_id) if winner_id else None,
            "duration_minutes": int(duration_minutes),
            "started_at": int(started_at_ts) if started_at_ts else None,
            "finished_at": now,
            "duration_seconds": max(0, now - int(started_at_ts)) if started_at_ts else None,
        })

    async def get_player_stats(self, user_id: int, limit: int = 500) -> Dict[str, int]:
        """Статистика игрока по сохранённым партиям.

        Побед и участий в старых партиях нет — история пишется с момента
        появления ``banzai_results``, поэтому цифры честные, а не выдуманные
        из билетов лотереи.
        """
        stats = {"wins": 0}
        try:
            stats["wins"] = await self.banzai_results.count_documents(
                {"winner_id": int(user_id)}
            )
        except Exception as e:
            logger.debug(f"Статистика банзая недоступна: {e}")
        return stats

    async def get_winner_name(self, chat_id: int, bot: Bot, user_id: Optional[int]) -> str:
        """Имя победителя для истории: «Никто», если партия без победителя."""
        if not user_id:
            return "Никто"
        return await self._get_user_display(chat_id, bot, int(user_id))

    async def get_recent_results(self, chat_id: int, limit: int = 5) -> List[Dict]:
        """Последние завершённые партии в этом чате."""
        try:
            cursor = self.banzai_results.find({"chat_id": chat_id}).sort(
                "finished_at", -1
            ).limit(max(1, int(limit)))
            return await cursor.to_list(length=None)
        except Exception:
            return []

    async def _notify_participants_dm(
        self, chat_id: int, bot: Bot, started_at_ts: int, leader_id: Optional[int]
    ) -> int:
        """Личное напоминание о финале — участникам текущей партии.

        «Участник» здесь значит «сделал ход в этой игре»: записи активности
        ограничены ``started_at_ts``, поэтому случайные люди и те, кто писал
        до старта, напоминание не получат. Каждому — не больше одного раза
        за партию, иначе игра начнёт спамить личку на каждом раунде.
        """
        notified = self._dm_notified.setdefault(chat_id, set())
        try:
            cursor = self.banzai_chat_activity.aggregate([
                {"$match": {
                    "chat_id": chat_id,
                    "timestamp": {"$gte": int(started_at_ts)},
                    "is_bot": {"$ne": True},
                }},
                {"$group": {"_id": "$user_id"}},
                {"$limit": 200},
            ])
            participants = [doc["_id"] for doc in await cursor.to_list(length=None)]
        except Exception as e:
            logger.debug(f"Не удалось собрать участников для ЛС-напоминания: {e}")
            return 0

        if not participants:
            return 0

        banned = await self._banned_user_ids(participants)
        targets = [int(uid) for uid in participants
                   if uid and int(uid) not in banned and int(uid) not in notified]
        if not targets:
            return 0

        sent = 0
        for uid in targets:
            body = BanzaiPresenter.render_dm_final_reminder(
                is_leader=(leader_id is not None and int(leader_id) == uid)
            )
            try:
                await bot.send_message(uid, body, parse_mode="HTML")
                notified.add(uid)
                sent += 1
            except TelegramForbiddenError:
                # Игрок не открывал чат с ботом или заблокировал его — это не
                # ошибка игры, просто пропускаем и больше не пробуем.
                notified.add(uid)
            except Exception as e:
                logger.debug(f"Не удалось отправить напоминание игроку {uid}: {e}")
        return sent

    async def _finish_game(self, chat_id: int, bot: Bot, duration_minutes: int):
        """Завершает игру и распределяет награды."""
        started_at_ts = None
        started_at_raw = await self.banzai_games.find_one({"_id": chat_id}, {"started_at": 1})
        if started_at_raw and "started_at" in started_at_raw:
            started_at_ts = started_at_raw["started_at"]

        # Победитель — только участник этой партии и только не забаненный.
        winner_id, _ = await self._get_last_user_and_ts(chat_id, since_ts=started_at_ts)

        winner_name = None
        if winner_id:
            winner_name = await self._get_user_display(chat_id, bot, int(winner_id))

            # Распределяем награды
            try:
                # 1. Билет в лотерею
                ticket_result = await self.lottery_service.add_ticket(int(winner_id), source="banzai_win")
                ticket_confirmed = bool(ticket_result and ticket_result.get('success'))
                if not ticket_confirmed:
                    logger.warning('Banzai ticket requires verification chat=%s user=%s', chat_id, winner_id)

                # 2. Монеты — из SenseiBank, не из эмиссии. process_game_win
                # резервирует новые Coin под общий лимит эмиссии; для призовых
                # это неверно: банк платит уже существующими и отказывает,
                # если их нет.
                payout = await self.economy_service.pay_game_reward_from_bank(
                    int(winner_id), BANZAI_PRIZE_COINS, description="Banzai Win"
                )
                if not payout.get("success"):
                    logger.warning(
                        "Banzai prize not paid for chat=%s user=%s: %s",
                        chat_id, winner_id, payout.get("reason"),
                    )

                # 3. GRAM (если есть)
                reward_ton = 0.0
                try:
                    rt = await self.banzai_games.find_one({"_id": chat_id}, {"reward_ton": 1})
                    if rt and "reward_ton" in rt:
                        reward_ton = float(rt["reward_ton"])
                except Exception:
                    pass

                if reward_ton > 0 and self.xrocket_service:
                    # Attempt transfer directly — xRocket transfer API is the source of truth
                    # for sufficient funds (get_balance() endpoint returns 404 on pay.xrocket.tg).
                    tid = f"banzai:{chat_id}:{int(winner_id)}:{int(time.time()*1000)}"
                    transfer_ok = await self.xrocket_service.transfer(
                        user_id=int(winner_id),
                        currency="GRAM",
                        amount=reward_ton,
                        transfer_id=tid,
                    )
                    if not transfer_ok:
                        logger.warning(f"Insufficient xRocket balance for GRAM transfer in Banzai: reward_amount={reward_ton}")

                # Отправляем визуальное уведомление победителю
                try:
                    w = 32
                    lines = [
                        Visuals.frame_top_left(w),
                        Visuals.frame_line_left(f"{Visuals.trophy_raw()} BANZAI ULTIMATE — ПОБЕДА", w, "center"),
                        Visuals.frame_separator_left(w),
                        Visuals.frame_line_left(f"👑 {winner_name}", w, "center"),
                        Visuals.frame_line_left("Ты выдержал тишину до конца", w, "center"),
                        Visuals.frame_separator_left(w),
                        Visuals.frame_line_left("🎁 Трофеи:", w),
                        Visuals.frame_line_left("🎫 1 Билет" if ticket_confirmed else
                                                "🎫 Билет: проверка", w),
                        Visuals.frame_line_left(
                            f"💰 +{BANZAI_PRIZE_COINS:,.0f} Coins"
                            + ("" if payout.get("success") else " (банк пуст)"), w),
                    ]
                    if reward_ton > 0:
                        lines.append(Visuals.frame_line_left(f"💎 +{reward_ton} GRAM", w))
                    lines.append(Visuals.frame_bottom_left(w))
                    text = "<pre>\n" + "\n".join(lines) + "\n</pre>"
                    await bot.send_message(int(winner_id), text, parse_mode="HTML")
                except Exception:
                    pass
            except Exception as e:
                logger.error(f"Error distributing Banzai rewards: {e}")

        # Обновляем интерфейс игры на финальный вид
        # Покажем общее время игры на финальном экране.
        total_elapsed_seconds = None
        try:
            game = await self.banzai_games.find_one({"_id": chat_id}, {"started_at": 1})
            if game and game.get("started_at") is not None:
                total_elapsed_seconds = max(0, int(time.time()) - int(game["started_at"]))
        except Exception:
            pass

        await self._update_game_interface(
            chat_id=chat_id,
            bot=bot,
            remaining_seconds=0,
            duration_minutes=duration_minutes,
            leader_name="-",
            is_finished=True,
            winner_name=winner_name,
            force=True,
            silence_seconds=0,
            elapsed_seconds=total_elapsed_seconds,
        )

        # Сохраняем результат: без этого у игры нет ни истории, ни лидерборда.
        try:
            await self._record_result(
                chat_id=chat_id,
                winner_id=winner_id,
                duration_minutes=duration_minutes,
                started_at_ts=started_at_ts,
            )
        except Exception as e:
            logger.warning("Не удалось записать историю банзая для %s: %s", chat_id, e)

        # Unpin the game message when game finishes
        message_id = await self.get_game_message_id(chat_id)
        if message_id:
            await self.unpin_game_message(chat_id, message_id, bot)