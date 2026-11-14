"""Serve the standalone dojo through the existing bot HTTP process."""
from pathlib import Path

from aiohttp import web

from src.web.dojo_multiplayer import setup_multiplayer

PAGE = Path(__file__).resolve().parents[2] / 'index.html'


def setup_dojo(app, container=None, bot=None):
    setup_multiplayer(app, container, bot)

    async def page(request):
        return web.FileResponse(PAGE, headers={
            'Cache-Control': 'no-store',
            'X-Content-Type-Options': 'nosniff',
            'Referrer-Policy': 'no-referrer',
            'Content-Security-Policy': (
                "default-src 'none'; script-src 'unsafe-inline' https://telegram.org; "
                "style-src 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; "
                "base-uri 'none'; form-action 'none'; "
                "frame-ancestors https://web.telegram.org https://*.telegram.org"
            ),
        })

    app.router.add_get('/miniapp/dojo', page)
    app.router.add_get('/miniapp/dojo/', page)
