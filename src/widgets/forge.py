"""Compact, supersampled katana forge. Deterministic particles; no user state.

The silhouette has sori (curvature), an asymmetric kissaki, a small oval tsuba,
wrapped tsuka and a single cutting edge. It is intentionally not a broadsword.
"""

import math
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from src.core.visuals import Visuals
from src.widgets.rendering import PALETTES, font

WIDTH, HEIGHT = 760, 320
SCALE = 2
STRIKES = (0.22, 0.46)
FRAME_COUNT = 40


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
    school = min(4, max(0, int(receipt.after // 20)))
    silk, aura = (
        ("#233e74", "#accfff"), ("#873824", "#ff9b43"),
        ("#b7c8cf", "#bcefff"), ("#593780", "#d6b3ff"),
        ("#305843", "#c4e092"),
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
    # Tsuka, kashira, alternating silk wrap and menuki.
    poly([(49, 154), (165, 146), (166, 160), (50, 169)], silk)
    for x in range(57, 160, 13):
        yy = 154 - (x - 49) * 0.068
        poly([(x, yy), (x + 9, yy + 6), (x + 1, yy + 13), (x - 7, yy + 7)], "#a68c77")
        poly([(x, yy + 4), (x + 3, yy + 6), (x, yy + 9), (x - 3, yy + 7)], "#211f29")
    poly([(45, 153), (52, 153), (53, 169), (46, 170)], "#b9a076")
    draw.ellipse(
        (163 * SCALE, 136 * SCALE, 177 * SCALE, 169 * SCALE),
        fill="#c8a66c",
        outline="#f6d9a1",
        width=SCALE,
    )
    box((177, 147, 187, 161), "#c8a66c", 2)
    hot = (int(215 + 40 * heat), int(229 - 83 * heat), int(240 - 175 * heat))
    poly(outline, hot)
    # Shinogi ridge and wavy hamon follow the curved, single-edged blade.
    ridge = [(185 + length * u / 30, 152 - 21 * (u / 30) ** 2) for u in range(30)]
    line(ridge, "#8fa8bb")
    hamon = [
        (187 + (length - 27) * u / 90, 157 - 18 * (u / 90) ** 2 + math.sin(u * 0.7) * 1.1)
        for u in range(91)
    ]
    line(hamon, "#fff2d6" if heat else "#f3fbff")
    tip_x = 185 + length
    line([(tip_x - 21, 130), (tip_x - 12, 141)], "#9bafbe")

    # Enchanted inlay follows the curved blade. Reveal it after quenching;
    # all light is masked to the steel and confined to the art viewport.
    reveal = min(1.0, max(0.0, (phase - 0.56) / 0.28))
    if reveal:
        mask = Image.new("L", image.size)
        ImageDraw.Draw(mask).polygon(
            [(round(x * SCALE), round(y * SCALE)) for x, y in outline], fill=255)
        magic = Image.new("RGBA", image.size)
        md = ImageDraw.Draw(magic)
        from PIL import ImageColor
        rgb = ImageColor.getrgb(aura)
        points = []
        for j in range(65):
            u = j / 64
            x = 194 + (length - 24) * u
            y = 151 - 20 * u * u
            if school in (1, 3):  # molten seams / lightning
                y += math.sin(j * 2.3) * 4 + math.sin(j * 0.8) * 2
            else:
                y += math.sin(j * 0.34) * 3
            points.append((round(x * SCALE), round(y * SCALE)))
        md.line(points, fill=(*rgb, round(100 * reveal)), width=2 * SCALE)
        for j in range(3, 62, 7):
            x, y = points[j]
            direction = -1 if j % 2 else 1
            md.line([(x, y), (x + 6 * SCALE, y + direction * 6 * SCALE),
                     (x + 13 * SCALE, y + direction * 7 * SCALE)],
                    fill=(*rgb, round(90 * reveal)), width=SCALE)
            if school == 0:  # constellation pinpoints
                md.ellipse((x-SCALE, y-SCALE, x+SCALE, y+SCALE), fill=(255, 249, 216, 255))
        bloom = magic.filter(ImageFilter.GaussianBlur(3 * SCALE))
        magic = Image.alpha_composite(bloom, magic)
        magic.putalpha(ImageChops.multiply(magic.getchannel("A"), mask))
        image = Image.alpha_composite(image.convert("RGBA"), magic).convert("RGB")
        draw = ImageDraw.Draw(image)

    # Expanding impact rings distinguish growth (blue) from failed tempering
    # (amber). Geometry stays inside the forge region, never over the receipt.
    for strike in STRIKES:
        age = phase - strike
        if 0 <= age < 0.13:
            t = age / 0.13
            radius = 8 + 74 * t
            color = tuple(round(v * (1 - 0.65 * t)) for v in
                          ((142, 220, 255) if receipt.success else (255, 151, 79)))
            draw.ellipse(((397-radius)*SCALE, (151-radius*0.32)*SCALE,
                          (397+radius)*SCALE, (151+radius*0.32)*SCALE),
                         outline=color, width=SCALE)

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
    summary = f"{blade} · {rank}  |  Попытка: {receipt.cost:,.0f} монет"
    size = 13
    while size > 10 and draw.textlength(summary, font=font(size * SCALE)) > 704 * SCALE:
        size -= 1
    text(28, 270, summary, size, c["text"])
    text(28, 291, "Ковка показана схематично · не в масштабе", 10, c["muted"])
    return image.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
