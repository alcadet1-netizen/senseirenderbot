from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

import pytest

from src.bot.handlers.chat_settings import cmd_joindiag


@pytest.mark.asyncio
@pytest.mark.parametrize('allowed,expected', [
    (['message', 'chat_member'], 'chat_member в настройке Telegram: да'),
    (['message'], 'chat_member в настройке Telegram: нет'),
    ([], 'по умолчанию'),
    (None, 'подписка неизвестна'),
])
async def test_admin_diagnostics_reports_real_api_state(allowed, expected):
    message = NS(from_user=NS(id=123), chat=NS(id=-100222, type='supergroup'), answer=AsyncMock())
    bot = NS(id=999, get_chat_member=AsyncMock(return_value=NS(status='administrator', can_invite_users=False)),
             get_webhook_info=AsyncMock(return_value=NS(url='', allowed_updates=allowed)))
    with patch('src.bot.handlers.chat_settings.settings') as settings:
        settings.admin_ids = [123]
        await cmd_joindiag(message, bot)
    text = message.answer.await_args.args[0]
    assert expected in text and 'administrator' in text and 'Право приглашать: нет' in text
    assert 'Webhook: выключен' in text and '-100222' in text


@pytest.mark.asyncio
async def test_non_admin_cannot_inspect_bot_subscription():
    message = NS(from_user=NS(id=456), chat=NS(id=-100222, type='group'), answer=AsyncMock())
    bot = NS(get_chat_member=AsyncMock(), get_webhook_info=AsyncMock())
    with patch('src.bot.handlers.chat_settings.settings') as settings:
        settings.admin_ids = [123]
        await cmd_joindiag(message, bot)
    message.answer.assert_not_awaited()
    bot.get_webhook_info.assert_not_awaited()
