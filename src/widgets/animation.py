"""Bounded local GIF rendering: animate accents, never the actual user numbers.

Telegram's sendAnimation accepts GIF. No ffmpeg, external service or periodic
message edits are required. Clients with autoplay disabled keep a readable frame.
"""
from functools import lru_cache
from io import BytesIO

from PIL import Image, ImageDraw

from src.widgets.cards import Card, to_png


@lru_cache(maxsize=8)
def to_gif(card: Card) -> bytes:
    """12 palette frames, 660 px wide, ~2 s loop; cache only eight snapshots."""
    with Image.open(BytesIO(to_png(card))) as source:
        width = 660
        base = source.convert('RGB').resize(
            (width, round(source.height * width / source.width)), Image.Resampling.LANCZOS,
        )
    palette = base.quantize(colors=96)
    scale = width / 880
    frames = []
    for index in range(12):
        frame = base.copy()
        draw = ImageDraw.Draw(frame)
        x = 42 + (796 - 72) * index / 11
        draw.rounded_rectangle(
            (42 * scale, 116 * scale, 838 * scale, 120 * scale), radius=2, fill='#293751',
        )
        draw.rounded_rectangle(
            (x * scale, 116 * scale, (x + 72) * scale, 120 * scale), radius=2, fill='#86aaff',
        )
        # A highlight moves *inside* the real progress; numbers never change.
        if card.progress:
            y = (145 + len(card.rows) * 58) * scale
            filled = 796 * max(0, min(100, card.progress)) / 100 * scale
            segment = min(40 * scale, filled)
            start = 42 * scale + max(0, filled - segment) * index / 11
            draw.rectangle((start, y + 2, start + segment, y + 5), fill='#d7e6ff')
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
