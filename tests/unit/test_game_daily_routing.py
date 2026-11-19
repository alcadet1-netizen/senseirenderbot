from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from aiogram import Bot, Dispatcher, Router
from aiogram.types import Update

from src.bot.middlewares.game_daily import GameDailyMiddleware


@pytest.mark.asyncio
@pytest.mark.parametrize('name', ['count_wave_message', 'check_bomb_participant', 'check_roulette_response'])
@pytest.mark.parametrize('text', ['Ежа', 'фарм', 'фарма', 'фармить', 'ферма'])
async def test_game_consumes_alias_but_daily_still_runs_once(name, text):
    dp = Dispatcher()
    game_router = Router()
    game_router.message.middleware(GameDailyMiddleware(name))
    seen = []
    async def game(message):
        seen.append('game')
    game.__name__ = name
    game_router.message.register(game)
    dp.include_router(game_router)
    container = SimpleNamespace()
    bot = Bot('123456:TEST')
    event = Update.model_validate({'update_id': 1, 'message': {'message_id': 4, 'date': 1,
        'chat': {'id': -100, 'type': 'supergroup'},
        'from': {'id': 7, 'is_bot': False, 'first_name': 'H'}, 'text': text}})
    try:
        with patch('src.bot.presenters.hedgehog_presenter.launch_hedgehog', new_callable=AsyncMock) as launch:
            await dp.feed_update(bot, event, container=container)
        assert seen == ['game']
        launch.assert_awaited_once()
        assert launch.await_args.args[1].id == 7 and launch.await_args.args[2] is container
    finally:
        await bot.session.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('text,name', [('обычный текст','count_wave_message'), ('Ежа','cmd_senseiwave')])
async def test_other_text_or_handlers_are_not_forwarded(text, name):
    middleware = GameDailyMiddleware('count_wave_message')
    callback = SimpleNamespace(__name__=name)
    event = SimpleNamespace(text=text, from_user=SimpleNamespace(id=7))
    with patch('src.bot.presenters.hedgehog_presenter.launch_hedgehog', new_callable=AsyncMock) as launch:
        assert await middleware(AsyncMock(return_value='ok'), event,
            {'handler': SimpleNamespace(callback=callback), 'container': object()}) == 'ok'
    launch.assert_not_awaited()


def test_production_game_routers_install_forwarding_only_for_game_handlers():
    from src.bot.handlers import bomb, roulette, wave
    for module, name in [(bomb, 'check_bomb_participant'),
                         (roulette, 'check_roulette_response'),
                         (wave, 'count_wave_message')]:
        assert any(isinstance(middleware, GameDailyMiddleware) and middleware.game_handler_name == name
                   for middleware in module.router.message.middleware)
