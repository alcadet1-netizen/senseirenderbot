"""Статическая одиночная игра: без кошелька, API наград и мультиплеера."""
from pathlib import Path
from aiohttp import web

ROOT = Path(__file__).parent / 'dojo'


def setup_dojo(app):
    async def page(request):
        name = request.match_info.get('asset', 'index.html')
        if name not in {'index.html', 'style.css', 'game.js'}:
            raise web.HTTPNotFound()
        return web.FileResponse(ROOT / name, headers={
            'Cache-Control': 'no-store',
            'X-Content-Type-Options': 'nosniff',
            'Referrer-Policy': 'no-referrer',
            'Content-Security-Policy': "default-src 'none'; script-src 'self'; style-src 'self'; "
                "img-src 'self' data:; connect-src 'none'; base-uri 'none'; "
                "form-action 'none'; frame-ancestors https://web.telegram.org https://*.telegram.org",
        })
    app.router.add_get('/miniapp/dojo', page)
    app.router.add_get('/miniapp/dojo/', page)
    app.router.add_get('/miniapp/dojo/{asset:game\\.js|style\\.css}', page)
