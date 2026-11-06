"""Bounded local GIF rendering: animate accents, never the actual user numbers.

Telegram's sendAnimation accepts GIF. No ffmpeg, external service or periodic
message edits are required. Clients with autoplay disabled keep a readable frame.
"""
from functools import lru_cache
from io import BytesIO

from PIL import Image, ImageDraw

from src.widgets.cards import Card
from src.widgets.rendering import PALETTES, render_image


@lru_cache(maxsize=8)
def to_gif(card: Card) -> bytes:
    """12 palette frames, 660 px wide, ~2 s loop; cache only eight snapshots."""
    source, geometry = render_image(card)
    colors = PALETTES[card.theme]
    width = 660
    base = source.resize((width, round(source.height * width / source.width)), Image.Resampling.LANCZOS)
    palette = base.quantize(colors=96)
    scale = width / 880
    frames = []
    for index in range(12):
        frame = base.copy()
        draw = ImageDraw.Draw(frame)
        left, top, right, bottom = geometry.accent
        x = left + (right - left - 72) * index / 11
        draw.rounded_rectangle(
            (left * scale, top * scale, right * scale, bottom * scale), radius=2, fill=colors['line'],
        )
        draw.rounded_rectangle(
            (x * scale, top * scale, (x + 72) * scale, bottom * scale), radius=2, fill=colors['accent'],
        )
        if card.progress and geometry.progress:
            left, top, right, bottom = geometry.progress
            y = top * scale
            filled = (right - left) * max(0, min(100, card.progress)) / 100 * scale
            segment = min(40 * scale, filled)
            start = left * scale + max(0, filled - segment) * index / 11
            draw.rectangle((start, y + 2, start + segment, y + 5), fill=colors['glow'])
        frames.append(frame.quantize(palette=palette, dither=Image.Dither.NONE))
    output = BytesIO()
    frames[0].save(
        output, format='GIF', save_all=True, append_images=frames[1:],
        duration=[120] * 11 + [600], loop=0, optimize=False, disposal=1,
    )
    result = output.getvalue()
    if len(result) > 5 * 1024 * 1024:
        raise ValueError('Widget animation exceeds the local 5 MiB budget')
    return result
