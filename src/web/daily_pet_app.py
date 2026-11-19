"""Retired daily-pet Mini App endpoints for previously issued links."""
from aiohttp import web


def setup_daily_pet(app, container):
    async def retired(request):
        return web.json_response(
            {'error': 'Поглаживания больше недоступны. Ежедневная награда выдаётся в чате.'},
            status=410, headers={'Cache-Control': 'no-store'})

    app.router.add_get('/miniapp/daily-pet', retired)
    app.router.add_get('/miniapp/daily-pet/{asset:app\\.(?:js|css)|art\\.webp}', retired)
    app.router.add_post('/miniapp/daily-pet/api/{action:view|tap}', retired)
