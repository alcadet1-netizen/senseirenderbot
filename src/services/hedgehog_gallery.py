"""Persistent shuffle-bag selection for ordinary and paid hedgehog notices."""
import hashlib
import secrets
from typing import List, Tuple

from src.services.hedgehog_service import GameError
from src.services.hedgehog_gridfs import HedgehogGridFS


async def gallery_files(gridfs: HedgehogGridFS) -> List[str]:
    """Get list of image filenames from GridFS."""
    files = await gridfs.list_images()
    names = [f['filename'] for f in files]
    if not names:
        raise GameError('Картинки ежа временно недоступны. Попробуйте позже.')
    return names


async def select_image(user, gridfs: HedgehogGridFS) -> Tuple[str, List[str]]:
    """Select a hedgehog image for the user from GridFS."""
    names = await gallery_files(gridfs)
    previous = user.get('daily_pet') or {}
    last = previous.get('image_name')
    if last not in names:
        # Avoid immediately repeating the photo used by the old ID-based renderer.
        index = int(hashlib.sha256(str(user['id']).encode()).hexdigest()[:8], 16) % len(names)
        last = names[index]
    seen = set(user.get('hedgehog_images_seen') or []) & set(names)
    seen.add(last)
    available = [name for name in names if name not in seen]
    if not available:
        seen = {last}
        available = [name for name in names if name != last] or names
    chosen = secrets.choice(available)
    seen.add(chosen)
    return chosen, sorted(seen)
