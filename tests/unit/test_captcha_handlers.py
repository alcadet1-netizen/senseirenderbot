"""Капча: кнопка «я поставил», обновление реакции и выдача доступа."""

from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest
from aiogram.types import MessageReactionUpdated

from src.bot.handlers.captcha import cb_captcha_check, on_reaction
from src.services.captcha_service import CaptchaService

from tests.unit.test_captcha_service import FakeCollection


def build_service():
    return CaptchaService(NS(database=NS(captcha_states=FakeCollection())))


def make_callback(user_id=7, nonce="abc", message_id=555):
    bot = NS(
        edit_message_text=AsyncMock(),
        send_message=AsyncMock(),
    )
    callback = NS(
        from_user=NS(id=user_id, first_name="Player", is_bot=False),
        data=f"captcha:check:{nonce}",
        bot=bot,
        message=NS(chat=NS(id=user_id), message_id=message_id),
        answer=AsyncMock(),
    )
    return callback, bot


@pytest.mark.asyncio
async def test_button_passes_when_the_reaction_was_seen():
    service = build_service()
    state = await service.issue(7)
    await service.attach_message(7, 555)
    await service.record_reaction(7, 555, [{"emoji": state["reaction"]}])

    callback, bot = make_callback(nonce=state["nonce"])
    await cb_captcha_check(callback, NS(captcha_service=service))

    assert await service.is_passed(7) is True
    assert callback.answer.await_args.args[0] == "Проверка пройдена ✅"
    # Доступ открыт — показали меню и убрали кнопку.
    assert bot.edit_message_text.await_count == 1
    assert bot.send_message.await_count == 1


@pytest.mark.asyncio
async def test_button_refuses_without_the_reaction():
    service = build_service()
    state = await service.issue(7)
    await service.attach_message(7, 555)
    # Реакция была, но чужая.
    await service.record_reaction(7, 555, [{"emoji": "👍"}])

    callback, bot = make_callback(nonce=state["nonce"])
    await cb_captcha_check(callback, NS(captcha_service=service))

    assert await service.is_passed(7) is False
    assert "Не вижу нужную реакцию" in callback.answer.await_args.args[0]
    assert bot.send_message.await_count == 0, "доступа нет — меню не показываем"


@pytest.mark.asyncio
async def test_reaction_on_a_different_message_does_not_pass():
    service = build_service()
    state = await service.issue(7)
    await service.attach_message(7, 555)
    await service.record_reaction(7, 999, [{"emoji": state["reaction"]}])

    callback, _ = make_callback(nonce=state["nonce"])
    await cb_captcha_check(callback, NS(captcha_service=service))
    assert await service.is_passed(7) is False


@pytest.mark.asyncio
async def test_stale_button_does_not_pass():
    """Кнопка от прошлой попытки не должна работать на новой."""
    service = build_service()
    state = await service.issue(7)
    await service.record_reaction(7, 555, [{"emoji": state["reaction"]}])

    callback, _ = make_callback(nonce="old-nonce")
    await cb_captcha_check(callback, NS(captcha_service=service))

    assert await service.is_passed(7) is False
    assert "устарела" in callback.answer.await_args.args[0]


@pytest.mark.asyncio
async def test_expired_captcha_tells_the_player_to_restart():
    service = build_service()
    state = await service.issue(7)
    service.collection.docs[7]["expires_at"] = 1

    callback, bot = make_callback(nonce=state["nonce"])
    await cb_captcha_check(callback, NS(captcha_service=service))

    assert "Время вышло" in callback.answer.await_args.args[0]
    assert bot.edit_message_text.await_count == 1


@pytest.mark.asyncio
async def test_reaction_update_grants_access_immediately():
    service = build_service()
    state = await service.issue(7)
    await service.attach_message(7, 555)

    bot = NS(edit_message_text=AsyncMock(), send_message=AsyncMock())
    event = MessageReactionUpdated.model_validate(dict(
        chat=dict(id=7, type="private"),
        message_id=555,
        date=1,
        old_reaction=[dict(type="emoji", emoji="👍")],
        new_reaction=[dict(type="emoji", emoji=state["reaction"])],
        user=dict(id=7, is_bot=False, first_name="Player"),
    ))
    # bot у TelegramObject — read-only property над приватным полем,
    # поэтому подменяем именно поле.
    event._bot = bot

    await on_reaction(event, NS(captcha_service=service))

    assert await service.is_passed(7) is True
    bot.edit_message_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_wrong_reaction_update_does_not_grant_access():
    service = build_service()
    await service.issue(7)
    await service.attach_message(7, 555)

    bot = NS(edit_message_text=AsyncMock(), send_message=AsyncMock())
    event = MessageReactionUpdated.model_validate(dict(
        chat=dict(id=7, type="private"),
        message_id=555,
        date=1,
        old_reaction=[],
        new_reaction=[dict(type="emoji", emoji="🤮")],
        user=dict(id=7, is_bot=False, first_name="Player"),
    ))
    # bot у TelegramObject — read-only property над приватным полем,
    # поэтому подменяем именно поле.
    event._bot = bot

    await on_reaction(event, NS(captcha_service=service))

    assert await service.is_passed(7) is False
    bot.edit_message_text.assert_not_awaited()


# ---------------------------------------------------------------------------
# /start у нового игрока
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_start_shows_captcha_and_does_not_register_the_player():
    """Новый игрок при /start получает капчу, а профиль не создаётся."""
    from unittest.mock import patch

    from src.bot.handlers.user_commands import cmd_start

    service = build_service()
    container = NS(
        captcha_service=service,
        user_service=NS(get_or_create=AsyncMock()),
    )
    message = NS(
        from_user=NS(id=7, first_name="Player", username="player", last_name=None),
        chat=NS(id=7, type="private"),
        answer=AsyncMock(return_value=NS(message_id=42)),
        bot=NS(),
    )
    command = NS(args=None)

    await cmd_start(message, command, container)

    container.user_service.get_or_create.assert_not_awaited()
    message.answer.assert_awaited_once()
    assert "ПРОВЕРКА НА ЧЕЛОВЕКА" in message.answer.await_args.args[0]
    assert await service.is_passed(7) is False


@pytest.mark.asyncio
async def test_start_after_captcha_registers_the_player():
    """Прошедший капчу игрок при /start регистрируется как обычно."""
    from src.bot.handlers.user_commands import cmd_start

    service = build_service()
    await service.issue(7)
    await service.mark_passed(7)

    get_or_create = AsyncMock(return_value={"created": False, "user": {"coins": 0}})
    container = NS(
        captcha_service=service,
        user_service=NS(get_or_create=get_or_create),
    )
    message = NS(
        from_user=NS(id=7, first_name="Player", username="player", last_name=None),
        chat=NS(id=7, type="private"),
        answer=AsyncMock(return_value=NS(message_id=42)),
        bot=NS(),
    )

    await cmd_start(message, NS(args=None), container)

    get_or_create.assert_awaited_once()
