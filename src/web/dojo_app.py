"""SenseiCoin miner Mini App: one kick starts an eight-hour bank-funded cycle."""
import logging
from pathlib import Path

from aiohttp import web

from src.services.hedgehog_service import GameError
from src.services.maintenance_service import MaintenanceService
from src.web.telegram_auth import verify_init_data

ROOT = Path(__file__).parent / 'dojo'
ASSETS = {
    'index.html',
    'style.css',
    'miner.js',
    'assets/kick.webp',
    'assets/mining.webp',
}


def setup_dojo(app, container=None):
    headers = {
        'Cache-Control': 'no-store',
        'X-Content-Type-Options': 'nosniff',
        'Referrer-Policy': 'no-referrer',
    }

    async def page(request):
        name = request.match_info.get('asset', 'index.html')
        if request.path.startswith('/miniapp/dojo/assets/'):
            name = 'assets/' + name
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
                {'error': 'Майнер недоступен.'}, status=503, headers=headers)
        try:
            payload = await request.json()
            if not isinstance(payload, dict):
                raise ValueError()
            user = verify_init_data(payload.get('initData'), container.settings.bot_token)
        except (ValueError, TypeError, KeyError):
            return web.json_response(
                {'error': 'Откройте майнер внутри Telegram.'}, status=401, headers=headers)
        if container.settings.maintenance_mode or MaintenanceService.is_enabled():
            return web.json_response(
                {'error': 'Сенсей на техобслуживании. Попробуйте позже.'},
                status=503, headers=headers)
        action = request.match_info['action']
        try:
            service = container.dojo_miner_service
            if action == 'state':
                result = await service.state(user['id'])
            elif action == 'kick':
                result = await service.kick(user['id'])
            else:
                result = await service.collect(user['id'])
            return web.json_response(result, headers=headers)
        except GameError as exc:
            return web.json_response({'error': str(exc)}, status=409, headers=headers)
        except Exception:
            # Never log initData, Telegram tokens or raw payloads.
            logging.getLogger(__name__).error('Dojo miner API failed: action=%s', action)
            return web.json_response(
                {'error': 'Майнер не ответил. Попробуйте ещё раз.'}, status=503,
                headers=headers)

    app.router.add_get('/miniapp/dojo', page)
    app.router.add_get('/miniapp/dojo/', page)
    app.router.add_get(
        '/miniapp/dojo/{asset:style\\.css|miner\\.js}', page)
    app.router.add_get(
        '/miniapp/dojo/assets/{asset:kick\\.webp|mining\\.webp}', page)
    app.router.add_post('/miniapp/dojo/api/{action:state|kick|collect}', api)
