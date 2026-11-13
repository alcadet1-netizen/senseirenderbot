"""Compact, supersampled katana forge. Deterministic particles; no user state.

The silhouette has sori (curvature), an asymmetric kissaki, a small oval tsuba,
wrapped tsuka and a single cutting edge. It is intentionally not a broadsword.
"""

import math
from functools import lru_cache
from pathlib import Path
from PIL import Image, ImageChops, ImageDraw, ImageFilter

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
def katana_handle(school):
    art = katana_art(school)
    return art.crop((0, 0, 340, art.height)).resize(
        (145*SCALE, 95*SCALE), Image.Resampling.LANCZOS)


def paint_katana(image, school, length):
    art = katana_art(school)
    # Keep the ornate guard/handle rigid; only the steel changes length.
    split = 340
    handle = katana_handle(school)
    blade = art.crop((split, 0, art.width, art.height)).resize((round((length+12)*SCALE), 95*SCALE), Image.Resampling.LANCZOS)
    sprite = Image.new("RGB", (handle.width+blade.width, 95*SCALE))
    sprite.paste(handle, (0, 0)); sprite.paste(blade, (handle.width, 0))
    # Feather the photographic backdrop into the forge, not over the labels.
    mask = Image.new("L", sprite.size, 255)
    md = ImageDraw.Draw(mask)
    for inset in range(14*SCALE):
        alpha = round(255 * inset / (14*SCALE))
        md.rectangle((inset, inset, sprite.width-1-inset, sprite.height-1-inset), outline=alpha)
    image.paste(sprite, (40*SCALE, 96*SCALE), mask)
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
    t = 1 - (1 - t) ** 3
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
    silk, aura = (
        ("#233e74", "#accfff"), ("#873824", "#ff9b43"),
        ("#b7c8cf", "#bcefff"), ("#593780", "#d6b3ff"),
        ("#305843", "#c4e092"),
    )[school % 5]
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
    image = paint_katana(image, school, length)
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
        mask = Image.new("L", image.size)
        ImageDraw.Draw(mask).polygon(
            [(int(x * SCALE), int(y * SCALE)) for x, y in outline], fill=255
        )
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
