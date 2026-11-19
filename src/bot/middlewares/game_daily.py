"""Let the daily alias also run when a chat game's message handler consumes it."""
from aiogram import BaseMiddleware

DAILY_ALIASES = frozenset({'ежа', 'фарм', 'фармить', 'фарма', 'ферма'})


class GameDailyMiddleware(BaseMiddleware):
    def __init__(self, game_handler_name):
        self.game_handler_name = game_handler_name

    async def __call__(self, handler, event, data):
        result = await handler(event, data)
        selected = data.get('handler')
        callback = getattr(selected, 'callback', None)
        if (getattr(callback, '__name__', '') == self.game_handler_name
                and event.from_user and event.text
                and event.text.lower() in DAILY_ALIASES):
            from src.bot.presenters.hedgehog_presenter import launch_hedgehog
            await launch_hedgehog(event, event.from_user, data['container'])
        return result
