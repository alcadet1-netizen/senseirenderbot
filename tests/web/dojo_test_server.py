"""Local browser fixture. Fake Telegram API only; never start as production server."""
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from aiohttp import web
from src.web.dojo_app import setup_dojo

if __name__ == '__main__':
    app = web.Application(client_max_size=16*1024)
    settings = SimpleNamespace(bot_token='123456:local-test-only', dojo_app_url='')
    bot = SimpleNamespace(get_me=AsyncMock(return_value=SimpleNamespace(username='test_dojo_bot')),
                          save_prepared_inline_message=AsyncMock(return_value=SimpleNamespace(id='prepared')))
    setup_dojo(app, SimpleNamespace(settings=settings), bot)
    web.run_app(app, host='127.0.0.1', port=int(sys.argv[1]), print=lambda s:print(s, flush=True))
