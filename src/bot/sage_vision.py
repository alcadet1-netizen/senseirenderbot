"""Bounded in-memory Telegram image loading for explicit sage requests."""
import asyncio
from io import BytesIO
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_DOWNLOAD = 5 * 1024 * 1024


class ImageUnavailable(Exception):
    pass


class LimitedBuffer(BytesIO):
    def write(self, data):
        if self.tell() + len(data) > MAX_DOWNLOAD:
            raise ImageUnavailable('Фото слишком большое. Пришли изображение до 5 МБ.')
        return super().write(data)


def image_source(message):
    for source in (message, getattr(message, 'reply_to_message', None)):
        if source is None:
            continue
        photos = getattr(source, 'photo', None)
        if photos:
            suitable = [p for p in photos if not p.file_size or p.file_size <= MAX_DOWNLOAD]
            return max(suitable or photos, key=lambda p: p.width * p.height)
        doc = getattr(source, 'document', None)
        if doc and getattr(doc, 'mime_type', None) in {'image/jpeg', 'image/png', 'image/webp'}:
            return doc
    return None


def prepare_image(raw):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as image:
                if image.width * image.height > 20_000_000 or getattr(image, 'is_animated', False):
                    raise ImageUnavailable('Пришли статичное фото до 20 мегапикселей.')
                if image.format not in {'JPEG', 'PNG', 'WEBP'}:
                    raise ImageUnavailable('Поддерживаются JPEG, PNG и WebP.')
                image = ImageOps.exif_transpose(image)
                image.thumbnail((1600, 1600))
                image = image.convert('RGB')
                output = BytesIO()
                image.save(output, format='JPEG', quality=85)
                if output.tell() > 4 * 1024 * 1024:
                    raise ImageUnavailable('Изображение слишком большое. Пришли уменьшенную копию.')
                return output.getvalue()
    except ImageUnavailable:
        raise
    except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ImageUnavailable('Не удалось прочитать картинку. Пришли её заново как фото.') from None


async def load_image(bot, source):
    if source.file_size and source.file_size > MAX_DOWNLOAD:
        raise ImageUnavailable('Фото слишком большое. Пришли изображение до 5 МБ.')
    try:
        with LimitedBuffer() as buffer:
            await asyncio.wait_for(bot.download(source.file_id, destination=buffer, timeout=10), timeout=12)
            return await asyncio.to_thread(prepare_image, buffer.getvalue())
    except ImageUnavailable:
        raise
    except Exception:
        raise ImageUnavailable('Фото удалено или недоступно для загрузки. Пришли его заново.') from None
