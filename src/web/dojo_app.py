"""Single-player Dojo survival Mini App with a small server-side coin payout."""
import logging
from pathlib import Path

from aiohttp import web

from src.services.hedgehog_service import GameError
from src.services.maintenance_service import MaintenanceService
from src.web.telegram_auth import verify_init_data

ROOT = Path(__file__).parent / 'dojo'
ASSETS = {
    'index.html', 'style.css', 'game.js', 'economy.js', 'renderer.js',
    'vendor/three.module.js', 'vendor/three.core.js',
}


def setup_dojo(app, container=None):
    headers = {
        'Cache-Control': 'no-store',
        'X-Content-Type-Options': 'nosniff',
        'Referrer-Policy': 'no-referrer',
    }

    async def page(request):
        name = request.match_info.get('asset', 'index.html')
        if name not in ASSETS:
            raise web.HTTPNotFound()
        response = web.FileResponse(ROOT / name, headers=headers)
        response.headers['Content-Security-Policy'] = (
            "default-src 'none'; script-src 'self' https://telegram.org; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; base-uri 'none'; "
            "form-action 'none'; frame-ancestors https://web.telegram.org https://*.telegram.org"
        )
        return response

    async def api(request):
        if container is None:
            return web.json_response(
                {'error': 'Награды недоступны.'}, status=503, headers=headers)
        try:
            payload = await request.json()
            if not isinstance(payload, dict):
                raise ValueError()
            user = verify_init_data(payload.get('initData'), container.settings.bot_token)
        except (ValueError, TypeError, KeyError):
            return web.json_response(
                {'error': 'Откройте игру внутри Telegram.'}, status=401, headers=headers)
        if container.settings.maintenance_mode or MaintenanceService.is_enabled():
            return web.json_response(
                {'error': 'Сенсей на техобслуживании. Попробуйте позже.'},
                status=503, headers=headers)
        try:
            if request.match_info['action'] == 'start':
                result = await container.dojo_service.start(user['id'])
            else:
                result = await container.dojo_service.claim(
                    user['id'], payload.get('run'), payload.get('wave'),
                    payload.get('victory'))
            return web.json_response(result, headers=headers)
        except GameError as exc:
            return web.json_response({'error': str(exc)}, status=409, headers=headers)
        except Exception:
            # Never log initData, Telegram tokens or raw payloads.
            logging.getLogger(__name__).error(
                'Dojo reward API failed: action=%s', request.match_info['action'])
            return web.json_response(
                {'error': 'Награда не учтена. Попробуйте позже.'}, status=503, headers=headers)

    app.router.add_get('/miniapp/dojo', page)
    app.router.add_get('/miniapp/dojo/', page)
    app.router.add_get(
        '/miniapp/dojo/{asset:game\\.js|economy\\.js|renderer\\.js|style\\.css|vendor/three\\.(?:module|core)\\.js}',
        page)
    app.router.add_post('/miniapp/dojo/api/{action:start|claim}', api)
