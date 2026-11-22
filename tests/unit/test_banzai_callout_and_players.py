"""Banzai: предупреждение за минуту и учёт только реальных игроков."""

from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest


class FakeGames:
    """Минимальная замена коллекции banzai_games."""

    def __init__(self, doc=None):
        self.doc = dict(doc or {})

    async def find_one(self, query, projection=None):
        if query.get("_id") != self.doc.get("_id"):
            return None
        if projection:
            return {k: self.doc[k] for k in projection if k in self.doc}
        return dict(self.doc)

    async def find_one_and_update(self, query, update, return_document=None):
        if query.get("_id") != self.doc.get("_id"):
            return None
        for key, value in (update.get("$set") or {}).items():
            self.doc[key] = value
        for key, value in (update.get("$inc") or {}).items():
            self.doc[key] = self.doc.get(key, 0) + value
        for key, value in (update.get("$addToSet") or {}).items():
            current = self.doc.setdefault(key, [])
            if value not in current:
                current.append(value)
        return dict(self.doc)

    async def update_one(self, query, update, upsert=False):
        if query.get("_id") != self.doc.get("_id"):
            return NS(matched_count=0, modified_count=0)
        for key, value in (update.get("$set") or {}).items():
            self.doc[key] = value
        return NS(matched_count=1, modified_count=1)


class FakeCallouts:
    """Коллекция претензий: уникальный индекс (chat_id, round) как в Mongo."""

    def __init__(self):
        self.docs = set()

    async def insert_one(self, doc):
        from pymongo.errors import DuplicateKeyError
        key = (doc["chat_id"], doc["round"])
        if key in self.docs:
            raise DuplicateKeyError("E11000 duplicate key error")
        self.docs.add(key)
        return NS(inserted_id=key)

    async def delete_many(self, query):
        self.docs = {k for k in self.docs if k[0] != query.get("chat_id")}
        return NS(deleted_count=0)


class FakeCursor:
    def __init__(self, docs):
        self.docs = docs

    def sort(self, key, direction):
        return FakeCursor(sorted(self.docs, key=lambda d: d[key], reverse=direction < 0))

    def limit(self, count):
        return self

    async def to_list(self, length=None):
        return self.docs

    def __aiter__(self):
        self._iter = iter(self.docs)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration


class FakeActivity:
    def __init__(self):
        self.docs = []

    async def insert_one(self, doc):
        self.docs.append(dict(doc))
        return NS(inserted_id=len(self.docs))

    def find(self, query, projection=None):
        chat_id = query.get("chat_id")
        docs = [d for d in self.docs if d.get("chat_id") == chat_id]
        want_no_bot = query.get("is_bot", "missing") == {"$ne": True}
        if want_no_bot:
            docs = [d for d in docs if not d.get("is_bot")]
        return FakeCursor(docs)

    async def find_one(self, query, projection=None, sort=None):
        chat_id = query.get("chat_id")
        docs = [d for d in self.docs if d.get("chat_id") == chat_id]
        if not docs:
            return None
        if sort:
            key, direction = sort[0]
            docs = sorted(docs, key=lambda d: d[key], reverse=direction < 0)
        return dict(docs[0])


def build_service(doc=None, leader=(7, 1500)):
    """Собирает сервис с поддельным Mongo.

    ``leader`` — (user_id, timestamp) последнего сообщения; по умолчанию есть
    живой лидер, иначе оклик «осталась минута» отправлять некому.
    """
    from src.services.banzai_service import BanzaiService

    service = BanzaiService.__new__(BanzaiService)
    service.banzai_games = FakeGames(doc)
    service.banzai_chat_activity = FakeActivity()
    if leader:
        service.banzai_chat_activity.docs.append(
            {"chat_id": (doc or {}).get("_id", -100), "user_id": leader[0], "timestamp": leader[1]}
        )
    service.banzai_callouts = FakeCallouts()
    service._workers = {}
    service._last_ui_text = {}
    service._last_ui_edit_ts = {}
    service._last_taunt_ts = {}
    service._user_display_cache = {}
    service._deletion_tasks = {}
    return service


def game_doc(**overrides):
    doc = {
        "_id": -100,
        "active": True,
        "duration_minutes": 10,
        "started_at": 1000,
        "last_activity": 1000,
        "reset_makers": [7],
        "silence_round": 0,
        "one_minute_callout_done": False,
        "message_id": None,
    }
    doc.update(overrides)
    return doc


def make_bot():
    return NS(
        id=42,
        send_message=AsyncMock(),
        get_chat_member=AsyncMock(
            side_effect=lambda chat_id, uid: NS(
                user=NS(id=uid, username=f"player{uid}", full_name=f"Player {uid}")
            )
        ),
    )


# ---------------------------------------------------------------------------
# 1. Участники: только настоящие игроки
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bot_message_is_not_counted_as_a_player():
    """Сообщение бота не попадает ни в активность, ни в счётчики игры."""
    service = build_service(game_doc(), leader=None)

    await service.update_user_activity(-100, 42, is_bot=True)

    assert service.banzai_chat_activity.docs == [], "активность бота не пишем"
    assert service.banzai_games.doc["reset_makers"] == [7], "бот не попал в игроки"
    assert service.banzai_games.doc["last_activity"] == 1000, "таймер не сброшен ботом"
    assert service.banzai_games.doc["silence_round"] == 0, "раунд не переключён ботом"


@pytest.mark.asyncio
async def test_human_message_still_counts():
    service = build_service(game_doc(), leader=None)
    await service.update_user_activity(-100, 8, is_bot=False)
    assert len(service.banzai_chat_activity.docs) == 1
    assert service.banzai_games.doc["reset_makers"] == [7, 8]
    assert service.banzai_games.doc["silence_round"] == 1


@pytest.mark.asyncio
async def test_bot_messages_do_not_show_up_in_contenders_or_people_count():
    """«Люди» и «Последние ходы» не показывают бота."""
    service = build_service(game_doc(), leader=None)

    await service.update_user_activity(-100, 42, is_bot=True)
    await service.update_user_activity(-100, 7, is_bot=False)

    state = await service.get_live_state(-100, bot=make_bot())
    assert [name for name, _ in state["contenders"]] == ["@player7"]
    assert state["reset_makers_count"] == 1


# ---------------------------------------------------------------------------
# 2. Оклик «осталась минута»
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_one_minute_callout_is_sent_once_per_silence_round():
    service = build_service(game_doc())
    bot = make_bot()

    await service._send_one_minute_callout(-100, bot, started_at_ts=1000)
    await service._send_one_minute_callout(-100, bot, started_at_ts=1000)

    assert bot.send_message.await_count == 1, "в рамках одной тишины — один оклик"
    assert service.banzai_games.doc["one_minute_callout_done"] is True


@pytest.mark.asyncio
async def test_one_minute_callout_returns_after_the_timer_was_reset():
    """Перебили — таймер пошёл заново, через 9 минут нужен новый оклик."""
    service = build_service(game_doc())
    bot = make_bot()

    await service._send_one_minute_callout(-100, bot, started_at_ts=1000)
    assert bot.send_message.await_count == 1

    # Игрок перебил: новый раунд тишины, флаг снят.
    await service.update_user_activity(-100, 8, is_bot=False)
    assert service.banzai_games.doc["one_minute_callout_done"] is False
    assert service.banzai_games.doc["silence_round"] == 1

    await service._send_one_minute_callout(-100, bot, started_at_ts=1000)
    assert bot.send_message.await_count == 2, "после перебоя оклик приходит снова"


@pytest.mark.asyncio
async def test_one_minute_callout_survives_many_resets():
    """Три перебоя подряд — три оклика, по одному на раунд."""
    service = build_service(game_doc())
    bot = make_bot()

    for expected in range(1, 4):
        await service._send_one_minute_callout(-100, bot, started_at_ts=1000)
        assert bot.send_message.await_count == expected
        # Пока флаг стоит, повторный тик молчит.
        await service._send_one_minute_callout(-100, bot, started_at_ts=1000)
        assert bot.send_message.await_count == expected
        await service.update_user_activity(-100, 8, is_bot=False)

    assert service.banzai_games.doc["silence_round"] == 3


@pytest.mark.asyncio
async def test_two_workers_cannot_send_the_same_callout_twice():
    """Флаг занят атомарной вставкой: второй воркер молчит."""
    service = build_service(game_doc())
    bot = make_bot()

    # Другой воркер уже забрал претензию на этот раунд.
    await service.banzai_callouts.insert_one({"chat_id": -100, "round": 0, "created_at": 0})

    await service._send_one_minute_callout(-100, bot, started_at_ts=1000)
    assert bot.send_message.await_count == 0, "оклик за этот раунд уже отправлен"


@pytest.mark.asyncio
async def test_callout_is_skipped_when_game_is_gone():
    service = build_service(None)
    bot = make_bot()
    await service._send_one_minute_callout(-100, bot, started_at_ts=1000)
    assert bot.send_message.await_count == 0


# ---------------------------------------------------------------------------
# 3. Middleware: сообщения ботов не доходят до сервиса
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_chat_activity_middleware_skips_bot_messages():
    from aiogram.types import Message
    from src.bot.middlewares.chat_activity import ChatActivityMiddleware

    msg = Message.model_validate(dict(
        message_id=1, date=1, chat=dict(id=-1001, type="supergroup"),
        from_user=dict(id=42, is_bot=True, first_name="SenseiBot"), text="hello",
    ))
    container = NS(
        chat_activity_service=NS(update_activity=AsyncMock()),
        banzai_service=NS(update_user_activity=AsyncMock()),
    )
    handler = AsyncMock(return_value="handled")

    assert await ChatActivityMiddleware()(handler, msg, {"container": container}) == "handled"
    container.banzai_service.update_user_activity.assert_not_awaited()


@pytest.mark.asyncio
async def test_chat_activity_middleware_still_records_humans():
    from aiogram.types import Message
    from src.bot.middlewares.chat_activity import ChatActivityMiddleware

    msg = Message.model_validate(dict(
        message_id=1, date=1, chat=dict(id=-1001, type="supergroup"),
        from_user=dict(id=7, is_bot=False, first_name="Player"), text="hello",
    ))
    container = NS(
        chat_activity_service=NS(update_activity=AsyncMock()),
        banzai_service=NS(update_user_activity=AsyncMock()),
    )
    handler = AsyncMock(return_value="handled")

    await ChatActivityMiddleware()(handler, msg, {"container": container})
    container.banzai_service.update_user_activity.assert_awaited_once_with(-1001, 7)


@pytest.mark.asyncio
async def test_bot_records_left_in_db_are_ignored():
    """Старые записи бота в коллекции активности не делают его лидером."""
    service = build_service(game_doc(), leader=None)
    service.banzai_chat_activity.docs.extend([
        {"chat_id": -100, "user_id": 42, "timestamp": 5000, "is_bot": True},
        {"chat_id": -100, "user_id": 7, "timestamp": 4000},
    ])

    uid, ts = await service._get_last_user_and_ts(-100)
    assert (uid, ts) == (7, 4000), "бот не может быть последним"

    state = await service.get_live_state(-100, bot=make_bot())
    assert [name for name, _ in state["contenders"]] == ["@player7"]
