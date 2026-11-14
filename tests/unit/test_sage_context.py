from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
import json

import pytest

from src.bot.sage_context import SAGE_PATTERN, build_sage_question, selected_context, handle_sage, MAX_CONTEXT


def message(text='сенсей мудрец', reply=None, **kwargs):
    return NS(text=text, caption=None, reply_to_message=reply, quote=None, chat=NS(id=7),
              bot=NS(send_chat_action=AsyncMock()), message_id=99, answer=AsyncMock(), **kwargs)


@pytest.mark.parametrize('call', ['сенсей мудрец', 'мудрец сенсей', 'СЕНСЕЙ МУДРЕЦ, проанализируй',
    'мудрец сенсей\nпомоги', 'сэнсей мудрец: что думаешь?', 'сенсей, мудрец, объясни ему',
    'мудрец sensei твое мнение', 'помоги, сенсей мудрец'])
def test_aliases_use_replied_message_and_preserve_request(call):
    result = build_sage_question(message(call, NS(text='Исходное утверждение про налоги', reply_to_message=None)))
    assert 'Исходное утверждение про налоги' in result
    assert 'просьба пользователя' in result


@pytest.mark.parametrize('text', ['мудрец', 'сенсей', 'лжесенсей мудрец', 'сенсей мудрецы', 'просто привет'])
def test_no_accidental_sage_calls(text):
    assert build_sage_question(message(text)) is None


def test_quote_and_caption_are_included_without_identity():
    msg = message('мудрец сенсей объясни', NS(text=None, caption='Подпись к фото', from_user=NS(id=999, username='secret')))
    msg.quote = NS(text='Выбранный фрагмент')
    prompt = build_sage_question(msg)
    assert 'Выбранный фрагмент' in prompt and 'Подпись к фото' in prompt
    assert 'secret' not in prompt and '999' not in prompt
    assert 'не утверждай, что видел' in prompt


def test_context_is_bounded_and_cycles_stop():
    reply = NS(text='x' * 10000, reply_to_message=None)
    reply.reply_to_message = reply
    assert sum(len(x['text']) for x in selected_context(message(reply=reply))) <= MAX_CONTEXT
    assert len(selected_context(message(reply=reply))) == 1


def test_non_reply_question_still_works():
    assert 'почему небо синее' in build_sage_question(message('сенсей мудрец почему небо синее'))


@pytest.mark.asyncio
async def test_empty_call_and_unreadable_attachment_request_clarification_without_api():
    service = NS(ask_sensei=AsyncMock())
    msg = message(reply=NS(text=None, caption=None, reply_to_message=None))
    await handle_sage(msg, NS(digest_service=service))
    service.ask_sensei.assert_not_awaited()
    assert 'текстовое пояснение' in msg.answer.call_args.args[0]


@pytest.mark.asyncio
async def test_reply_request_calls_one_api_and_sends_plain_text():
    from src.bot.handlers.digest import cmd_sage
    from src.bot.handlers.triggers import trigger_sage_question
    for handler in (cmd_sage, trigger_sage_question):
        service = NS(ask_sensei=AsyncMock(return_value='<не HTML> Моё мнение'))
        msg = message('мудрец сенсей, объясни ему', NS(text='Вода кипит при любой температуре', reply_to_message=None))
        await handler(msg, NS(digest_service=service))
        assert 'Вода кипит' in service.ask_sensei.call_args.args[0]
        service.ask_sensei.assert_awaited_once()
        assert msg.answer.call_args.kwargs['parse_mode'] is None
        assert msg.answer.call_args.args[0] == '<не HTML> Моё мнение'


@pytest.mark.asyncio
async def test_typing_failure_does_not_block_answer_and_api_error_is_safe():
    msg = message('сенсей мудрец помоги с задачей')
    msg.bot.send_chat_action.side_effect = RuntimeError('network')
    service = NS(ask_sensei=AsyncMock(side_effect=RuntimeError('secret-key')))
    await handle_sage(msg, NS(digest_service=service))
    service.ask_sensei.assert_awaited_once()
    assert 'secret-key' not in msg.answer.call_args.args[0]


@pytest.mark.asyncio
async def test_caption_trigger_and_output_length_limit():
    msg = message(None)
    msg.caption = 'сенсей мудрец, помоги решить задачу про проценты'
    await handle_sage(msg, NS(digest_service=NS(ask_sensei=AsyncMock(return_value='y'*12000))))
    assert msg.answer.await_count == 2
    assert all(len(c.args[0]) <= 3500 for c in msg.answer.call_args_list)


@pytest.mark.asyncio
@pytest.mark.parametrize('reason', [
    'Bad Request: message to be replied not found',
    'Bad Request: chat not found',
    'Bad Request: message thread not found',
])
async def test_deleted_or_missing_message_does_not_raise_or_send_orphan(reason):
    from aiogram.exceptions import TelegramBadRequest
    from aiogram.methods import SendMessage
    msg = message('сенсей мудрец объясни смысл слова дзен')
    msg.answer = AsyncMock()
    msg.answer.side_effect = TelegramBadRequest(method=SendMessage(chat_id=7, text='x'), message=reason)
    await handle_sage(msg, NS(digest_service=NS(ask_sensei=AsyncMock(return_value='x' * 6000))))
    msg.answer.assert_awaited_once()
    msg.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_network_timeout_never_retries_potentially_delivered_answer():
    from aiogram.exceptions import TelegramNetworkError
    from aiogram.methods import SendMessage
    msg = message('мудрец сенсей помоги решить задачу')
    msg.answer.side_effect = TelegramNetworkError(method=SendMessage(chat_id=7, text='x'), message='timeout')
    await handle_sage(msg, NS(digest_service=NS(ask_sensei=AsyncMock(return_value='answer'))))
    msg.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_deleted_target_for_usage_hint_is_also_safe():
    from aiogram.exceptions import TelegramBadRequest
    from aiogram.methods import SendMessage
    msg = message()
    msg.answer.side_effect = TelegramBadRequest(method=SendMessage(chat_id=7, text='x'), message='message to be replied not found')
    service = NS(ask_sensei=AsyncMock())
    await handle_sage(msg, NS(digest_service=service))
    service.ask_sensei.assert_not_awaited()


def test_inaccessible_reply_object_needs_no_fetch_or_assumed_text():
    msg = message(reply=NS(message_id=9, date=0))
    assert build_sage_question(msg) == ''


@pytest.mark.parametrize('wording', ['проанализируй', 'помоги', 'объясни ему', 'что думаешь?', 'твое мнение'])
def test_vague_request_without_source_does_not_invent_context(wording):
    assert build_sage_question(message('сенсей мудрец ' + wording)) == ''


def test_emoji_chunks_fit_telegram_utf16_limit_and_preserve_text():
    from src.bot.sage_context import answer_chunks
    text = ('🦔' * 2000 + '\nАбзац с пояснением. ') * 3
    chunks = list(answer_chunks(text))
    assert ''.join(chunks) == text
    assert all(len(chunk.encode('utf-16-le')) // 2 <= 3500 for chunk in chunks)


@pytest.mark.asyncio
async def test_reply_target_is_strict_and_no_content_protection():
    msg = message('сенсей мудрец почему небо синее')
    await handle_sage(msg, NS(digest_service=NS(ask_sensei=AsyncMock(return_value='Ответ'))))
    options = msg.answer.call_args.kwargs
    assert options['reply_parameters'].message_id == 99
    assert options['reply_parameters'].allow_sending_without_reply is False
    assert options['protect_content'] is False
    assert options['link_preview_options'].is_disabled is True


@pytest.mark.asyncio
async def test_rate_limited_call_does_not_spend_api_or_send_extra_messages():
    msg = message('мудрец сенсей объясни теорию относительности')
    msg.from_user = NS(id=8)
    service = NS(ask_sensei=AsyncMock())
    limiter = NS(throttle=AsyncMock(return_value=False))
    await handle_sage(msg, NS(digest_service=service, throttle_service=limiter))
    service.ask_sensei.assert_not_awaited()
    msg.answer.assert_not_awaited()
    assert limiter.throttle.call_args.kwargs == dict(key='7:8', limit_seconds=5, scope='explicit_sage')


@pytest.mark.asyncio
@pytest.mark.parametrize('call', ['сенсей мудрец, что думаешь?', 'мудрец сенсей, объясни ему'])
async def test_real_dispatch_routes_both_orders_once_with_reply_context(call):
    from aiogram import Bot, Dispatcher, Router, F
    from aiogram.types import Update
    from src.bot.handlers.digest import cmd_sage
    from src.bot.handlers.triggers import trigger_sage_question
    dp = Dispatcher()
    router = Router()
    router.message.register(cmd_sage, F.text.regexp(SAGE_PATTERN))
    router.message.register(trigger_sage_question, F.text.regexp(SAGE_PATTERN))
    dp.include_router(router)
    session = AsyncMock(return_value=True)
    bot = Bot('123456:TEST', session=session)
    service = NS(ask_sensei=AsyncMock(return_value='Разбор сообщения'))
    event = Update.model_validate(dict(update_id=1, message=dict(message_id=99, date=1,
        chat=dict(id=7, type='private'), text=call, **{'from': dict(id=7, is_bot=False, first_name='User')},
        reply_to_message=dict(message_id=98, date=1, chat=dict(id=7, type='private'), text='Исходная задача'))))
    try:
        await dp.feed_update(bot, event, container=NS(digest_service=service))
        service.ask_sensei.assert_awaited_once()
        assert 'Исходная задача' in service.ask_sensei.call_args.args[0]
        from aiogram.methods import SendMessage
        sends = [c.args[1] for c in session.call_args_list if isinstance(c.args[1], SendMessage)]
        assert len(sends) == 1
        assert sends[0].reply_parameters.message_id == 99
    finally:
        await dp.storage.close()
