"""HD personal petting Mini App; authenticated identity and server arrival timing."""
import re
import time
from pathlib import Path

from aiohttp import web

from src.services.daily_pet_service import PetRateLimit
from src.services.hedgehog_service import GameError
from src.services.maintenance_service import MaintenanceService
from src.web.telegram_auth import verify_init_data

ROOT = Path(__file__).parent / 'daily_pet'


def setup_daily_pet(app, container):
    headers = {'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer'}

    async def page(request):
        name = request.match_info.get('asset', 'index.html')
        if name not in {'index.html', 'app.js', 'app.css', 'art.webp'}:
            raise web.HTTPNotFound()
        response = web.FileResponse(ROOT / name, headers=headers)
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; script-src 'self' https://telegram.org; style-src 'self' 'unsafe-inline'; "
            "img-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'none'; "
            "frame-ancestors 'self' https://web.telegram.org https://*.telegram.org")
        return response

    async def api(request):
        try:
            payload = await request.json()
            if not isinstance(payload, dict):
                raise ValueError()
            user = verify_init_data(payload.get('initData'), container.settings.bot_token)
        except (ValueError, TypeError, KeyError):
            return web.json_response({'error': 'Откройте игру внутри Telegram.'}, status=401, headers=headers)
        # Captured ONLY after the complete body and HMAC verification, never from
        # client time. Waiting on database/another tap cannot reset this arrival.
        received_at = time.time()
        if container.settings.maintenance_mode or MaintenanceService.is_enabled():
            return web.json_response({'error': 'Бот на обслуживании. Основная награда сохранена.'}, status=503, headers=headers)
        action = request.match_info['action']
        query_id = ''
        if action == 'tap':
            value = payload.get('request_id')
            if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,64}', value):
                return web.json_response({'error': 'Неверный ID поглаживания.'}, status=400, headers=headers)
            query_id = 'web:' + value
        try:
            result = await container.daily_pet_service.widget_action(
                payload.get('session'), user['id'], 'p' if action == 'tap' else 'v', query_id,
                received_at=received_at if action == 'tap' else None)
            return web.json_response(result, headers=headers)
        except PetRateLimit as exc:
            return web.json_response({'error': str(exc)}, status=429, headers=headers)
        except GameError as exc:
            return web.json_response({'error': str(exc)}, status=409, headers=headers)
        except Exception:
            # No request/initData/token or raw exception is logged here.
            import logging
            logging.getLogger(__name__).error('Private Mini App API failed: action=%s', action)
            return web.json_response({'error': 'Нет ответа. Повтор с тем же ID не удвоит бонус.'}, status=503, headers=headers)

    app.router.add_get('/miniapp/daily-pet', page)
    app.router.add_get('/miniapp/daily-pet/{asset:app\\.(?:js|css)|art\\.webp}', page)
    app.router.add_post('/miniapp/daily-pet/api/{action:view|tap}', api)
