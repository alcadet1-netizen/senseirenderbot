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
async def test_probe_success_no_economy_and_query_flag_matrix():
    message, container = setup_probe()
    await cmd_widget_check(message, container)
    requests = [call.args[0] for call in message.bot.call_args_list]
    assert len(requests) == 4
    assert all(isinstance(r, SendWidget) and not r.is_shared for r in requests)
    assert [r.allow_queries for r in requests] == [False, False, True, True]
    assert requests[0].html == requests[2].html
    assert requests[1].html == requests[3].html
    assert "diagnostic_no_game" in requests[3].html
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


@pytest.mark.parametrize('description', ['ConnectionError', 'TimeoutError'])
def test_legacy_mtproto_network_error_is_temporary_not_api_support(description):
    from src.infra.mtproto.widgets import MtprotoWidgetError
    assert describe_failure(MtprotoWidgetError(description)).category == 'temporary'


def test_background_transport_failure_is_not_html_or_network_failure():
    from src.infra.mtproto.widgets import MtprotoWidgetError
    failure = describe_failure(MtprotoWidgetError(
        'MTPROTO_UPDATES_FAILED: TypeNotFoundError constructor=0x1234abcd; layer=233',
        category='transport_runtime'))
    assert failure.category == 'transport_runtime'
    assert 'Фоновый обработчик' in failure.advice


@pytest.mark.asyncio
async def test_probe_detects_query_flag_rejection_without_blame_on_artwork():
    from src.infra.mtproto.widgets import MtprotoWidgetError
    message, container = setup_probe()
    message.bot.side_effect = [{}, {}, MtprotoWidgetError('INPUT_MEDIA_WIDGET_NOT_ALLOWED')]
    await cmd_widget_check(message, container)
    assert message.bot.call_count == 3
    text = message.answer.call_args.args[0]
    assert 'minimal_queries' in text and 'allow_queries=true' in text
    assert 'Отличается флаг запросов, а не оформление' in text
    assert 'widget_policy' in text
    assert 'не доказывает общий запрет' in text
    assert container.settings.telegram_widget_beta is False


def test_policy_error_is_not_proof_of_bot_wide_ban():
    from src.infra.mtproto.widgets import MtprotoWidgetError
    failure = describe_failure(MtprotoWidgetError('INPUT_MEDIA_WIDGET_NOT_ALLOWED'))
    assert failure.category == 'widget_policy'
    assert 'параметров нужно уточнить' in failure.advice
    assert 'этому боту или чату' not in failure.advice


@pytest.mark.asyncio
@pytest.mark.parametrize('status,permission,is_member,expected', [
    ('administrator', False, True, 'Право отправлять фото'),
    ('member', True, True, 'Право отправлять фото'),
    ('member', False, True, 'недоступна отправка'),
    ('member', None, True, 'не сообщил определённого'),
    ('restricted', False, True, 'недоступна отправка'),
    ('restricted', True, False, 'недоступна отправка'),
    ('restricted', True, True, 'Право отправлять фото'),
    ('left', True, False, 'недоступна отправка'),
    ('kicked', True, False, 'недоступна отправка'),
])
async def test_actual_group_photo_permissions(status, permission, is_member, expected):
    from src.bot.widget_diagnostics import widget_chat_advice
    message, _ = setup_probe(private=False)
    message.bot.get_chat_member.return_value = SimpleNamespace(
        status=status, is_member=is_member, can_send_photos=permission)
    message.bot.get_chat.return_value = SimpleNamespace(
        permissions=SimpleNamespace(can_send_photos=permission))
    text = await widget_chat_advice(message)
    assert expected in text
    message.bot.get_chat_member.assert_awaited_once_with(message.chat.id, message.bot.id)
    message.bot.promote_chat_member.assert_not_called()
    message.bot.set_chat_permissions.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize('exc', [TimeoutError(), error(TelegramNetworkError, 'network failed')])
async def test_photo_permission_lookup_failure_is_unknown_not_denial(exc):
    from src.bot.widget_diagnostics import widget_chat_advice
    message, _ = setup_probe(private=False)
    message.bot.get_chat_member.side_effect = exc
    assert 'Не удалось проверить' in await widget_chat_advice(message)


@pytest.mark.asyncio
async def test_explicit_group_probe_uses_actual_destination_and_hides_runtime():
    message, container = setup_probe(private=False)
    message.text = '/senseiwidgetcheck@bot here'
    message.chat.id = -100123
    message.bot.get_chat_member.return_value = SimpleNamespace(status='administrator')
    message.bot.get_chat.return_value = SimpleNamespace(permissions=None)
    container.native_widget_transport = SimpleNamespace(
        send_widget=AsyncMock(), diagnostic_status=lambda: 'PRIVATE_RUNTIME_DETAILS')
    await cmd_widget_check(message, container)
    requests = container.native_widget_transport.send_widget.call_args_list
    assert len(requests) == 4
    assert all(call.args[0] == message.chat.id for call in requests)
    assert [c.kwargs['allow_queries'] for c in requests] == [False, False, True, True]
    replies = '\n'.join(c.args[0] for c in message.answer.call_args_list)
    assert 'PRIVATE_RUNTIME_DETAILS' not in replies
    assert 'в этой группе' in replies
    assert 'Допуск в группе этим не проверен' not in replies


@pytest.mark.asyncio
async def test_group_probe_here_does_not_bypass_admin_check():
    message, container = setup_probe(admin=False, private=False)
    message.text = '/senseiwidgetcheck here'
    await cmd_widget_check(message, container)
    message.bot.assert_not_called()
    message.bot.get_chat_member.assert_not_called()


@pytest.mark.asyncio
async def test_group_policy_failure_is_scoped_to_actual_group():
    from src.infra.mtproto.widgets import MtprotoWidgetError
    message, container = setup_probe(private=False)
    message.text = '/senseiwidgetcheck here'
    message.bot.get_chat_member.return_value = SimpleNamespace(status='administrator')
    message.bot.get_chat.return_value = SimpleNamespace(permissions=None)
    message.bot.side_effect = MtprotoWidgetError('INPUT_MEDIA_WIDGET_NOT_ALLOWED')
    await cmd_widget_check(message, container)
    assert message.bot.call_count == 1
    text = message.answer.call_args.args[0]
    assert 'minimal' in text and 'этой группе' in text
    assert 'личному чату' not in text
