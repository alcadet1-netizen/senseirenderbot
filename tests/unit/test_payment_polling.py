"""Guard the production polling subscription, not only synthetic dispatch."""
import ast
from pathlib import Path

from aiogram import Dispatcher
from src.bot.handlers import setup_routers


def test_production_polling_subscribes_to_middleware_payment_updates():
    tree = ast.parse(Path('src/main.py').read_text())
    polling = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
               and isinstance(n.func, ast.Attribute) and n.func.attr == 'start_polling']
    assert len(polling) == 1
    expression = next(k.value for k in polling[0].keywords if k.arg == 'allowed_updates')
    dp = Dispatcher()
    dp.include_router(setup_routers())
    # Middleware-only events are absent from router-derived subscriptions.
    assert 'pre_checkout_query' not in dp.resolve_used_update_types()
    updates = eval(compile(ast.Expression(expression), '<polling subscription>', 'eval'), {'dp': dp})
    assert {'pre_checkout_query', 'message', 'channel_post',
            'widget_query', 'shared_widget_query'} <= set(updates)
    assert set(dp.resolve_used_update_types()) <= set(updates)
    assert len(updates) == len(set(updates))
