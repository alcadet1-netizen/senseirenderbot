"""A read-only receipt for one completed katana upgrade, not a second attempt.

The blade movement is deliberately schematic so a 0.03 cm change is visible.
All numeric labels are the real before/after values and never animate or reroll.
"""

from dataclasses import dataclass
from functools import lru_cache
from io import BytesIO

from PIL import Image

from src.core.visuals import Visuals
from src.widgets.katana_models import katana_name
from src.widgets.cards import Card, label, number
from src.widgets.forge import FRAME_COUNT, HEIGHT, WIDTH, render_forge


@dataclass(frozen=True)
class KatanaUpgrade:
    name: str
    before: float
    after: float
    cost: float
    success: bool

    @classmethod
    def from_result(cls, name: str, result: dict) -> "KatanaUpgrade":
        after = number(result["new_length"])
        success = bool(result["is_upgraded"])
        # Compatibility for older service adapters. Current service provides the
        # actual previous length, which matters when a failure hits the zero floor.
        before = result.get("old_length")
        if before is None:
            before = (
                after - number(result["growth"]) if success else after + number(result["growth"])
            )
        return cls(label(name, 40), number(before), after, number(result["cost"]), success)

    @property
    def delta(self) -> float:
        value = round(self.after - self.before, 2)
        return 0.0 if value == 0 else value  # No negative zero in the receipt.

    @property
    def status(self) -> str:
        return "КАТАНА УЛУЧШЕНА" if self.success else "ЗАКАЛКА НЕ УДАЛАСЬ"

    def as_card(self) -> Card:
        blade, rank = Visuals.get_katana_art(self.after)
        return Card(
            self.status,
            self.name,
            (
                ("Было", f"{self.before:.2f} см"),
                ("Изменение", f"{self.delta:+.2f} см"),
                ("Стало", f"{self.after:.2f} см"),
                ("Стоимость попытки", f"{self.cost:,.0f} монет"),
                ("Клинок", katana_name(self.after)),
                ("Ранг", rank),
            ),
            art=Visuals.get_katana_art_ascii(self.after),
        )


def render_upgrade(receipt: KatanaUpgrade, phase: float = 1.0) -> Image.Image:
    """Compact 760x320 forge receipt, with a curved, single-edged katana."""
    return render_forge(receipt, phase)


def to_upgrade_png(receipt: KatanaUpgrade) -> bytes:
    output = BytesIO()
    render_upgrade(receipt).save(output, format="PNG")
    return output.getvalue()


@lru_cache(maxsize=8)
def to_upgrade_gif(receipt: KatanaUpgrade) -> bytes:
    # Include hot steel, sparks and the cooled blade in one stable palette.
    atlas = Image.new("RGB", (WIDTH, HEIGHT * 6))
    for i, phase in enumerate((0.0, 0.22, 0.46, 0.65, 0.84, 1.0)):
        atlas.paste(render_upgrade(receipt, phase), (0, i * HEIGHT))
    palette = atlas.quantize(colors=192)
    frames = [
        render_upgrade(receipt, i / (FRAME_COUNT - 1)).quantize(
            palette=palette,
            dither=Image.Dither.NONE,
        )
        for i in range(FRAME_COUNT)
    ]
    output = BytesIO()
    frames[0].save(
        output,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=[65] * (FRAME_COUNT - 1) + [1400],
        loop=0,
        disposal=1,
        optimize=False,
    )
    result = output.getvalue()
    if len(result) > 5 * 1024 * 1024:
        raise ValueError("Katana animation exceeds the local 5 MiB budget")
    return result


def to_upgrade_html(receipt: KatanaUpgrade) -> str:
    """Offline widget-profile-1 source; not a Bot API message payload."""
    from src.widgets.cards import to_html, validate_html

    if receipt.delta > 0:
        start, end = 0.74, 1
    elif receipt.delta < 0:
        start, end = 1, 0.74
    else:
        start = end = 0.87
    source = to_html(receipt.as_card())
    # A notification is a read-only receipt: no navigation or toggle buttons.
    import re

    source = re.sub(r"<button[^>]*>.*?</button>", "", source, flags=re.S)
    source = re.sub(r"<script>.*?</script>", "", source, flags=re.S)
    css = f"""
.forge{{height:66px}}
.edge{{transform-origin:168px 50px;transform:scaleX({end});animation:forge 1400ms ease-out}}
@keyframes forge{{from{{transform:scaleX({start})}}to{{transform:scaleX({end})}}}}
@media(prefers-reduced-motion:reduce){{.edge{{animation:none}}}}
"""
    drawing = """<svg class="forge" viewBox="0 0 710 90" width="100%" height="66">
<path d="M30 53L146 45L147 59L31 67Z" fill="#967458"/>
<path d="M40 53l12 10 12-13 12 11 12-13 12 11 12-13 12 11 12-13" fill="none" stroke="#d4b997" stroke-width="3"/>
<ellipse cx="158" cy="51" rx="7" ry="18" fill="#c8a66c"/>
<g class="edge"><path d="M168 45Q430 45 655 20L680 7 656 34Q440 63 168 58Z" fill="#c9dce9"/>
<path d="M171 55Q400 58 652 30" fill="none" stroke="#ffffff" stroke-width="2"/></g></svg>"""
    source = source.replace("</style>", css + "</style>")
    source = source.replace(
        '<div id="stats">',
        drawing + '<div class="hint">Схематично · не в масштабе</div><div id="stats">',
    )
    return validate_html(source)
