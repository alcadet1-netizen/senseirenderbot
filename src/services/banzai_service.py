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
from src.infra.mongo.client import MongoClient
from src.services.chat_activity_service import ChatActivityService
from src.services.lottery_service import LotteryService
from src.services.economy_service import EconomyService
from src.services.xrocket_service import XRocketService
from src.bot.presenters.banzai_presenter import BanzaiPresenter
from src.core.visuals import Visuals
from datetime import datetime, timezone
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

logger = logging.getLogger(__name__)


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
        # Track deletion tasks to avoid garbage collection warnings (Python 3.10+)
        self._deletion_tasks: Dict[int, Set[asyncio.Task]] = {}

        # Collections
        self.banzai_games = self.db.banzai_games
        self.banzai_chat_activity = self.db.banzai_chat_activity

        # Ensure indexes
        asyncio.create_task(self._ensure_indexes())

    async def update_user_activity(self, chat_id: int, user_id: int) -> None:
        """Обновляет активность пользователя в чате для игры БАНЗАЙ.
        Добавляет запись в сортированный набор (в MongoDB мы сохраняем документ с индексом).
        Для простоты сохраняем отдельный документ, но можем использовать сортированный набор через MongoDB.
        Однако для получения последних пользователей нам нужна сортировка по timestamp.
        Мы будем сохранять документы и создавать индекс по (chat_id, timestamp) для быстрого доступа.
        """
        doc = {
            "chat_id": chat_id,
            "user_id": user_id,
            "timestamp": int(time.time()),
        }
        await self.banzai_chat_activity.insert_one(doc)

        # Also update the game document's last_activity if the game is active
        await self.banzai_games.update_one(
            {"_id": chat_id, "active": True},
            {"$set": {"last_activity": int(time.time())}}
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
        except Exception as e:
            logger.warning(f"Не удалось создать индексы для banzai collections: {e}")

    def _active_key(self, chat_id: int) -> str:
        """Ключ для проверки активной игры (оставляем для совместимости, но не используем)."""
        return f"banzai:{chat_id}:active"

    def _duration_key(self, chat_id: int) -> str:
        return f"banzai:{chat_id}:duration"

    def _started_at_key(self, chat_id: int) -> str:
        return f"banzai:{chat_id}:started_at"

    def _one_minute_callout_key(self, chat_id: int) -> str:
        return f"banzai:{chat_id}:callout_1m"

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
            "last_taunt_ts": 0,
        }

        await self.banzai_games.replace_one(
            {"_id": chat_id},
            game_doc,
            upsert=True
        )

        # Очищаем старые записи активности для этого чата (опционально)
        await self.banzai_chat_activity.delete_many({"chat_id": chat_id})

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

        # Очищаем кэш интерфейса и открепляем сообщение
        message_id = await self.get_game_message_id(chat_id)
        if message_id and bot is not None:
            await self.unpin_game_message(chat_id, message_id, bot)

        self._last_ui_text.pop(chat_id, None)
        self._last_ui_edit_ts.pop(chat_id, None)
        self._last_taunt_ts.pop(chat_id, None)
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

        # Получаем последнего пользователя и его timestamp через chat_activity_service
        last_user_id, last_user_ts = await self._get_last_user_and_ts(chat_id)

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
        """Восстанавливает активные работники после перезапуска бота."""
        restored = 0
        try:
            # Находим все активные игры
            async for game in self.banzai_games.find({"active": True}):
                chat_id = game["_id"]
                if chat_id in self._workers and not self._workers[chat_id].done():
                    continue

                duration_minutes = game.get("duration_minutes", 10)
                task = asyncio.create_task(self._game_worker(chat_id, bot, duration_minutes))
                self._workers[chat_id] = task
                restored += 1
        except Exception as e:
            logger.error(f"Не удалось восстановить работников Banzai: {e}", exc_info=True)
        return restored

    def get_game_keyboard(self, chat_id: int, active: bool = True) -> InlineKeyboardMarkup:
        """Возвращает клавиатуру для игры."""
        return BanzaiPresenter.get_game_keyboard(chat_id, active=active, is_private=False)

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
        remaining_seconds = duration_seconds - int(silence_duration)

        leader_id = status.get("last_user_id")
        leader_ts = status.get("last_user_ts")
        if leader_id and leader_ts and started_at_ts is not None and int(leader_ts) < started_at_ts:
            leader_id = None

        leader_name = "Никто"
        if leader_id:
            leader_name = await self._get_user_display(chat_id, bot, int(leader_id))

        # Получаем топ-5 конкурентов (последних активных пользователей)
        contenders: List[Tuple[int, int]] = []
        try:
            cursor = self.banzai_chat_activity.find(
                {"chat_id": chat_id, "timestamp": {"$gte": started_at_ts}}
            ).sort("timestamp", -1).limit(5)
            async for doc in cursor:
                uid = doc["user_id"]
                ts = doc["timestamp"]
                contenders.append((uid, ts))
        except Exception as e:
            logger.debug(f"Ошибка при получении contendors: {e}")
            contenders = []

        contenders = list(reversed(contenders))  # От старых к новым для отображения
        rendered_contenders: List[Tuple[str, int]] = []
        for uid, ts in contenders:
            rendered_contenders.append((self._get_user_display_cached(uid), ts))

        return {
            "active": 1,
            "duration_minutes": duration_minutes,
            "remaining_seconds": remaining_seconds,
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

                # Получаем текущего лидера (последнего пользователя) и его timestamp
                current_leader_id, current_leader_ts = await self._get_last_user_and_ts(chat_id)

                # Игнорируем лидеров из до начала игры (для отображения лидера)
                if current_leader_ts and current_leader_ts < started_at_ts:
                    current_leader_id = None

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

                # Периодически обновляем интерфейс
                if tick_counter % update_interval == 0:
                    await self._update_game_interface(
                        chat_id=chat_id,
                        bot=bot,
                        remaining_seconds=remaining_seconds,
                        duration_minutes=duration_minutes,
                        leader_name=last_known_leader_name,
                        is_finished=False,
                        silence_seconds=silence_duration,
                    )

                # Отправляем уведомление за 1 минуту до конца
                if 0 < remaining_seconds <= 60:
                    await self._send_one_minute_callout(chat_id, bot, started_at_ts)

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
        )

        kb = BanzaiPresenter.get_game_keyboard(chat_id, active=not is_finished, is_private=False)

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

    async def _get_last_user_and_ts(self, chat_id: int) -> Tuple[Optional[int], Optional[int]]:
        """Получает последнего пользователя и его timestamp из коллекции активности БАНЗАЙ."""
        try:
            latest = await self.banzai_chat_activity.find_one(
                {"chat_id": chat_id},
                sort=[("timestamp", -1)]
            )
            if latest:
                return latest["user_id"], latest["timestamp"]
        except Exception:
            pass

        return None, None

    async def _send_one_minute_callout(self, chat_id: int, bot: Bot, started_at_ts: int) -> None:
        """Отправляет уведомление за одну минуту до конца игры."""
        callout_key = f"banzai:{chat_id}:callout_1m"
        # Проверяем, не отправляли ли мы уже это уведомление
        game = await self.banzai_games.find_one({"_id": chat_id})
        if game and game.get("one_minute_callout_done", False):
            return

        last_user_id, last_user_ts = await self._get_last_user_and_ts(chat_id)
        if not last_user_id or not last_user_ts or last_user_ts < started_at_ts:
            # Если нет действительного лидера, просто отмечаем как отправленное и выходим
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

    async def _finish_game(self, chat_id: int, bot: Bot, duration_minutes: int):
        """Завершает игру и распределяет награды."""
        started_at_ts = None
        started_at_raw = await self.banzai_games.find_one({"_id": chat_id}, {"started_at": 1})
        if started_at_raw and "started_at" in started_at_raw:
            started_at_ts = started_at_raw["started_at"]

        last_user_id, last_user_ts = await self._get_last_user_and_ts(chat_id)

        # Проверяем валидность победителя
        winner_id = None
        if last_user_id and last_user_ts and started_at_ts:
            if last_user_ts >= started_at_ts:
                winner_id = last_user_id

        winner_name = None
        if winner_id:
            winner_name = await self._get_user_display(chat_id, bot, int(winner_id))

            # Распределяем награды
            try:
                # 1. Билет в лотерею
                await self.lottery_service.add_ticket(int(winner_id), source="banzai_win")

                # 2. Монеты
                await self.economy_service.process_game_win(int(winner_id), coins=500.0, xp=0, description="Banzai Win")

                # 3. TON (если есть)
                reward_ton = 0.0
                try:
                    rt = await self.banzai_games.find_one({"_id": chat_id}, {"reward_ton": 1})
                    if rt and "reward_ton" in rt:
                        reward_ton = float(rt["reward_ton"])
                except Exception:
                    pass

                if reward_ton > 0 and self.xrocket_service:
                    tid = f"banzai:{chat_id}:{int(winner_id)}:{int(time.time()*1000)}"
                    await self.xrocket_service.transfer_ton(
                        user_id_to=int(winner_id),
                        amount=reward_ton,
                        transfer_id=tid,
                        description="Banzai Reward"
                    )

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
                        Visuals.frame_line_left("🎫 1 Билет", w),
                        Visuals.frame_line_left("💰 +500 Coins", w),
                    ]
                    if reward_ton > 0:
                        lines.append(Visuals.frame_line_left(f"💎 +{reward_ton} TON", w))
                    lines.append(Visuals.frame_bottom_left(w))
                    text = "<pre>\n" + "\n".join(lines) + "\n</pre>"
                    await bot.send_message(int(winner_id), text, parse_mode="HTML")
                except Exception:
                    pass
            except Exception as e:
                logger.error(f"Error distributing Banzai rewards: {e}")

        # Обновляем интерфейс игры на финальный вид
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
        )

        # Unpin the game message when game finishes
        message_id = await self.get_game_message_id(chat_id)
        if message_id:
            await self.unpin_game_message(chat_id, message_id, bot)