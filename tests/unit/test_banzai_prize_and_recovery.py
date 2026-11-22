"""Banzai: приз из SenseiBank, восстановление после рестарта, статистика."""

from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest

from tests.unit.test_banzai_callout_and_players import (
    FakeCursor,
    build_service,
    game_doc,
    make_bot,
)


class TxnContext:
    """Сессия Mongo: контекстный менеджер с with_transaction внутри."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def with_transaction(self, callback, **kwargs):
        return await callback(None)


class Txn:
    async def start_session(self):
        return TxnContext()


@pytest.mark.asyncio
async def test_bank_pays_the_prize_without_minting():
    """Победа списывает 500 Coin из банка и зачисляет их игроку."""
    from src.services.economy_service import EconomyService

    balances = {"single": {"_id": "single", "coins": 800.0},
                "main": {"_id": "main", "balance": 0.0}}
    user = {"id": 7, "coins": 10.0, "is_banned": False}
    journal = []

    class Bank:
        async def find_one(self, query, session=None):
            return dict(balances[query["_id"]])

        async def update_one(self, query, update, session=None):
            doc = balances[query["_id"]]
            for field, value in update["$inc"].items():
                doc[field] = doc.get(field, 0) + value
            return NS(matched_count=1, modified_count=1)

    class Users:
        async def find_one(self, query, session=None):
            return dict(user)

        async def update_one(self, query, update, session=None):
            user["coins"] += update["$inc"]["coins"]
            return NS(matched_count=1, modified_count=1)

    svc = EconomyService.__new__(EconomyService)
    svc.bank = Bank()
    svc.users = Users()
    svc.transactions = NS(insert_one=AsyncMock(side_effect=lambda doc, **k: journal.append(doc)))
    svc.mongo_client = NS(database=NS(client=Txn()))

    result = await svc.pay_game_reward_from_bank(7, 500.0, description="Banzai Win")

    assert result["success"] is True
    assert result["from_bank"] is True
    assert balances["single"]["coins"] == 300.0
    assert user["coins"] == 510.0
    assert journal[0]["funding_source"] == "senseibank"


@pytest.mark.asyncio
async def test_empty_bank_refuses_instead_of_printing_coins():
    from src.services.economy_service import EconomyService

    class Bank:
        async def find_one(self, query, session=None):
            return {"_id": query["_id"], "coins": 100.0, "balance": 0.0}

    class Users:
        async def find_one(self, query, session=None):
            return {"id": 7, "coins": 0.0, "is_banned": False}

        async def update_one(self, *a, **k):
            raise AssertionError("игрока нельзя кредитовать при пустом банке")

    svc = EconomyService.__new__(EconomyService)
    svc.bank = Bank()
    svc.users = Users()
    svc.transactions = NS(insert_one=AsyncMock())
    svc.mongo_client = NS(database=NS(client=Txn()))

    result = await svc.pay_game_reward_from_bank(7, 500.0)
    assert result["success"] is False
    assert result["reason"] == "insufficient_bank"


@pytest.mark.asyncio
async def test_banned_player_is_not_paid():
    from src.services.economy_service import EconomyService

    class Bank:
        async def find_one(self, query, session=None):
            return {"_id": query["_id"], "coins": 1000.0, "balance": 1000.0}

    class Users:
        async def find_one(self, query, session=None):
            return {"id": 7, "coins": 0.0, "is_banned": True}

    svc = EconomyService.__new__(EconomyService)
    svc.bank = Bank()
    svc.users = Users()
    svc.transactions = NS(insert_one=AsyncMock())
    svc.mongo_client = NS(database=NS(client=Txn()))

    result = await svc.pay_game_reward_from_bank(7, 500.0)
    assert result == {"success": False, "reason": "banned"}


class FakeGamesCollection:
    def __init__(self, docs):
        self.docs = {d["_id"]: dict(d) for d in docs}
        self.deleted = []

    def find(self, query):
        return FakeCursor([d for d in self.docs.values() if d.get("active") is True])

    async def update_one(self, query, update, **kwargs):
        doc = self.docs.get(query["_id"])
        if doc is None:
            return NS(matched_count=0)
        doc.update(update.get("$set") or {})
        return NS(matched_count=1)

    async def delete_one(self, query):
        self.deleted.append(query["_id"])
        self.docs.pop(query["_id"], None)
        return NS(deleted_count=1)


@pytest.mark.asyncio
async def test_stale_game_is_dropped_instead_of_restored(monkeypatch):
    """Партия, пережившая простой дольше допустимого, закрывается."""
    import time as _time

    started = int(_time.time()) - 10_000

    service = build_service(game_doc(started_at=started, duration_minutes=10))
    service.banzai_games = FakeGamesCollection([
        {"_id": -100, "active": True, "started_at": started, "duration_minutes": 10},
    ])
    service.banzai_chat_activity = NS(delete_many=AsyncMock())
    service.banzai_callouts = NS(delete_many=AsyncMock())

    monkeypatch.setattr(
        "src.services.banzai_service.asyncio.create_task",
        lambda coro: (coro.close(), NS(done=lambda: True))[1],
    )

    restored = await service.restore_workers(make_bot())

    assert restored == 0, "старая партия не восстанавливается"
    assert service.banzai_games.deleted == [-100]


@pytest.mark.asyncio
async def test_fresh_game_restarts_its_clock(monkeypatch):
    """Свежая партия восстанавливается, но отсчёт идёт с рестарта."""
    import time as _time

    now = int(_time.time())
    started = now - 60

    service = build_service(game_doc(started_at=started, duration_minutes=10))
    service.banzai_games = FakeGamesCollection([
        {"_id": -100, "active": True, "started_at": started, "duration_minutes": 10},
    ])

    def fake_task(coro):
        coro.close()
        return NS(done=lambda: False)

    monkeypatch.setattr("src.services.banzai_service.asyncio.create_task", fake_task)

    restored = await service.restore_workers(make_bot())

    assert restored == 1
    doc = service.banzai_games.docs[-100]
    assert doc["started_at"] >= now - 2, "старт партии сдвинут к рестарту"
    assert doc["one_minute_callout_done"] is False, "оклик снова доступен"


@pytest.mark.asyncio
async def test_finished_game_is_recorded_for_history():
    service = build_service(game_doc())
    service.banzai_results = NS(insert_one=AsyncMock())

    await service._record_result(
        chat_id=-100, winner_id=7, duration_minutes=10, started_at_ts=1000
    )

    doc = service.banzai_results.insert_one.await_args.args[0]
    assert doc["winner_id"] == 7
    assert doc["chat_id"] == -100
    assert doc["duration_minutes"] == 10


@pytest.mark.asyncio
async def test_player_stats_count_only_own_wins():
    service = build_service(game_doc())

    async def count(query):
        return 3 if query == {"winner_id": 7} else 0

    service.banzai_results = NS(count_documents=AsyncMock(side_effect=count))
    stats = await service.get_player_stats(7)
    assert stats["wins"] == 3


@pytest.mark.asyncio
async def test_recent_results_are_empty_without_history():
    service = build_service(game_doc())
    service.banzai_results = NS(find=lambda *a, **k: FakeCursor([]))
    assert await service.get_recent_results(-100) == []
