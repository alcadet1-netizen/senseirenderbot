"""A read-only receipt for one completed katana upgrade, not a second attempt.

The blade movement is deliberately schematic so a 0.03 cm change is visible.
All numeric labels are the real before/after values and never animate or reroll.
"""
from dataclasses import dataclass
from functools import lru_cache
from io import BytesIO

from PIL import Image, ImageDraw

from src.core.visuals import Visuals
from src.widgets.cards import Card, label, number
from src.widgets.rendering import PALETTES, font, wrap


@dataclass(frozen=True)
class KatanaUpgrade:
    name: str
    before: float
    after: float
    cost: float
    success: bool

    @classmethod
    def from_result(cls, name: str, result: dict) -> 'KatanaUpgrade':
        after = number(result['new_length'])
        success = bool(result['is_upgraded'])
        # Compatibility for older service adapters. Current service provides the
        # actual previous length, which matters when a failure hits the zero floor.
        before = result.get('old_length')
        if before is None:
            before = after - number(result['growth']) if success else after + number(result['growth'])
        return cls(label(name, 40), number(before), after, number(result['cost']), success)

    @property
    def delta(self) -> float:
        value = round(self.after - self.before, 2)
        return 0.0 if value == 0 else value  # No negative zero in the receipt.

    @property
    def status(self) -> str:
        return 'КАТАНА УЛУЧШЕНА' if self.success else 'ЗАКАЛКА НЕ УДАЛАСЬ'

    def as_card(self) -> Card:
        blade, rank = Visuals.get_katana_art(self.after)
        return Card(self.status, self.name, (
            ('Было', f'{self.before:.2f} см'),
            ('Изменение', f'{self.delta:+.2f} см'),
            ('Стало', f'{self.after:.2f} см'),
            ('Стоимость попытки', f'{self.cost:,.0f} монет'),
            ('Клинок', blade), ('Ранг', rank),
        ), art=Visuals.get_katana_art_ascii(self.after))


def render_upgrade(receipt: KatanaUpgrade, phase: float = 1.0) -> Image.Image:
    """Fixed 760x490 receipt. All stats, including the final outcome, are always visible."""
    c = PALETTES['dark']
    accent = c['accent'] if receipt.success else '#ffc078'
    width, height = 760, 490
    image = Image.new('RGB', (width, height), c['bg'])
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((12, 12, width - 12, height - 12), radius=26, fill=c['panel'])
    draw.text((32, 30), 'SENSEI  /  КУЗНИЦА', font=font(15), fill=accent)
    draw.text((32, 62), receipt.status, font=font(25), fill=c['text'])
    for i, line in enumerate(wrap(draw, receipt.name, 17, 696)):
        draw.text((32, 101 + i * 22), line, font=font(17), fill=c['muted'])
    # A fractional increase would be invisible at true scale. Show schematic
    # blade growth/shrinkage, with an explicit note directly below the drawing.
    phase = max(0.0, min(1.0, phase))
    if receipt.delta > 0:
        length = 305 + 165 * phase
    elif receipt.delta < 0:
        length = 470 - 165 * phase
    else:
        length = 390
    y, start = 192, 168
    draw.rounded_rectangle((48, y - 10, 144, y + 10), radius=7, fill='#8b6b55')
    for x in range(58, 142, 14):
        draw.line((x, y - 9, x + 7, y + 9), fill='#c4a78e', width=2)
    draw.rounded_rectangle((146, y - 30, 163, y + 30), radius=5, fill=accent)
    tip = start + length
    draw.polygon([(start, y - 10), (tip - 26, y - 10), (tip, y),
                  (tip - 26, y + 10), (start, y + 10)], fill=c['text'])
    draw.line((start + 5, y, tip - 30, y), fill=accent, width=2)
    draw.text((32, 237), 'Клинок показан схематично · не в масштабе', font=font(15), fill=c['muted'])
    columns = [('БЫЛО', f'{receipt.before:.2f} см'), ('ИЗМЕНЕНИЕ', f'{receipt.delta:+.2f} см'),
               ('СТАЛО', f'{receipt.after:.2f} см')]
    for i, (title, value) in enumerate(columns):
        x = 32 + i * 236
        draw.rounded_rectangle((x, 280, x + 224, 358), radius=14, fill=c['tile'])
        draw.text((x + 14, 290), title, font=font(13), fill=c['muted'])
        size = 25
        while size > 12 and draw.textlength(value, font=font(size)) > 196:
            size -= 1
        draw.text((x + 14, 315), value, font=font(size), fill=accent if i == 1 else c['text'])
    blade, rank = Visuals.get_katana_art(receipt.after)
    for i, line in enumerate(wrap(draw, f'{blade}  ·  Ранг {rank}', 18, 696)):
        draw.text((32, 381 + i * 22), line, font=font(18), fill=c['text'])
    draw.text((32, 436), f'Стоимость попытки: {receipt.cost:,.0f} монет', font=font(17), fill=c['muted'])
    return image


def to_upgrade_png(receipt: KatanaUpgrade) -> bytes:
    output = BytesIO()
    render_upgrade(receipt).save(output, format='PNG')
    return output.getvalue()


@lru_cache(maxsize=8)
def to_upgrade_gif(receipt: KatanaUpgrade) -> bytes:
    # Palette sampled from the final state includes all text/blade colours.
    palette = render_upgrade(receipt).quantize(colors=96)
    frames = []
    for index in range(12):
        t = index / 11
        phase = 1 - (1 - t) ** 3  # ease-out, holds the accurate final frame.
        frame = render_upgrade(receipt, phase).quantize(palette=palette, dither=Image.Dither.NONE)
        frames.append(frame)
    output = BytesIO()
    frames[0].save(output, format='GIF', save_all=True, append_images=frames[1:],
                   duration=[100] * 11 + [1500], loop=0, disposal=1, optimize=False)
    result = output.getvalue()
    if len(result) > 5 * 1024 * 1024:
        raise ValueError('Katana animation exceeds the local 5 MiB budget')
    return result


def to_upgrade_html(receipt: KatanaUpgrade) -> str:
    """Offline widget-profile-1 source; not a Bot API message payload."""
    from src.widgets.cards import to_html, validate_html
    if receipt.delta > 0:
        start, end = 52, 84
    elif receipt.delta < 0:
        start, end = 84, 52
    else:
        start = end = 68
    source = to_html(receipt.as_card())
    css = f'''
.forge{{display:flex;align-items:center;height:44px}}
.grip{{width:36px;height:12px;border-radius:4px;background:#967458}}
.edge{{height:8px;border-radius:0 8px 8px 0;width:{end}%;background:var(--tg-theme-button-color,#6ab3f3);animation:forge 900ms ease-out}}
@keyframes forge{{from{{width:{start}%}}to{{width:{end}%}}}}
@media(prefers-reduced-motion:reduce){{.edge{{animation:none}}}}
'''
    source = source.replace('</style>', css + '</style>')
    source = source.replace('<div id="stats">', '<div class="forge"><div class="grip"></div><div class="edge"></div></div><div class="hint">Схематично · не в масштабе</div><div id="stats">')
    return validate_html(source)
