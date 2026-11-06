"""One bounded data model for native-widget HTML and Bot API image fallback.

HTML is a widget *source*, not Telegram message HTML. It must be delivered as
inputMediaWidget by a layer-233 transport; sending it as a document is not enough.
No network, bot credentials, financial actions, or user-controlled scripts.
"""
from dataclasses import dataclass
from html import escape
from io import BytesIO
import math
import zlib


@dataclass(frozen=True)
class Card:
    title: str
    subtitle: str
    rows: tuple[tuple[str, str], ...]
    progress: int | None = None
    art: str = ""


def label(value: object, limit: int = 48) -> str:
    # Keep control characters and surrogate code points out of UTF-8 payloads.
    text = ''.join(c for c in str(value or '') if c.isprintable() and not 0xD800 <= ord(c) <= 0xDFFF)
    return text[:limit]


def number(value: object) -> float:
    try:
        result = float(value)
        return max(0.0, min(result, 1e15)) if math.isfinite(result) else 0.0
    except (TypeError, ValueError, OverflowError):
        return 0.0


def profile_card(profile: dict) -> Card:
    from src.core.constants import LEVEL_NAMES, LEVEL_XP_REQUIREMENTS
    from src.core.visuals import Visuals

    xp = int(number(profile.get('xp')))
    level = int(number(profile.get('level')))
    max_level = max(LEVEL_XP_REQUIREMENTS)
    next_xp = int(number(profile.get('xp_next')))
    current = LEVEL_XP_REQUIREMENTS.get(level, 0)
    maxed = level >= max_level
    progress = 100 if maxed or next_xp <= current else round(100 * (xp - current) / (next_xp - current))
    coins = number(profile.get('coins'))
    has_katana = bool(profile.get('has_katana', False))
    length = number(profile.get('katana_length'))
    katana_name, rank = Visuals.get_katana_art(length) if has_katana else ('Нет катаны', '')
    rows = (
        ('Уровень', str(level)),
        ('Звание', label(profile.get('level_name') or LEVEL_NAMES.get(level, 'Ученик'))),
        ('Роль', label(profile.get('role') or 'Не назначена')),
        ('Опыт', f'{xp:,} / {next_xp:,} XP' if not maxed else f'{xp:,} XP · MAX'),
        ('До следующего', 'Максимальный уровень' if maxed else f'{max(0, next_xp - xp):,} XP'),
        ('Монеты', f'{coins:,.2f}'),
        # Same illustrative conversion as /mysensei, not an exchange quote.
        ('Оценка баланса', f'≈ {coins * 0.0002:,.2f} USDT'),
        ('Билеты', str(int(number(profile.get('tickets'))))),
        ('Сообщения', str(int(number(profile.get('messages'))))),
        ('Серия daily', f'{int(number(profile.get("streak")))} дн.'),
        ('Достижения', str(int(number(profile.get('achievements_count'))))),
        ('Победы / поражения', f'{int(number(profile.get("wins")))} / {int(number(profile.get("losses")))}'),
        ('Катана', f'{length:.1f} см' if has_katana else 'Нет катаны'),
    )
    if has_katana:
        rows += (('Клинок', label(katana_name)), ('Ранг клинка', rank))
    return Card(
        'МОЙ СЕНСЕЙ', label(profile.get('username') or profile.get('first_name') or 'Ученик'),
        rows, max(0, min(100, progress)),
        Visuals.get_katana_art_ascii(length) if has_katana else '',
    )


def top_card(users: list[dict]) -> Card:
    return Card('ЗАЛ СЛАВЫ', 'Рейтинг по опыту · снимок на момент отправки', tuple(
        (f'{i}. {label(user.get("username") or "Ученик", 30)}',
         f'{int(number(user.get("xp"))):,} XP')
        for i, user in enumerate(users[:10], 1)
    ) or (('Пока нет участников', '—'),))


def validate_html(source: str) -> str:
    if '\x00' in source:
        raise ValueError('Widget HTML contains NUL')
    raw = source.encode('utf-8')
    if len(raw) > 32768 or len(zlib.compress(raw, 9)) > 4096:
        raise ValueError('Widget exceeds Telegram limits: 32 KiB UTF-8 / 4 KiB zlib-9')
    return source


def to_html(card: Card) -> str:
    """Self-contained, theme-aware HTML; user data enters text nodes only."""
    rows = ''.join(f'<div class="row"><span>{escape(k)}</span><b>{escape(v)}</b></div>'
                   for k, v in card.rows)
    progress = '' if card.progress is None else (
        f'<div class="track"><div class="fill" style="width:{max(0, min(100, int(card.progress)))}%"></div></div>'
        f'<div class="hint">Прогресс уровня: {max(0, min(100, int(card.progress)))}%</div>'
    )
    art = '<pre class="blade">' + escape(card.art) + '</pre>' if card.art else ''
    return validate_html('''<!doctype html><html><head><meta charset="utf-8"><style>
body{margin:0;padding:12px 20px;font-family:system-ui;color:var(--tg-theme-text-color,#e8edf6);background:var(--tg-theme-bg-color,#101827)}
h2{font-size:18px;margin:0 0 6px;color:var(--tg-theme-button-color,#709cff)}
.hint{font-size:11px;color:var(--tg-theme-hint-color,#8698b4);margin:8px 0}
.row{display:flex;justify-content:space-between;gap:12px;font-size:12px;line-height:16px;padding:4px 0;border-bottom:1px solid var(--tg-theme-secondary-bg-color,#253047)}
.row span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.row b{overflow-wrap:anywhere;text-align:right;max-width:62%}
.track{height:6px;background:var(--tg-theme-secondary-bg-color,#253047);border-radius:3px;margin-top:14px}
.fill{height:6px;background:var(--tg-theme-button-color,#709cff);border-radius:3px}
.blade{font-size:13px;color:var(--tg-theme-button-color,#709cff);white-space:pre-wrap}
@keyframes arrival{from{transform:translateX(8px)}to{transform:translateX(0)}}
@keyframes charge{from{transform:scaleX(0)}to{transform:scaleX(1)}}
.row{animation:arrival 350ms ease-out}.fill{transform-origin:left;animation:charge 700ms ease-out}
button{margin-top:12px;padding:8px 12px}
</style></head><body><h2>''' + escape(card.title) + '</h2><div class="hint">' + escape(card.subtitle) +
        '</div><div id="stats">' + rows + progress + art + '''</div>
<button id="toggle">Скрыть / показать</button><div class="hint">Снимок · обновление кнопкой под сообщением</div>
<script>
var stats=document.getElementById('stats');
document.getElementById('toggle').onclick=function(){stats.style.display=stats.style.display==='none'?'block':'none';};
if(window.TelegramWidget){window.TelegramWidget.ready();}
</script></body></html>''')


def to_png(card: Card) -> bytes:
    """Bot API compatibility view. No HTML/JS is executed by the server."""
    from PIL import Image, ImageDraw, ImageFont
    def font(size):
        # DejaVu is installed explicitly in the production Docker image.
        try:
            return ImageFont.truetype('DejaVuSans.ttf', size)
        except OSError:
            return ImageFont.load_default(size=size)
    width = 880
    height = 205 + 58 * len(card.rows) + (65 if card.progress is not None else 0) + (46 if card.art else 0)
    image = Image.new('RGB', (width, height), '#101827')
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((16, 16, width - 16, height - 16), radius=24, outline='#293751', width=2)
    draw.text((42, 38), card.title, font=font(30), fill='#86aaff')
    draw.text((42, 84), card.subtitle[:48], font=font(19), fill='#a7b7cf')
    for i, (key, value) in enumerate(card.rows):
        y = 136 + i * 58
        # Bound labels to their column by measured width, including wide Unicode.
        key = label(key)
        while key and draw.textlength(key, font=font(23)) > 325:
            key = key[:-1]
        draw.text((42, y), key, font=font(23), fill='#bdc9dc')
        value_font = font(23)
        for size in range(23, 12, -1):
            value_font = font(size)
            if draw.textlength(value, font=value_font) <= 440:
                break
        # Names/titles have their own bounded values; shrink rather than cut.
        draw.text((width - 42, y), value, font=value_font, fill='#f1f5fc', anchor='ra')
    if card.progress is not None:
        y = 145 + len(card.rows) * 58
        draw.rounded_rectangle((42, y, width - 42, y + 10), radius=5, fill='#293751')
        p = max(0, min(100, card.progress))
        if p:
            draw.rounded_rectangle((42, y, 42 + (width - 84) * p / 100, y + 10), radius=5, fill='#86aaff')
        draw.text((42, y + 20), f'Прогресс уровня: {p}%', font=font(18), fill='#a7b7cf')
    if card.art:
        draw.text((42, height - 94), card.art, font=font(20), fill='#86aaff')
    draw.text((42, height - 49), 'SENSEI  /  Снимок · обновите кнопкой под карточкой', font=font(17), fill='#8394b0')
    output = BytesIO()
    image.save(output, format='PNG')
    return output.getvalue()
