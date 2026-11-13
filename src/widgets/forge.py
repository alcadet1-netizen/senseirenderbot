"""Compact, supersampled katana forge. Deterministic particles; no user state.

The silhouette has sori (curvature), an asymmetric kissaki, a small oval tsuba,
wrapped tsuka and a single cutting edge. It is intentionally not a broadsword.
"""

import math
from functools import lru_cache
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageColor

from src.core.visuals import Visuals
from src.widgets.katana_models import MODEL_NAMES, model_index, model_path
from src.widgets.rendering import PALETTES, font

WIDTH, HEIGHT = 760, 320
SCALE = 2
STRIKES = (0.22, 0.46)
FRAME_COUNT = 40


@lru_cache(maxsize=15)
def katana_art(school):
    """Normalized, bundled model panel; cached read-only source."""
    with Image.open(model_path(school)) as source:
        return source.convert("RGB")


@lru_cache(maxsize=15)
def katana_layers(school):
    """Geometric art-direction masks, not automatic background segmentation.

    Isolate the central weapon strip; outer landscape stays out of moving layers.
    Small painted details inside the silhouette are intentionally retained.
    """
    art = katana_art(school).convert("RGBA")
    mask = Image.new("L", art.size)
    md = ImageDraw.Draw(mask)
    md.polygon([(8, 47), (285, 44), (306, 12), (352, 17), (369, 58),
                (828, 44), (807, 78), (350, 105), (342, 138),
                (298, 136), (284, 104), (8, 98)], fill=255)
    art.putalpha(mask.filter(ImageFilter.GaussianBlur(2.0)))
    return art.crop((0, 0, 340, art.height)), art.crop((340, 0, art.width, art.height))


@lru_cache(maxsize=15)
def katana_handle(school):
    return katana_layers(school)[0].resize((145*SCALE, 95*SCALE), Image.Resampling.LANCZOS)


def model_mix(before, after, phase):
    old, new = model_index(before), model_index(after)
    t = min(1.0, max(0.0, (phase - 0.52) / 0.24))
    t = t*t*(3-2*t)
    return old, new, t


def paint_katana(image, school, length):
    # Transparent weapon layers: the workshop itself never stretches.
    handle = katana_handle(school)
    blade = katana_layers(school)[1].resize(
        (round((length+12)*SCALE), 95*SCALE), Image.Resampling.LANCZOS)
    image.paste(handle, (40*SCALE, 96*SCALE), handle)
    image.paste(blade, (185*SCALE, 96*SCALE), blade)
    return image


def blade_outline(length):
    start, y = 185, 147
    spine = [(start + length * u / 24, y - 21 * (u / 24) ** 2) for u in range(25)]
    tip = (start + length + 12, y - 27)
    edge = [(start + (length - 22) * u / 24, y + 13 - 18 * (u / 24) ** 2) for u in range(25)]
    return spine + [tip] + list(reversed(edge))


def blade_length(receipt, phase):
    # Forging first, reveal second. Actual delta remains printed throughout.
    t = max(0, min(1, (phase - 0.30) / 0.48))
    t = t * t * t * (t * (t * 6 - 15) + 10)  # zero velocity/acceleration at both ends
    if receipt.delta > 0:
        return 360 + 130 * t
    if receipt.delta < 0:
        return 490 - 130 * t
    return 425


def render_forge(receipt, phase=1.0):
    phase = max(0.0, min(1.0, phase))
    c = PALETTES["dark"]
    # Cosmetic schools are deterministic, never another economic roll.
    school = model_index(receipt.after)
    aura = (
        "#e2c58f", "#bcefff", "#ff9b43", "#83cfff", "#cd9bff",
        "#ff9b43", "#bcefff", "#b6a0ff", "#c7b9ff", "#a6dd78",
        "#ff9b43", "#bcefff", "#ff6c94", "#c08cff", "#ffe1a0",
    )[school]
    accent = aura if receipt.success else "#ffc078"
    image = Image.new("RGB", (WIDTH * SCALE, HEIGHT * SCALE), c["bg"])
    draw = ImageDraw.Draw(image)

    def box(coords, fill, radius=0, outline=None, width=1):
        coords = tuple(round(v * SCALE) for v in coords)
        if radius:
            draw.rounded_rectangle(
                coords, radius=radius * SCALE, fill=fill, outline=outline, width=width * SCALE
            )
        else:
            draw.rectangle(coords, fill=fill)

    def poly(points, fill):
        draw.polygon([(round(x * SCALE), round(y * SCALE)) for x, y in points], fill=fill)

    def line(points, fill, width=1):
        draw.line(
            [(round(x * SCALE), round(y * SCALE)) for x, y in points],
            fill=fill,
            width=width * SCALE,
        )

    def text(x, y, value, size, fill):
        draw.text((x * SCALE, y * SCALE), value, font=font(size * SCALE), fill=fill)

    box((10, 8, 750, 312), c["panel"], 22)
    text(28, 20, "SENSEI  /  КУЗНИЦА", 12, accent)
    text(28, 42, receipt.status, 20, c["text"])
    # Name is secondary; shorten by measured width with an explicit ellipsis.
    name = receipt.name
    while name and draw.textlength(name, font=font(14 * SCALE)) > 690 * SCALE:
        name = name[:-2] + "…"
    text(28, 70, name, 14, c["muted"])

    # Subtle workshop platform, anvil and a cool reflection under the blade.
    line([(30, 190), (726, 190)], "#293c4b")
    poly(
        [
            (349, 170),
            (455, 170),
            (442, 180),
            (418, 180),
            (424, 188),
            (373, 188),
            (379, 179),
            (362, 179),
        ],
        "#3b4a55",
    )
    length = blade_length(receipt, phase)
    outline = blade_outline(length)
    heat = max(max(0.0, 1 - abs(phase - s) / 0.15) for s in STRIKES) if phase < 0.7 else 0
    if heat:
        glow = Image.new("RGBA", image.size)
        gd = ImageDraw.Draw(glow)
        gd.ellipse(
            (270 * SCALE, 125 * SCALE, 535 * SCALE, 176 * SCALE),
            fill=(255, 95, 24, int(100 * heat)),
        )
        glow = glow.filter(ImageFilter.GaussianBlur(14 * SCALE))
        clipped = Image.new("RGBA", image.size)
        clipped.paste(glow.crop((0, 96 * SCALE, WIDTH * SCALE, 191 * SCALE)), (0, 96 * SCALE))
        image = Image.alpha_composite(image.convert("RGBA"), clipped).convert("RGB")
        draw = ImageDraw.Draw(image)
    # Reference artwork replaces the old schematic line blade entirely.
    old_school, new_school, mix = model_mix(receipt.before, receipt.after, phase)
    if old_school != new_school and mix < 1:
        old_image = paint_katana(image.copy(), old_school, length)
        new_image = paint_katana(image.copy(), new_school, length)
        image = Image.blend(old_image, new_image, mix)
    else:
        image = paint_katana(image, new_school, length)
    draw = ImageDraw.Draw(image)

    # Two actual hammer swings. Particles are ballistic and deterministic.
    for strike in STRIKES:
        if strike - 0.12 <= phase <= strike + 0.035:
            travel = min(1.0, max(0.0, (phase - strike + 0.12) / 0.12))
            angle = -0.9 * (1 - travel)
            pivot = (395, 117)

            def transform(points):
                return [
                    (
                        pivot[0] + x * math.cos(angle) - y * math.sin(angle),
                        pivot[1] + x * math.sin(angle) + y * math.cos(angle),
                    )
                    for x, y in points
                ]

            poly(transform([(-5, -24), (4, -24), (4, 22), (-5, 22)]), "#b18761")
            poly(transform([(-27, 15), (26, 15), (28, 31), (-27, 31)]), "#8a9caa")
            line(transform([(-25, 17), (24, 17)]), "#dfedf4", 2)
        age = phase - strike
        if 0 <= age <= 0.21:
            t = age / 0.21
            for j in range(20):
                angle = math.pi * (1.08 + (j * 0.61803398875 % 1) * 0.83)
                speed = 35 + (j * 29 % 97)
                x = 397 + math.cos(angle) * speed * t
                y = max(98, 149 + math.sin(angle) * speed * t + 34 * t * t)
                tail = (
                    x - math.cos(angle) * (3 + 5 * (1 - t)),
                    y - math.sin(angle) * (3 + 5 * (1 - t)),
                )
                color = "#fff0bd" if j % 3 == 0 else "#ff9c45"
                line([tail, (x, y)], color, 1)
            if age < 0.035:
                line([(388, 145), (403, 153)], "#fff7d0", 3)
    # Quench: thin rising vapour wisps appear only after the last strike.
    if 0.54 < phase < 0.76:
        t = (phase - 0.54) / 0.22
        for j in range(4):
            points = [
                (310 + j * 55 + math.sin(u * 0.3 + j) * 4, 144 - u * 0.55 - t * 15)
                for u in range(0, int(12 + 24 * t))
            ]
            line(points, "#708e9e", 1)

    # Final polish travels only along the blade, clipped to its silhouette.
    if 0.70 < phase < 0.98:
        # Follow the actual bright steel/ornaments, not the obsolete schematic
        # outline. Restrict the mask to the blade half of the art viewport.
        mask = Image.new("L", image.size)
        steel = image.convert("L").crop((185*SCALE, 96*SCALE,
                                        round((197+length)*SCALE), 191*SCALE))
        steel = steel.point(lambda v: min(255, max(0, (v-75)*2)))
        mask.paste(steel, (185*SCALE, 96*SCALE))
        streak = Image.new("RGB", image.size, "#ffffff")
        band = Image.new("L", image.size)
        x = 185 + length * (phase - 0.70) / 0.28
        ImageDraw.Draw(band).polygon(
            [
                (int((x - 20) * SCALE), 110 * SCALE),
                (int((x - 7) * SCALE), 110 * SCALE),
                (int((x + 13) * SCALE), 170 * SCALE),
                (int(x * SCALE), 170 * SCALE),
            ],
            fill=210,
        )
        image.paste(streak, (0, 0), ImageChops.multiply(mask, band))
        draw = ImageDraw.Draw(image)

    # A restrained final energy reveal, fixed to the blade and fading to a
    # clean held frame. No camera shake, global flashing or random rerolls.
    if 0.76 < phase < 0.98:
        t = (phase - 0.76) / 0.22
        intensity = math.sin(math.pi * t)
        fx = Image.new("RGBA", image.size)
        fd = ImageDraw.Draw(fx)
        rgb = ImageColor.getrgb(aura if receipt.success else "#ed9265")
        for j in range(12):
            u = (j + 0.5) / 12
            x = (190 + length * u) * SCALE
            y = (145 - 15*u*u + math.sin(j*2.4)*19* t) * SCALE
            r = (1 + 2*intensity) * SCALE
            alpha = round(200 * intensity)
            fd.line((x-r, y, x+r, y), fill=(*rgb, alpha), width=SCALE)
            fd.line((x, y-r, x, y+r), fill=(*rgb, alpha), width=SCALE)
        fx = Image.alpha_composite(fx.filter(ImageFilter.GaussianBlur(2*SCALE)), fx)
        viewport = Image.new("RGBA", image.size)
        viewport.paste(fx.crop((0, 96*SCALE, WIDTH*SCALE, 191*SCALE)), (0, 96*SCALE))
        image = Image.alpha_composite(image.convert("RGBA"), viewport).convert("RGB")
        draw = ImageDraw.Draw(image)

    # All numeric labels stay outside the forge region, invariant across frames.
    columns = [
        ("БЫЛО", f"{receipt.before:.2f} см"),
        ("ИЗМЕНЕНИЕ", f"{receipt.delta:+.2f} см"),
        ("СТАЛО", f"{receipt.after:.2f} см"),
    ]
    for i, (title, value) in enumerate(columns):
        x = 28 + i * 238
        box((x, 201, x + 228, 259), c["tile"], 10)
        text(x + 12, 207, title, 10, c["muted"])
        size = 21
        while size > 11 and draw.textlength(value, font=font(size * SCALE)) > 204 * SCALE:
            size -= 1
        text(x + 12, 226, value, size, accent if i == 1 else c["text"])
    blade, rank = Visuals.get_katana_art(receipt.after)
    summary = f"{MODEL_NAMES[school]} · {school+1}/15  |  Попытка: {receipt.cost:,.0f} монет"
    size = 13
    while size > 10 and draw.textlength(summary, font=font(size * SCALE)) > 704 * SCALE:
        size -= 1
    text(28, 270, summary, size, c["text"])
    text(28, 291, "Ковка показана схематично · не в масштабе", 10, c["muted"])
    return image.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
