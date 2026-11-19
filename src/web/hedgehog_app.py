"""Mini App static UI and authenticated same-origin game API."""
import logging
import hashlib
from io import BytesIO

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

    # GridFS service for hedgehog images
    gridfs = container.hedgehog_gridfs

    async def picture(request):
        """Serve hedgehog image by index from GridFS."""
        index = int(request.match_info['index'])
        # Get list of images from GridFS
        files = await gridfs.list_images()
        if index >= len(files):
            raise web.HTTPNotFound()
        # Get image content by ID
        content = await gridfs.get_image_by_id(files[index]['id'])
        if not content:
            raise web.HTTPNotFound()
        return web.Response(
            body=content,
            content_type='image/jpeg',
            headers={'X-Content-Type-Options': 'nosniff', 'Cache-Control': 'public, max-age=3600'}
        )

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
            if result.get('state') == 'done' and result['result']['success']:
                # Get images from GridFS to determine index
                files = await gridfs.list_images()
                if files:
                    index = int(hashlib.sha256(token.encode()).hexdigest()[:8], 16) % len(files)
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
