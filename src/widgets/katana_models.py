"""Shared cosmetic progression. Never writes balances or upgrade state."""
import math
from pathlib import Path

MODEL_NAMES = (
    'Стальной дракон', 'Ледяной страж', 'Сердце вулкана', 'Громовой клинок', 'Тень космоса',
    'Пламя дракона', 'Северная корона', 'Повелитель бурь', 'Звёздная ночь', 'Змеиный яд',
    'Ярость дракона', 'Вечная мерзлота', 'Кровавая луна', 'Неоновый самурай', 'Золотая сакура',
)


def model_index(length: float) -> int:
    value = float(length)
    if not math.isfinite(value):
        raise ValueError('Katana length must be finite')
    return min(len(MODEL_NAMES)-1, max(0, math.floor(value / 20)))


def model_path(index: int) -> Path:
    if not 0 <= index < len(MODEL_NAMES):
        raise ValueError('Unknown katana model')
    return Path(__file__).parent / 'assets' / 'katanas' / f'{index:02d}.webp'


def model_caption(length: float) -> str:
    index = model_index(length)
    interval = f'{index*20} ≤ длина < {(index+1)*20} см' if index < 14 else 'от 280 см'
    progress = (f'До модели «{MODEL_NAMES[index+1]}»: {(index+1)*20-length:.2f} см'
                if index < 14 else 'Высшая модель коллекции')
    return (f'⚔️ {MODEL_NAMES[index]} · {length:.2f} см\n'
            f'Модель {index+1}/15 · {interval}\n{progress}')


def render_model_png(length: float) -> bytes:
    """Static view deliberately does not encode a fake upgrade attempt."""
    from io import BytesIO
    from PIL import Image
    with Image.open(model_path(model_index(length))) as image:
        output = BytesIO()
        image.save(output, format='PNG')
        return output.getvalue()
