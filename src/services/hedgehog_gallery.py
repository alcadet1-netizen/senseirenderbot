"""Persistent shuffle-bag selection for ordinary and paid hedgehog notices."""
import hashlib
import secrets
from pathlib import Path

from src.services.hedgehog_service import GameError

GALLERY = Path(__file__).resolve().parents[1] / 'infra/storage/ega'


def gallery_files(directory=GALLERY):
    files = sorted(p for p in directory.iterdir() if p.is_file() and p.suffix.lower() in {'.jpg', '.jpeg', '.png'}) if directory.is_dir() else []
    if not files:
        raise GameError('Картинки ежа временно недоступны. Попробуйте позже.')
    return files


def select_image(user, directory=GALLERY):
    names = [p.name for p in gallery_files(directory)]
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
