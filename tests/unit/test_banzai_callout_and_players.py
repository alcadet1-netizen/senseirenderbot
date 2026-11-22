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
    def __init__(self, docs, limit=None):
        self.docs = docs
        self._limit = limit

    def sort(self, key, direction):
        return FakeCursor(sorted(self.docs, key=lambda d: d[key], reverse=direction < 0), self._limit)

    def limit(self, count):
        return FakeCursor(self.docs, count)

    async def to_list(self, length=None):
        docs = self.docs[: self._limit] if self._limit else self.docs
        return docs[:length] if length else docs

    def __aiter__(self):
        docs = self.docs[: self._limit] if self._limit else self.docs
        self._iter = iter(docs)
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

    @staticmethod
    def _apply_match(docs, match):
        chat_id = match.get("chat_id")
        docs = [d for d in docs if d.get("chat_id") == chat_id]
        if match.get("is_bot") == {"$ne": True}:
            docs = [d for d in docs if not d.get("is_bot")]
        since = (match.get("timestamp") or {}).get("$gte") if isinstance(match.get("timestamp"), dict) else None
        if since is not None:
            docs = [d for d in docs if d.get("timestamp", 0) >= since]
        return docs

    def find(self, query, projection=None):
        return FakeCursor(self._apply_match(self.docs, query))

    def aggregate(self, pipeline):
        """Повторяет используемый сервисом конвейер: match → sort → group → limit."""
        docs = []
        limit = None
        for stage in pipeline:
            if "$match" in stage:
                docs = self._apply_match(self.docs, stage["$match"])
            elif "$sort" in stage:
                (key, direction), = stage["$sort"].items()
                docs = sorted(docs, key=lambda d: d.get(key, 0), reverse=direction < 0)
            elif "$group" in stage:
                grouped, seen = [], {}
                for doc in docs:
                    uid = doc[stage["$group"]["_id"].lstrip("$")]
                    if uid not in seen:
                        seen[uid] = True
                        grouped.append({"_id": uid, "ts": doc.get("timestamp")})
                docs = grouped
            elif "$limit" in stage:
                limit = stage["$limit"]
        return FakeCursor(docs, limit)

    async def find_one(self, query, projection=None, sort=None):
        chat_id = query.get("chat_id")
        docs = [d for d in self.docs if d.get("chat_id") == chat_id]
        if not docs:
            return None
        if sort:
            key, direction = sort[0]
            docs = sorted(docs, key=lambda d: d[key], reverse=direction < 0)
        return dict(docs[0])


class FakeUsers:
    """Коллекция users: только поле is_banned, как в сервисе."""

    def __init__(self, banned=()):
        self.banned = set(int(u) for u in banned)

    async def find_one(self, query, projection=None):
        uid = int(query.get("id"))
        if query.get("is_banned") is True and uid not in self.banned:
            return None
        if uid in self.banned:
            return {"id": uid, "is_banned": True}
        return {"id": uid, "is_banned": False}

    def find(self, query, projection=None):
        ids = query.get("id", {})
        wanted = ids.get("$in", []) if isinstance(ids, dict) else [ids]
        docs = [{"id": int(u)} for u in wanted
                if query.get("is_banned") is True and int(u) in self.banned]
        return FakeCursor(docs)


def build_service(doc=None, leader=(7, 1500), banned=()):
    """Собирает сервис с поддельным Mongo.

    ``leader`` — (user_id, timestamp) последнего сообщения; по умолчанию есть
    живой лидер, иначе оклик «осталась минута» отправлять некому.
    """
    from src.services.banzai_service import BanzaiService

    service = BanzaiService.__new__(BanzaiService)
    service.db = NS(users=FakeUsers(banned))
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
    service._dm_notified = {}
    service.banzai_results = NS(
        insert_one=AsyncMock(),
        count_documents=AsyncMock(return_value=0),
        find=lambda *a, **k: FakeCursor([]),
    )
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
    """Бот, который помнит, куда слал: в чат или в личку."""
    async def send_message(target, *args, **kwargs):
        return NS(message_id=len(bot.sent))

    bot = NS(
        id=42,
        sent=[],
        get_chat_member=AsyncMock(
            side_effect=lambda chat_id, uid: NS(
                user=NS(id=uid, username=f"player{uid}", full_name=f"Player {uid}")
            )
        ),
    )

    async def _send(target, text, **kwargs):
        bot.sent.append(target)
        return NS(message_id=len(bot.sent))

    bot.send_message = AsyncMock(side_effect=_send)

    def chat_messages():
        return [t for t in bot.sent if t == -100]

    bot.chat_messages = chat_messages
    return bot


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

    assert len(bot.chat_messages()) == 1, "в рамках одной тишины — один оклик в чат"
    assert service.banzai_games.doc["one_minute_callout_done"] is True


@pytest.mark.asyncio
async def test_one_minute_callout_returns_after_the_timer_was_reset():
    """Перебили — таймер пошёл заново, через 9 минут нужен новый оклик."""
    service = build_service(game_doc())
    bot = make_bot()

    await service._send_one_minute_callout(-100, bot, started_at_ts=1000)
    assert len(bot.chat_messages()) == 1

    # Игрок перебил: новый раунд тишины, флаг снят.
    await service.update_user_activity(-100, 8, is_bot=False)
    assert service.banzai_games.doc["one_minute_callout_done"] is False
    assert service.banzai_games.doc["silence_round"] == 1

    await service._send_one_minute_callout(-100, bot, started_at_ts=1000)
    assert len(bot.chat_messages()) == 2, "после перебоя оклик приходит снова"


@pytest.mark.asyncio
async def test_one_minute_callout_survives_many_resets():
    """Три перебоя подряд — три оклика, по одному на раунд."""
    service = build_service(game_doc())
    bot = make_bot()

    for expected in range(1, 4):
        await service._send_one_minute_callout(-100, bot, started_at_ts=1000)
        assert len(bot.chat_messages()) == expected
        # Пока флаг стоит, повторный тик молчит.
        await service._send_one_minute_callout(-100, bot, started_at_ts=1000)
        assert len(bot.chat_messages()) == expected
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
    assert bot.chat_messages() == [], "оклик за этот раунд уже отправлен"


@pytest.mark.asyncio
async def test_callout_is_skipped_when_game_is_gone():
    service = build_service(None)
    bot = make_bot()
    await service._send_one_minute_callout(-100, bot, started_at_ts=1000)
    assert bot.sent == []


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


# ---------------------------------------------------------------------------
# 4. Участники ЛС-напоминания — только текущая игра
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dm_reminder_goes_only_to_players_of_this_game():
    """Напоминание получают только те, кто сделал ход в текущей партии."""
    service = build_service(game_doc(started_at=1000), leader=None)
    bot = make_bot()
    service.banzai_chat_activity.docs.extend([
        {"chat_id": -100, "user_id": 7, "timestamp": 1500},    # играет
        {"chat_id": -100, "user_id": 9, "timestamp": 1900},    # играет
        {"chat_id": -100, "user_id": 11, "timestamp": 500},    # писал до старта
        {"chat_id": -100, "user_id": 13, "timestamp": 1700},   # забанен
    ])
    service.db = NS(users=FakeUsers(banned={13}))

    sent = await service._notify_participants_dm(-100, bot, started_at_ts=1000, leader_id=9)

    assert sent == 2
    assert sorted(bot.sent) == [7, 9]
    assert 11 not in bot.sent, "кто писал до старта — не участник"
    assert 13 not in bot.sent, "забаненному не пишем"


@pytest.mark.asyncio
async def test_dm_reminder_is_sent_once_per_game():
    """Повторный оклик не должен снова писать в личку тем же людям."""
    service = build_service(game_doc(), leader=None)
    bot = make_bot()
    service.banzai_chat_activity.docs.append(
        {"chat_id": -100, "user_id": 7, "timestamp": 1500}
    )

    assert await service._notify_participants_dm(-100, bot, 1000, 7) == 1
    assert await service._notify_participants_dm(-100, bot, 1000, 7) == 0
    assert bot.sent == [7]


@pytest.mark.asyncio
async def test_dm_reminder_survives_blocked_bot():
    """Если игрок не открывал чат с ботом, игра не падает."""
    from aiogram.exceptions import TelegramForbiddenError

    service = build_service(game_doc(), leader=None)
    bot = make_bot()
    service.banzai_chat_activity.docs.extend([
        {"chat_id": -100, "user_id": 7, "timestamp": 1500},
        {"chat_id": -100, "user_id": 9, "timestamp": 1600},
    ])

    async def _send(target, text, **kwargs):
        if target == 7:
            raise TelegramForbiddenError(method=NS(), message="bot was blocked by the user")
        bot.sent.append(target)
        return NS(message_id=1)

    bot.send_message = AsyncMock(side_effect=_send)

    sent = await service._notify_participants_dm(-100, bot, 1000, 9)
    assert sent == 1 and bot.sent == [9]


# ---------------------------------------------------------------------------
# 5. Победитель не может быть забаненным или из прошлой игры
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_banned_player_cannot_win():
    service = build_service(game_doc(), leader=None)
    service.banzai_chat_activity.docs.append(
        {"chat_id": -100, "user_id": 13, "timestamp": 1800}
    )
    service.db = NS(users=FakeUsers(banned={13}))

    uid, _ = await service._get_last_user_and_ts(-100, since_ts=1000)
    assert uid is None, "забаненный не может стать королём"


@pytest.mark.asyncio
async def test_player_from_before_the_game_is_ignored():
    service = build_service(game_doc(), leader=None)
    service.banzai_chat_activity.docs.append(
        {"chat_id": -100, "user_id": 11, "timestamp": 500}
    )
    uid, _ = await service._get_last_user_and_ts(-100, since_ts=1000)
    assert uid is None


# ---------------------------------------------------------------------------
# 6. Окно не вылезает за рамку
# ---------------------------------------------------------------------------

def test_frame_lines_never_exceed_the_frame_width():
    from src.core.visuals import Visuals

    width = 30
    frame_width = Visuals._vwidth_str(Visuals.frame_top_left(width))
    samples = [
        "📊 Сбросов: 128 | Люди: 23",
        "◦ @abcdefghijklmnopqrstuvwxyz · 999s ago",
        "👑 KING: @someone_with_a_very_long_username",
        "🤫 Цель: 1440 мин тишины",
    ]
    for text in samples:
        line = Visuals.frame_line_left(text, width)
        assert Visuals._vwidth_str(line) <= frame_width, (text, line)
