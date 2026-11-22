"""Капча на входе: сервис, проверка реакции, срок жизни и лимит промахов."""

from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest

from src.services.captcha_service import (
    CAPTCHA_TTL_SECONDS,
    MAX_ATTEMPTS,
    CaptchaService,
)


class FakeCollection:
    """Одна коллекция в памяти с нужным сервису набором операций."""

    def __init__(self):
        self.docs = {}

    async def find_one(self, query):
        doc = self.docs.get(query.get("user_id"))
        return dict(doc) if doc else None

    async def update_one(self, query, update, upsert=False):
        uid = query["user_id"]
        doc = self.docs.setdefault(uid, {"user_id": uid})
        for key, value in (update.get("$set") or {}).items():
            doc[key] = value
        for key, value in (update.get("$inc") or {}).items():
            doc[key] = doc.get(key, 0) + value
        return NS(matched_count=1, modified_count=1)

    async def find_one_and_update(self, query, update, upsert=False, return_document=None):
        uid = query["user_id"]
        doc = self.docs.setdefault(uid, {"user_id": uid})
        for key, value in (update.get("$inc") or {}).items():
            doc[key] = doc.get(key, 0) + value
        return dict(doc)

    async def delete_one(self, query):
        self.docs.pop(query.get("user_id"), None)
        return NS(deleted_count=1)

    def create_index(self, *args, **kwargs):
        return "ok"


def build_service():
    client = NS(database=NS(captcha_states=FakeCollection()))
    return CaptchaService(client)


@pytest.mark.asyncio
async def test_new_player_is_not_passed_and_gets_a_reaction():
    svc = build_service()
    assert await svc.is_passed(7) is False

    state = await svc.issue(7)
    assert state["reaction"] in __import__(
        "src.services.captcha_service", fromlist=["CAPTCHA_REACTIONS"]
    ).CAPTCHA_REACTIONS
    assert state["status"] == "pending"
    assert state["expires_at"] - state["created_at"] == CAPTCHA_TTL_SECONDS


@pytest.mark.asyncio
async def test_correct_reaction_passes_and_sticks():
    svc = build_service()
    state = await svc.issue(7)

    result = await svc.verify(7, new_reactions=[{"emoji": state["reaction"]}], message_id=None)

    assert result["ok"] is True
    assert await svc.is_passed(7) is True

    # Повторная проверка ничего не ломает и не считает промах.
    again = await svc.verify(7, new_reactions=[])
    assert again == {"ok": True, "reason": "already"}


@pytest.mark.asyncio
async def test_wrong_reaction_does_not_pass_and_counts_attempts():
    svc = build_service()
    state = await svc.issue(7)

    result = await svc.verify(7, new_reactions=[{"emoji": "🤮"}])
    assert result["ok"] is False
    assert result["reason"] == "wrong_reaction"
    assert result["attempts_left"] == MAX_ATTEMPTS - 1
    assert await svc.is_passed(7) is False


@pytest.mark.asyncio
async def test_too_many_failures_block_further_checks():
    svc = build_service()
    await svc.issue(7)

    for _ in range(MAX_ATTEMPTS):
        await svc.verify(7, new_reactions=[{"emoji": "🤮"}])

    blocked = await svc.verify(7, new_reactions=[{"emoji": "🔥"}])
    assert blocked["ok"] is False
    assert blocked["reason"] == "too_many"

    # Новая попытка сбрасывает счётчик.
    await svc.issue(7)
    fresh = await svc.get_state(7)
    assert fresh["attempts"] == 0
    assert fresh["status"] == "pending"


@pytest.mark.asyncio
async def test_expired_captcha_is_not_accepted():
    svc = build_service()
    state = await svc.issue(7)
    # Просрочиваем вручную.
    stored = svc.collection.docs[7]
    stored["expires_at"] = 1

    result = await svc.verify(7, new_reactions=[{"emoji": state["reaction"]}])
    assert result["ok"] is False
    assert result["reason"] == "expired"


@pytest.mark.asyncio
async def test_reaction_on_another_message_does_not_count():
    svc = build_service()
    state = await svc.issue(7)
    await svc.attach_message(7, message_id=555)

    result = await svc.verify(
        7, new_reactions=[{"emoji": state["reaction"]}], message_id=999
    )
    assert result["ok"] is False
    assert result["reason"] == "wrong_message"


@pytest.mark.asyncio
async def test_recorded_reaction_is_visible_to_the_button():
    """Кнопка читает то, что записало обновление реакции."""
    svc = build_service()
    state = await svc.issue(7)
    await svc.attach_message(7, 555)

    await svc.record_reaction(7, 555, [{"emoji": state["reaction"]}])

    stored = await svc.get_state(7)
    assert stored["seen_message_id"] == 555
    assert stored["seen_reactions"] == [state["reaction"]]


@pytest.mark.asyncio
async def test_state_read_error_does_not_lock_the_player_out():
    """Если база недоступна, is_passed честно отвечает False, но не падает."""
    svc = build_service()

    async def boom(query):
        raise RuntimeError("db down")

    svc.collection.find_one = boom
    assert await svc.is_passed(7) is False


@pytest.mark.asyncio
async def test_reactions_contain_handles_objects_and_dicts():
    svc = build_service()
    obj = NS(emoji="🔥")
    assert svc.reactions_contain([obj], "🔥") is True
    assert svc.reactions_contain([{"emoji": "🔥"}], "🔥") is True
    assert svc.reactions_contain([{"emoji": "👍"}], "🔥") is False
    assert svc.reactions_contain(None, "🔥") is False
    assert svc.reactions_contain([NS(emoji="👍"), obj], "🔥") is True
