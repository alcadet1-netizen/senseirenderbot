from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

import pytest

from src.bot.handlers.callbacks import cb_donate_menu, cb_do_upgrade_katana
from src.bot.handlers.donate import show_donate_menu
from src.bot.keyboards.inline import MenuCb, get_profile_keyboard
from src.core.exceptions import InsufficientFundsError


@pytest.mark.parametrize('has_katana', [True, False])
def test_profile_has_owner_bound_donate_button(has_katana):
    buttons = [b for row in get_profile_keyboard(7, has_katana).inline_keyboard for b in row]
    button, = [b for b in buttons if b.text == '⭐ Донат']
    assert MenuCb.unpack(button.callback_data) == MenuCb(action='donate_menu', user_id=7)


@pytest.mark.asyncio
@pytest.mark.parametrize('owner', [7, 8])
async def test_donate_button_owner_and_actor(owner):
    actor = NS(id=7)
    query = NS(from_user=actor, message=NS(), answer=AsyncMock())
    container = NS()
    with patch('src.bot.handlers.callbacks.show_donate_menu', new_callable=AsyncMock) as show:
        await cb_donate_menu(query, MenuCb(action='donate_menu', user_id=owner), container)
    if owner == 7:
        show.assert_awaited_once_with(query.message, container, actor)
    else:
        show.assert_not_awaited()
        assert query.answer.call_args.kwargs['show_alert']


@pytest.mark.asyncio
async def test_pending_receipt_recovery_uses_clicking_user_not_message_author():
    message = NS(from_user=NS(id=999))  # profile is a bot-authored message
    service = NS(pending=AsyncMock(return_value={'receipt': 'pending'}))
    container = NS(mongo_client=NS())
    with (patch('src.bot.handlers.donate.StarCoinService', return_value=service),
          patch('src.bot.handlers.donate.coin_received', new_callable=AsyncMock) as recover):
        await show_donate_menu(message, container, NS(id=7))
    service.pending.assert_awaited_once_with(7)
    recover.assert_awaited_once_with(message, container, payment={'receipt': 'pending'}, user_id=7)


@pytest.mark.asyncio
async def test_profile_upgrade_shortage_shows_joke_and_donate_without_retry():
    query = NS(from_user=NS(id=7), answer=AsyncMock(), message=NS(edit_text=AsyncMock()))
    service = NS(upgrade_katana=AsyncMock(side_effect=InsufficientFundsError(100, 5)))
    await cb_do_upgrade_katana(query, MenuCb(action='confirm_upgrade_katana', user_id=7),
                               NS(economy_service=service))
    service.upgrade_katana.assert_awaited_once_with(7)
    query.message.edit_text.assert_awaited_once()
    text = query.message.edit_text.call_args.args[0]
    assert '/donate' in text and 'Нужно: 100' in text and 'У тебя: 5' in text
    markup = query.message.edit_text.call_args.kwargs['reply_markup']
    assert any(b.text == '⭐ Донат' for row in markup.inline_keyboard for b in row)


@pytest.mark.asyncio
async def test_expired_callback_ack_does_not_block_donate_menu():
    from aiogram.exceptions import TelegramBadRequest
    query = NS(from_user=NS(id=7), message=NS(),
               answer=AsyncMock(side_effect=TelegramBadRequest(method='answerCallbackQuery', message='query is too old')))
    container = NS()
    with patch('src.bot.handlers.callbacks.show_donate_menu', new_callable=AsyncMock) as show:
        await cb_donate_menu(query, MenuCb(action='donate_menu', user_id=7), container)
    show.assert_awaited_once_with(query.message, container, query.from_user)


@pytest.mark.asyncio
@pytest.mark.parametrize('detail', ['Bad Request: message is not modified', 'Bad Request: message to edit not found'])
async def test_repeated_shortage_receipt_handles_only_not_modified(detail):
    from aiogram.exceptions import TelegramBadRequest
    error = TelegramBadRequest(method='editMessageText', message=detail)
    query = NS(from_user=NS(id=7), answer=AsyncMock(),
               message=NS(edit_text=AsyncMock(side_effect=error)))
    service = NS(upgrade_katana=AsyncMock(side_effect=InsufficientFundsError(100, 5)))
    async def invoke():
        await cb_do_upgrade_katana(query, MenuCb(action='confirm_upgrade_katana', user_id=7),
                                   NS(economy_service=service))
    if 'not modified' in detail:
        await invoke()
    else:
        with pytest.raises(TelegramBadRequest):
            await invoke()
    service.upgrade_katana.assert_awaited_once_with(7)
    query.message.edit_text.assert_awaited_once()
