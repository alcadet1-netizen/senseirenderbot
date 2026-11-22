"""Persistent shuffle-bag selection for ordinary and paid hedgehog notices."""
import hashlib
import os
import secrets
from typing import List, Tuple

from src.services.hedgehog_service import GameError
from src.services.hedgehog_gridfs import HedgehogGridFS


def _is_valid_entry(entry: dict) -> bool:
    name = entry.get('filename')
    if not isinstance(name, str) or not name or os.path.basename(name) != name or name in {'.', '..'}:
        return False
    length = entry.get('length')
    if length is not None and length <= 0:
        return False
    return True


async def gallery_files(gridfs: HedgehogGridFS) -> List[str]:
    """Get list of non-empty safe image filenames from GridFS."""
    files = await gridfs.list_images()
    seen = set()
    names = []
    for f in files:
        if _is_valid_entry(f):
            name = f['filename']
            if name not in seen:
                seen.add(name)
                names.append(name)
    if not names:
        raise GameError('Картинки ежа временно недоступны. Попробуйте позже.')
    return names


async def select_image(user, gridfs: HedgehogGridFS, *, exclude=()) -> Tuple[str, List[str]]:
    """Select a hedgehog image for the user from GridFS."""
    excluded = set(exclude or ())
    names = [name for name in await gallery_files(gridfs) if name not in excluded]
    if not names:
        raise GameError('Картинки ежа временно недоступны. Попробуйте позже.')
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
