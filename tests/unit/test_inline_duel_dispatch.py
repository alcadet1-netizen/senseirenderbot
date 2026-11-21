"""Exercise aiogram argument injection, not direct calls to the handlers."""
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest
from aiogram import Bot, F, Router
from aiogram.types import Update

from src.bot.handlers.duel_commands import inline_duel, sent_inline_duel
from src.bot.loader import create_dispatcher


@pytest.mark.asyncio
async def test_dispatcher_injects_container_for_both_inline_duel_updates():
    offers = NS(update_one=AsyncMock())
    container = NS(mongo_client=NS(database=NS(dojo_duel_offers=offers, users=NS(
        find_one=AsyncMock(return_value={'coins': 500})))), duel_service=NS(_is_in_active_duel=lambda _: False))
    dp = create_dispatcher(container)
    router = Router()
    router.inline_query.register(inline_duel, F.query.startswith('dojo_vs '))
    router.chosen_inline_result.register(sent_inline_duel, F.result_id.startswith('vs_'))
    dp.include_router(router)
    session = AsyncMock()
    bot = Bot('123456:TEST', session=session)
    bot.me = AsyncMock(return_value=NS(username='dojo_test_bot'))
    user = {'id': 7, 'first_name': 'Игрок', 'is_bot': False}
    async def feed(i, **event):
        await dp.feed_update(bot, Update.model_validate({'update_id': i, **event}, context={'bot': bot}))
    await feed(1, inline_query={'id': 'q', 'from': user, 'query': 'dojo_vs 300', 'offset': '', 'chat_type': 'private'})
    result = session.await_args.args[1].results[0]
    await feed(2, chosen_inline_result={'result_id': result.id, 'from': user, 'query': 'dojo_vs 300', 'inline_message_id': 'post'})
    assert offers.update_one.await_count == 2
    assert offers.update_one.await_args.args[1]['$set']['status'] == 'open'
