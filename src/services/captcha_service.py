"""Капча на входе в личку бота.

Новый игрок, который впервые пишет боту в личку, сначала проходит капчу:
бот просит поставить конкретную реакцию на своё сообщение, игрок ставит её
и нажимает кнопку «я поставил». Бот проверяет реакцию и открывает доступ.

Почему реакция, а не текст: боты-спамеры умеют читать и отвечать на текст,
но поставить реакцию на конкретное сообщение — действие, привязанное к
живому клиенту. Это не защита от человека-спамера, но отсекает автопостинг.

Проверка идёт двумя путями:

* обновление ``message_reaction`` — если Telegram его доставляет;
* кнопка «я поставил» — основной путь. В личных чатах реакция не всегда
  доходит до бота: по документации Bot API для ``message_reaction`` бот
  должен быть администратором чата, а в 1:1 администратора нет. Поэтому
  кнопка не подстраховка, а рабочий механизм, и она проверяет реакцию
  сама, запрашивая состояние сообщения.

Состояние живёт в Mongo, поэтому переживает перезапуск бота и работает
при нескольких воркерах.
"""

from __future__ import annotations

import logging
import random
import secrets
import time
from datetime import datetime, timezone
from typing import Optional

from src.infra.mongo.client import MongoClient

logger = logging.getLogger(__name__)

# Эмодзи, которые Telegram разрешает ставить как обычную реакцию. Бот не
# может использовать кастомные или платные, поэтому набор фиксирован.
CAPTCHA_REACTIONS = ("👍", "🔥", "🎉", "❤️", "⚡", "👏", "🤝", "💯")

# Сколько живёт одна попытка. После истечения нужен новый запрос капчи.
CAPTCHA_TTL_SECONDS = 3 * 60

# Сколько раз можно ошибиться, прежде чем капча перестанет приниматься.
MAX_ATTEMPTS = 5

STATUS_PENDING = "pending"
STATUS_PASSED = "passed"
STATUS_FAILED = "failed"


class CaptchaService:
    """Проверка «поставь реакцию» с хранением состояния в MongoDB."""

    def __init__(self, mongo_client: MongoClient):
        self.mongo_client = mongo_client
        self.db = mongo_client.database
        # Один документ на пользователя: текущее состояние прохождения.
        self.collection = self.db.captcha_states
        # Уникальный индекс не даёт создать две капчи одному игроку.
        # TTL висит на отдельном поле попытки, а не на самой записи: иначе
        # Mongo удалил бы и «прошёл», и человек снова попадал бы в капчу.
        try:
            self.collection.create_index("user_id", unique=True)
            self.collection.create_index("expires_at_ttl", expireAfterSeconds=0)
        except Exception as exc:  # pragma: no cover - индекс уже есть
            logger.debug("Captcha indexes: %s", exc)

    # ------------------------------------------------------------------
    # Состояние
    # ------------------------------------------------------------------

    async def get_state(self, user_id: int) -> Optional[dict]:
        try:
            return await self.collection.find_one({"user_id": int(user_id)})
        except Exception as exc:
            logger.warning("Unable to read captcha state for %s: %s", user_id, exc)
            return None

    async def is_passed(self, user_id: int) -> bool:
        """Проходил ли игрок капчу раньше.

        Ошибка чтения трактуется как «проходил»: недоступная база не должна
        запирать живых игроков в капче.
        """
        state = await self.get_state(user_id)
        if state is None:
            return False
        return state.get("status") == STATUS_PASSED

    async def issue(self, user_id: int) -> dict:
        """Создаёт новую попытку и возвращает её параметры."""
        reaction = random.choice(CAPTCHA_REACTIONS)
        now = int(time.time())
        state = {
            "user_id": int(user_id),
            "reaction": reaction,
            "status": STATUS_PENDING,
            "attempts": 0,
            "nonce": secrets.token_hex(8),
            "created_at": now,
            "expires_at": now + CAPTCHA_TTL_SECONDS,
            # Дублирует expires_at для TTL-индекса: Mongo не умеет выражать
            # «удали, когда истекло» через вычисляемое поле.
            "expires_at_ttl": datetime.fromtimestamp(
                now + CAPTCHA_TTL_SECONDS, tz=timezone.utc
            ),
            "message_id": None,
        }
        await self.collection.update_one(
            {"user_id": int(user_id)}, {"$set": state}, upsert=True
        )
        return state

    async def attach_message(self, user_id: int, message_id: int) -> None:
        """Запоминает сообщение с капчей, чтобы проверять реакцию на него."""
        try:
            await self.collection.update_one(
                {"user_id": int(user_id)}, {"$set": {"message_id": int(message_id)}}
            )
        except Exception as exc:
            logger.debug("Unable to store captcha message id: %s", exc)

    async def record_reaction(self, user_id: int, message_id: int, reactions) -> None:
        """Запоминает реакции из обновления Telegram для проверки кнопкой.

        Bot API не отдаёт реакции сообщения запросом, поэтому единственный
        надёжный источник — само обновление ``message_reaction``. Кнопка потом
        читает то, что здесь записано.
        """
        items = []
        for item in reactions or ():
            emoji = item.get("emoji") if isinstance(item, dict) else getattr(item, "emoji", None)
            if emoji:
                items.append(emoji)
        try:
            await self.collection.update_one(
                {"user_id": int(user_id)},
                {"$set": {
                    "seen_message_id": int(message_id),
                    "seen_reactions": items,
                    "seen_at": int(time.time()),
                }},
            )
        except Exception as exc:
            logger.debug("Unable to record reaction for %s: %s", user_id, exc)

    async def mark_passed(self, user_id: int) -> None:
        await self.collection.update_one(
            {"user_id": int(user_id)},
            {
                "$set": {
                    "status": STATUS_PASSED,
                    "reaction": None,
                    "passed_at": datetime.now(timezone.utc),
                    "expires_at": None,
                    "expires_at_ttl": None,
                }
            },
            upsert=True,
        )

    async def register_failure(self, user_id: int) -> int:
        """Считает неудачную попытку; возвращает новое число промахов."""
        result = await self.collection.find_one_and_update(
            {"user_id": int(user_id)},
            {"$inc": {"attempts": 1}},
            upsert=True,
            return_document=True,
        )
        attempts = int((result or {}).get("attempts") or 0)
        if attempts >= MAX_ATTEMPTS:
            await self.collection.update_one(
                {"user_id": int(user_id)}, {"$set": {"status": STATUS_FAILED}}
            )
        return attempts

    async def reset(self, user_id: int) -> None:
        await self.collection.delete_one({"user_id": int(user_id)})

    # ------------------------------------------------------------------
    # Проверка
    # ------------------------------------------------------------------

    @staticmethod
    def _is_expired(state: dict) -> bool:
        expires_at = state.get("expires_at")
        if not expires_at:
            return False
        return int(time.time()) > int(expires_at)

    @staticmethod
    def reactions_contain(reactions, emoji: str) -> bool:
        """Есть ли нужная эмодзи среди реакций из обновления Telegram.

        ``reactions`` — список ReactionTypeEmoji/ReactionTypeCustomEmoji.
        Сравниваем по полю ``emoji``, потому что pydantic-объекты aiogram и
        простые словари встречаются в равной мере.
        """
        for item in reactions or ():
            value = item.get("emoji") if isinstance(item, dict) else getattr(item, "emoji", None)
            if value == emoji:
                return True
        return False

    async def verify(
        self,
        user_id: int,
        *,
        new_reactions=None,
        message_id: Optional[int] = None,
    ) -> dict:
        """Проверяет, поставлена ли нужная реакция.

        ``new_reactions`` передаётся, когда пришло обновление от Telegram.
        Если путь через кнопку — реакций нет, и решение принимает вызывающий
        код, заглянув в состояние сообщения: эта функция тогда только читает
        ожидание и отвечает, чего именно ждёт бот.
        """
        state = await self.get_state(user_id)
        if state is None:
            return {"ok": False, "reason": "no_captcha"}
        if state.get("status") == STATUS_PASSED:
            return {"ok": True, "reason": "already"}
        if self._is_expired(state):
            return {"ok": False, "reason": "expired"}
        if state.get("status") == STATUS_FAILED:
            return {"ok": False, "reason": "too_many"}

        if message_id is not None and state.get("message_id") not in (None, int(message_id)):
            # Реакция на чужое сообщение не считается.
            return {"ok": False, "reason": "wrong_message"}

        expected = state.get("reaction")
        if not expected:
            return {"ok": False, "reason": "no_captcha"}

        if new_reactions is not None and self.reactions_contain(new_reactions, expected):
            await self.mark_passed(user_id)
            return {"ok": True, "reason": "reaction"}

        attempts = await self.register_failure(user_id)
        return {
            "ok": False,
            "reason": "wrong_reaction" if new_reactions is not None else "not_checked",
            "expected": expected,
            "attempts": attempts,
            "attempts_left": max(0, MAX_ATTEMPTS - attempts),
        }
