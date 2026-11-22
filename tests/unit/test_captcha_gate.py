"""Капча-гейт: кого пускаем в личку, кого нет и что показываем."""

from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest
from aiogram.types import Message, MessageReactionUpdated, User

from src.bot.middlewares.captcha_gate import CaptchaGateMiddleware

CONTAINER = object()  # подменяется ниже через свойства


class FakeService:
    def __init__(self, passed=False, reaction="🔥"):
        self.passed = passed
        self.reaction = reaction
        self.issued = 0
        self.attached = None
        self.keep_active = []

    async def is_passed(self, user_id):
        return self.passed

    async def issue(self, user_id, *, keep_active: bool = False):
        self.issued += 1
        self.keep_active.append(keep_active)
        return {"reaction": self.reaction, "nonce": "abc123", "status": "pending",
                "message_id": None}

    async def attach_message(self, user_id, message_id):
        self.attached = (user_id, message_id)


def private_message(user_id=7, text="привет", is_bot=False):
    return Message.model_validate(dict(
        message_id=1, date=1,
        chat=dict(id=user_id, type="private"),
        from_user=dict(id=user_id, is_bot=is_bot, first_name="Player"),
        text=text,
    ))


def group_message(text="привет"):
    return Message.model_validate(dict(
        message_id=1, date=1,
        chat=dict(id=-100, type="supergroup"),
        from_user=dict(id=7, is_bot=False, first_name="Player"),
        text=text,
    ))


def make_container(service):
    return NS(captcha_service=service)


@pytest.mark.asyncio
async def test_unverified_player_gets_captcha_instead_of_handler():
    service = FakeService(passed=False)
    handler = AsyncMock(return_value="handled")
    message = private_message()
    object.__setattr__(message, "answer", AsyncMock(return_value=NS(message_id=99)))

    result = await CaptchaGateMiddleware(make_container(service))(handler, message, {})

    assert result is None, "обработчик не должен вызываться"
    handler.assert_not_awaited()
    message.answer.assert_awaited_once()
    text = message.answer.await_args.args[0]
    assert "ПРОВЕРКА НА ЧЕЛОВЕКА" in text
    assert "🔥" in text
    assert service.attached == (7, 99), "сообщение запоминается для проверки"


@pytest.mark.asyncio
async def test_verified_player_reaches_handler():
    service = FakeService(passed=True)
    handler = AsyncMock(return_value="handled")

    result = await CaptchaGateMiddleware(make_container(service))(handler, private_message(), {})

    assert result == "handled"
    handler.assert_awaited_once()
    assert service.issued == 0


@pytest.mark.asyncio
async def test_group_chat_is_never_blocked():
    service = FakeService(passed=False)
    handler = AsyncMock(return_value="handled")

    result = await CaptchaGateMiddleware(make_container(service))(handler, group_message(), {})

    assert result == "handled"
    assert service.issued == 0, "в группах капча не нужна"


@pytest.mark.asyncio
async def test_bots_are_never_blocked():
    service = FakeService(passed=False)
    handler = AsyncMock(return_value="handled")

    result = await CaptchaGateMiddleware(make_container(service))(
        handler, private_message(user_id=42, is_bot=True), {}
    )

    assert result == "handled"


@pytest.mark.asyncio
async def test_command_cannot_bypass_captcha():
    """До прохождения капчи команда не выполняется — иначе её легко обойти."""
    service = FakeService(passed=False)
    handler = AsyncMock(return_value="handled")
    message = private_message(text="/daily")
    object.__setattr__(message, "answer", AsyncMock(return_value=NS(message_id=1)))

    result = await CaptchaGateMiddleware(make_container(service))(handler, message, {})

    assert result is None
    handler.assert_not_awaited()


@pytest.mark.asyncio
async def test_start_command_is_allowed_through():
    """/start должен дойти до своего хендлера: он сам показывает капчу."""
    service = FakeService(passed=False)
    handler = AsyncMock(return_value="handled")

    result = await CaptchaGateMiddleware(make_container(service))(
        handler, private_message(text="/start"), {}
    )

    assert result == "handled"


@pytest.mark.asyncio
async def test_callback_queries_are_passed_through():
    """Кнопки капчи обрабатываются своими хендлерами."""
    service = FakeService(passed=False)
    handler = AsyncMock(return_value="handled")
    callback = NS(data="captcha:check:abc123", from_user=NS(id=7))

    result = await CaptchaGateMiddleware(make_container(service))(handler, callback, {})

    assert result == "handled"


@pytest.mark.asyncio
async def test_broken_service_does_not_lock_the_player_out():
    """Ошибка проверки не должна запирать живого игрока в капче."""
    service = FakeService()
    service.is_passed = AsyncMock(side_effect=RuntimeError("db down"))
    handler = AsyncMock(return_value="handled")

    result = await CaptchaGateMiddleware(make_container(service))(handler, private_message(), {})

    assert result == "handled"


@pytest.mark.asyncio
async def test_missing_service_fails_open():
    handler = AsyncMock(return_value="handled")
    result = await CaptchaGateMiddleware(NS(captcha_service=None))(handler, private_message(), {})
    assert result == "handled"


@pytest.mark.asyncio
async def test_admins_skip_captcha(monkeypatch):
    from src.bot.middlewares import captcha_gate

    # settings — pydantic-модель без сеттера, поэтому подменяем целиком.
    monkeypatch.setattr(
        captcha_gate, "settings", NS(admin_ids=[7]), raising=True
    )
    service = FakeService(passed=False)
    handler = AsyncMock(return_value="handled")

    result = await CaptchaGateMiddleware(make_container(service))(
        handler, private_message(user_id=7), {}
    )

    assert result == "handled"
    assert service.issued == 0
