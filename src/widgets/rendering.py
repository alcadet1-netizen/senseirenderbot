"""Telegram-inspired panels, shared geometry for still and animated output.

Solid layered surfaces (not expensive simulated blur), generous tap-era spacing,
measured text wrapping, and a readable first frame on both palettes.
"""
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw, ImageFont

if TYPE_CHECKING:
    from src.widgets.cards import Card


PALETTES = {
    'dark': dict(bg='#0e1621', panel='#17212b', tile='#202e3b', line='#304354',
                 text='#f0f5fa', muted='#a4b6c7', accent='#6ab3f3', glow='#cce9ff'),
    'light': dict(bg='#eef3f8', panel='#ffffff', tile='#f1f6fb', line='#d8e5f0',
                  text='#162b40', muted='#546d83', accent='#1976c9', glow='#78bfff'),
}


@dataclass(frozen=True)
class Geometry:
    width: int
    height: int
    accent: tuple[int, int, int, int]
    progress: tuple[int, int, int, int] | None


@lru_cache(maxsize=32)
def font(size: int):
    try:
        return ImageFont.truetype('DejaVuSans.ttf', size)
    except OSError:
        return ImageFont.load_default(size=size)


def wrap(draw, text: str, size: int, width: int) -> list[str]:
    """Measured wrapping, including unbroken wide Unicode names; no lost suffix."""
    lines = ['']
    for char in text:
        if lines[-1] and draw.textlength(lines[-1] + char, font=font(size)) > width:
            lines.append('')
        lines[-1] += char
    return lines


def render_image(card: 'Card') -> tuple[Image.Image, Geometry]:
    colors = PALETTES[card.theme]
    profile = card.progress is not None
    columns = 2 if profile else 1
    width, margin, gap = 880, 40, 16
    cell_width = (width - 2 * margin - gap * (columns - 1)) // columns
    # Measure every value before allocating, so long titles do not overlap.
    probe = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    entries = []
    for key, value in card.rows:
        if profile:
            lines = wrap(probe, value, 24, cell_width - 32)
            keys = wrap(probe, key, 17, cell_width - 32)
            entries.append((keys, lines, max(86, 22 * len(keys) + 29 * len(lines) + 24)))
        else:
            key_width = max(80, int(cell_width - 48 - probe.textlength(value, font=font(22))))
            keys = wrap(probe, key, 22, key_width)
            entries.append((keys, [value], max(62, len(keys) * 27 + 22)))
    row_heights = [max(e[2] for e in entries[i:i + columns]) for i in range(0, len(entries), columns)]
    subtitle_lines = wrap(probe, card.subtitle, 30, 650)
    top = 108 + 36 * len(subtitle_lines) + 38
    content_end = top + sum(row_heights) + gap * max(0, len(row_heights) - 1)
    progress_y = content_end + 28 if profile else None
    art_y = content_end + (100 if profile else 22)
    height = art_y + (58 if card.art else 0) + 62
    image = Image.new('RGB', (width, height), colors['bg'])
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((16, 16, width - 16, height - 16), radius=30, fill=colors['panel'])
    draw.text((margin, 40), 'SENSEI  /  ' + card.title, font=font(17), fill=colors['accent'])
    for i, line in enumerate(subtitle_lines):
        draw.text((margin, 78 + i * 36), line, font=font(30), fill=colors['text'])
    accent_y = top - 23
    accent = (margin, accent_y, width - margin, accent_y + 3)
    draw.rounded_rectangle(accent, radius=1, fill=colors['line'])
    y = top
    for index, (keys, values, _) in enumerate(entries):
        col, row = index % columns, index // columns
        x = margin + col * (cell_width + gap)
        h = row_heights[row]
        draw.rounded_rectangle((x, y, x + cell_width, y + h), radius=16, fill=colors['tile'])
        if profile:
            for j, line in enumerate(keys):
                draw.text((x + 16, y + 12 + j * 22), line, font=font(17), fill=colors['muted'])
            for j, line in enumerate(values):
                draw.text((x + 16, y + 15 + len(keys) * 22 + j * 29), line, font=font(24), fill=colors['text'])
        else:
            for j, line in enumerate(keys):
                draw.text((x + 16, y + 15 + j * 27), line, font=font(22), fill=colors['text'])
            draw.text((x + cell_width - 16, y + 17), values[0], anchor='ra', font=font(22), fill=colors['accent'])
        if col == columns - 1 or index == len(entries) - 1:
            y += h + gap
    progress_box = None
    if profile:
        p = max(0, min(100, card.progress))
        progress_box = (margin, progress_y, width - margin, progress_y + 10)
        draw.rounded_rectangle(progress_box, radius=5, fill=colors['line'])
        if p:
            draw.rounded_rectangle((margin, progress_y, margin + (width - margin * 2) * p / 100, progress_y + 10), radius=5, fill=colors['accent'])
        draw.text((margin, progress_y + 23), f'Прогресс уровня  {p}%', font=font(19), fill=colors['muted'])
    if card.art:
        for i, line in enumerate(wrap(draw, card.art, 19, width - margin * 2)):
            draw.text((margin, art_y + i * 24), line, font=font(19), fill=colors['accent'])
    draw.text((margin, height - 53), 'СНИМОК ДАННЫХ  ·  Обновить кнопкой под сообщением', font=font(16), fill=colors['muted'])
    return image, Geometry(width, height, accent, progress_box)
