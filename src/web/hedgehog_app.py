"""Mini App static UI and authenticated same-origin game API."""
import logging
from pathlib import Path

from aiohttp import web

from src.core.exceptions import DailyAlreadyClaimedError
from src.services.hedgehog_service import GameError
from src.services.maintenance_service import MaintenanceService
from src.web.telegram_auth import verify_init_data

logger = logging.getLogger(__name__)
ROOT = Path(__file__).parent / 'hedgehog'


def setup_hedgehog(app, container):
    async def page(request):
        name = request.match_info.get('asset', 'index.html')
        if name not in {'index.html', 'app.js', 'app.css'}:
            raise web.HTTPNotFound()
        response = web.FileResponse(ROOT / name)
        response.headers.update({
            'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
            'Referrer-Policy': 'no-referrer',
            'Content-Security-Policy': "default-src 'self'; script-src 'self' https://telegram.org; style-src 'self'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors https://web.telegram.org https://*.telegram.org",
        })
        return response

    # Reuse the bot's existing hedgehog pictures, never accept a filesystem path.
    images = sorted(p for p in (container.settings.BASE_DIR / 'src/infra/storage/ega').glob('*')
                    if p.is_file() and p.suffix.lower() in {'.jpg', '.jpeg', '.png', '.gif'})

    async def picture(request):
        index = int(request.match_info['index'])
        if index >= len(images):
            raise web.HTTPNotFound()
        return web.FileResponse(images[index], headers={'X-Content-Type-Options': 'nosniff'})

    async def api(request):
        headers = {'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'}
        try:
            payload = await request.json()
            if not isinstance(payload, dict):
                raise ValueError('Неверный запрос.')
            user = verify_init_data(payload.get('initData'), container.settings.bot_token)
        except (ValueError, TypeError, KeyError):
            return web.json_response({'error': 'Откройте игру заново внутри Telegram.'}, status=401, headers=headers)
        if container.settings.maintenance_mode or MaintenanceService.is_enabled():
            return web.json_response({'error': 'Сенсей на техобслуживании. Попробуйте позже.'}, status=503, headers=headers)
        try:
            token = payload.get('session')
            method = container.hedgehog_service.start if request.match_info['action'] == 'start' else container.hedgehog_service.finish
            result = await method(token, user['id'])
            if result.get('state') == 'done' and result['result']['success'] and images:
                import hashlib
                index = int(hashlib.sha256(token.encode()).hexdigest()[:8], 16) % len(images)
                result = {**result, 'image': f'/miniapp/hedgehog/picture/{index}'}
            return web.json_response(result, headers=headers)
        except (GameError, DailyAlreadyClaimedError) as exc:
            return web.json_response({'error': str(exc)}, status=409, headers=headers)
        except Exception:
            logger.exception('Hedgehog API failed (user=%s)', user['id'])
            return web.json_response({'error': 'Ёж потерял связь. Повторите запрос — второй награды не будет.'}, status=503, headers=headers)

    app.router.add_get('/miniapp/hedgehog', page)
    app.router.add_get('/miniapp/hedgehog/{asset:app\\.(?:js|css)}', page)
    app.router.add_get('/miniapp/hedgehog/picture/{index:\\d+}', picture)
    app.router.add_post('/miniapp/hedgehog/api/{action:start|finish}', api)
