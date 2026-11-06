from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.exceptions import TelegramBadRequest, TelegramNotFound, TelegramRetryAfter, TelegramNetworkError

from src.bot.native_widgets import SendWidget
from src.bot.widget_diagnostics import describe_failure, redact
from src.bot.handlers.widget_check import cmd_widget_check


def error(cls, message):
    return cls(method=SendWidget(chat_id=1, html=''), message=message)


@pytest.mark.parametrize('cls,message,category', [
    (TelegramNotFound, 'Not Found', 'method_or_route'),
    (TelegramBadRequest, 'Bad Request: unknown method sendWidget', 'method_or_route'),
    (TelegramBadRequest, 'Bad Request: INPUT_MEDIA_WIDGET_TOO_LARGE', 'payload'),
    (TelegramBadRequest, 'Bad Request: wrong height', 'payload'),
    (TelegramBadRequest, 'Bad Request: not enough rights', 'permissions'),
    (TelegramBadRequest, 'Bad Request: chat not found', 'bad_request'),
    (TelegramNetworkError, 'connection lost', 'temporary'),
])
def test_failure_classification(cls, message, category):
    failure = describe_failure(error(cls, message))
    assert failure.category == category
    assert len(failure.reference) == 8
    assert 'Попытка не потрачена' in failure.public_text()
    assert 'клиент с поддержкой' not in failure.public_text()


def test_retry_after_is_not_missing_widget_support():
    exc = TelegramRetryAfter(method=SendWidget(chat_id=1, html=''), message='retry', retry_after=4)
    assert describe_failure(exc).category == 'rate_limit'


def test_error_logs_and_admin_text_redact_secrets(caplog):
    token = '123456:super_secret_bot_token_value'
    session = 'x' * 32
    raw = f'failed https://api.telegram.org/bot{token}/sendWidget token={token} session={session}\nnext'
    failure = describe_failure(error(TelegramBadRequest, raw), SimpleNamespace(token=token))
    for value in (failure.description, caplog.text, redact(raw)):
        assert token not in value
        assert session not in value
        assert 'api.telegram.org' not in value
    assert '\n' not in failure.description


def setup_probe(admin=True, private=True):
    settings = SimpleNamespace(admin_ids=[7] if admin else [], telegram_widget_beta=False,
                               BASE_DIR=Path(__file__).resolve().parents[2])
    container = SimpleNamespace(settings=settings)
    message = SimpleNamespace(from_user=SimpleNamespace(id=7),
                              chat=SimpleNamespace(id=7, type='private' if private else 'supergroup'),
                              bot=AsyncMock(), answer=AsyncMock())
    return message, container


@pytest.mark.asyncio
@pytest.mark.parametrize('admin,private', [(False, True), (True, False)])
async def test_probe_is_private_admin_only(admin, private):
    message, container = setup_probe(admin, private)
    await cmd_widget_check(message, container)
    message.bot.assert_not_called()
    assert 'только администратору' in message.answer.call_args.args[0]


@pytest.mark.asyncio
async def test_probe_success_no_economy_and_queries_disabled():
    message, container = setup_probe()
    await cmd_widget_check(message, container)
    requests = [call.args[0] for call in message.bot.call_args_list]
    assert len(requests) == 2
    assert all(isinstance(r, SendWidget) and not r.allow_queries and not r.is_shared for r in requests)
    assert 'TelegramWidget.ready' in requests[0].html
    assert 'data:image/jpeg;base64,' in requests[1].html
    assert 'не подтверждает' in message.answer.call_args.args[0]
    assert container.settings.telegram_widget_beta is False


@pytest.mark.asyncio
async def test_probe_missing_method_stops_after_minimal():
    message, container = setup_probe()
    message.bot.side_effect = error(TelegramNotFound, 'Not Found')
    await cmd_widget_check(message, container)
    assert message.bot.call_count == 1
    text = message.answer.call_args.args[0]
    assert 'method_or_route' in text and 'minimal' in text
    assert 'Not Found' in text
    assert container.settings.telegram_widget_beta is False


@pytest.mark.asyncio
async def test_probe_full_payload_failure_does_not_claim_method_missing():
    message, container = setup_probe()
    message.bot.side_effect = [{}, error(TelegramBadRequest, 'INPUT_MEDIA_WIDGET_TOO_LARGE')]
    await cmd_widget_check(message, container)
    text = message.answer.call_args.args[0]
    assert 'payload' in text and 'hedgehog' in text
    assert 'INPUT_MEDIA_WIDGET_TOO_LARGE' in text
    assert 'method_or_route' not in text
