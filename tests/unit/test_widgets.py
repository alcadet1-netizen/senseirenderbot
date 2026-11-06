"""No Telegram network or MongoDB required. Run with a dummy BOT_TOKEN."""
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
import zlib

from PIL import Image
import pytest

from src.widgets.cards import Card, label, number, profile_card, top_card, to_html, to_png, validate_html
from src.bot.handlers.widgets import (
    WidgetAction, cmd_widget, export_html, keyboard, load_card, show_card, widget_callback,
)


@pytest.mark.parametrize('value', [None, 'bad', float('nan'), float('inf'), -3])
def test_invalid_numbers(value):
    assert number(value) == 0


def test_profile_bounds_and_escaping():
    card = profile_card(dict(username='<script>alert(1)</script>', level=1, xp=999999, xp_next=300))
    source = to_html(card)
    assert '&lt;script&gt;' in source
    assert source.count('<script>') == 1  # Only our fixed script.
    assert card.progress == 100
    assert 'fetch(' not in source and 'http' not in source


def test_progress_is_relative_to_level():
    from src.core.constants import LEVEL_XP_REQUIREMENTS
    start, end = LEVEL_XP_REQUIREMENTS[1], LEVEL_XP_REQUIREMENTS[2]
    assert profile_card(dict(level=1, xp=start, xp_next=end)).progress == 0
    assert profile_card(dict(level=1, xp=(start + end) / 2, xp_next=end)).progress == 50


def test_profile_name_fallback():
    assert profile_card({'first_name': 'Ученик'}).subtitle == 'Ученик'


def test_labels_are_bounded_utf8():
    assert len(label('я' * 100)) == 48
    assert label('a\x00\n\ud800b').encode('utf-8') == b'ab'


def test_leaderboard_is_bounded():
    assert len(top_card([{'username': 'я' * 1000, 'xp': 2}] * 100).rows) == 10
    assert top_card([]).rows


@pytest.mark.parametrize('card', [profile_card({}), top_card([]), top_card([{'username': '<>&' * 1000, 'xp': 1e99}] * 10)])
def test_payload_limits_and_png(card):
    raw = to_html(card).encode('utf-8')
    assert len(raw) <= 32768
    assert len(zlib.compress(raw, 9)) <= 4096
    image = Image.open(BytesIO(to_png(card)))
    assert image.format == 'PNG' and image.width == 880


@pytest.mark.parametrize('source', ['a\x00b', 'я' * 17000])
def test_invalid_source_rejected(source):
    with pytest.raises(ValueError):
        validate_html(source)


def test_compressed_limit():
    import random
    rng = random.Random(42)
    source = ''.join(chr(rng.randrange(33, 127)) for _ in range(10000))
    with pytest.raises(ValueError):
        validate_html(source)


def test_callback_roundtrip():
    markup = keyboard(123456789012, 'profile')
    for row in markup.inline_keyboard:
        for button in row:
            assert len(button.callback_data.encode()) <= 64
            assert WidgetAction.unpack(button.callback_data).owner == 123456789012


@pytest.mark.asyncio
async def test_other_user_cannot_refresh():
    query = SimpleNamespace(from_user=SimpleNamespace(id=2), answer=AsyncMock())
    with patch('src.bot.handlers.widgets.load_card', new_callable=AsyncMock) as load:
        await widget_callback(query, WidgetAction(owner=1, view='profile'), SimpleNamespace(settings=SimpleNamespace(widgets_enabled=True, widget_animations_enabled=True)))
        load.assert_not_awaited()
        assert query.answer.call_args.kwargs['show_alert']


@pytest.mark.asyncio
async def test_disabled_interface():
    message = SimpleNamespace(answer=AsyncMock())
    container = SimpleNamespace(settings=SimpleNamespace(widgets_enabled=False))
    await cmd_widget(message, container)
    message.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_png_failure_returns_safe_text():
    message = SimpleNamespace(answer=AsyncMock())
    with patch('src.bot.handlers.widgets.to_png', side_effect=OSError('missing font')):
        await show_card(message, Card('Title', '<script>', ()), 1, 'profile')
    assert message.answer.call_args.kwargs['parse_mode'] is None


@pytest.mark.asyncio
async def test_private_admin_export_only():
    message = SimpleNamespace(from_user=SimpleNamespace(id=1), chat=SimpleNamespace(type='supergroup'), answer=AsyncMock())
    await export_html(message, SimpleNamespace(settings=SimpleNamespace(admin_ids=[1])))
    message.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_top_uses_service_not_client_data():
    service = SimpleNamespace(get_top_by_xp=AsyncMock(return_value=[{'username': 'A', 'xp': 5}]))
    card = await load_card(SimpleNamespace(user_service=service), SimpleNamespace(id=1), 'top')
    service.get_top_by_xp.assert_awaited_once_with(10)
    assert card.rows == (('1. A', '5 XP'),)


@pytest.mark.asyncio
async def test_new_card_sends_photo_with_buttons():
    message = SimpleNamespace(answer_photo=AsyncMock())
    await show_card(message, profile_card({}), 7, 'profile')
    kwargs = message.answer_photo.call_args.kwargs
    assert kwargs['reply_markup'].inline_keyboard
    assert kwargs['parse_mode'] is None


@pytest.mark.asyncio
async def test_refresh_edits_existing_photo():
    message = SimpleNamespace(photo=[object()], edit_media=AsyncMock())
    await show_card(message, top_card([]), 7, 'top', edit=True)
    assert message.edit_media.call_args.args[0].type == 'photo'


@pytest.mark.asyncio
async def test_open_from_text_profile_sends_separate_image():
    from unittest.mock import MagicMock
    from aiogram.types import Message
    message = MagicMock(spec=Message)
    query = SimpleNamespace(from_user=SimpleNamespace(id=7), message=message, answer=AsyncMock())
    container = SimpleNamespace(settings=SimpleNamespace(widgets_enabled=True, widget_animations_enabled=True))
    with patch('src.bot.handlers.widgets.load_card', new_callable=AsyncMock, return_value=profile_card({})), \
         patch('src.bot.handlers.widgets.show_card', new_callable=AsyncMock) as show:
        await widget_callback(query, WidgetAction(owner=7, view='open'), container)
    query.answer.assert_awaited_once()
    assert show.call_args.kwargs['edit'] is False
    assert show.call_args.args[3] == 'profile'


def test_profile_menu_has_widget_entry():
    from src.bot.keyboards.inline import get_profile_keyboard
    entries = [b.callback_data for row in get_profile_keyboard(7).inline_keyboard for b in row]
    assert 'sw:7:open' in entries


@pytest.mark.asyncio
async def test_render_error_does_not_consume_financial_actions():
    # The module exposes views only; malicious view names never reach a service.
    query = SimpleNamespace(from_user=SimpleNamespace(id=7), answer=AsyncMock())
    container = SimpleNamespace(settings=SimpleNamespace(widgets_enabled=True, widget_animations_enabled=True))
    with patch('src.bot.handlers.widgets.load_card', new_callable=AsyncMock) as load:
        await widget_callback(query, WidgetAction(owner=7, view='daily'), container)
    load.assert_not_awaited()
    assert query.answer.call_args.kwargs['show_alert'] is True


def test_full_profile_fields_match_mysensei_data():
    from src.core.visuals import Visuals
    data = dict(username='Ronin', level=7, level_name='Жертва Рагпулла', role='Ронин',
                xp=5000, xp_next=5500, coins=1234.56, tickets=3, messages=444,
                streak=5, achievements_count=12, wins=19, losses=4,
                has_katana=True, katana_length=28.5)
    card = profile_card(data)
    rows = dict(card.rows)
    assert rows['Звание'] == data['level_name']
    assert rows['Роль'] == data['role']
    assert rows['Опыт'] == '5,000 / 5,500 XP'
    assert rows['До следующего'] == '500 XP'
    assert rows['Монеты'] == '1,234.56'
    assert rows['Оценка баланса'] == '≈ 0.25 USDT'
    assert rows['Достижения'] == '12'
    assert rows['Победы / поражения'] == '19 / 4'
    assert rows['Клинок'] == Visuals.get_katana_art(28.5)[0]
    assert card.art == Visuals.get_katana_art_ascii(28.5)
    html = to_html(card)
    from src.bot.handlers.widgets import text_fallback
    for key, value in card.rows:
        assert key in html and value in html
        assert f'{key}: {value}' in text_fallback(card)


def test_no_katana_does_not_show_stale_length_or_art():
    card = profile_card(dict(has_katana=False, katana_length=99))
    rows = dict(card.rows)
    assert rows['Катана'] == 'Нет катаны'
    assert 'Клинок' not in rows and 'Ранг клинка' not in rows
    assert card.art == ''


def test_max_level_has_no_fake_next_target():
    card = profile_card(dict(level=20, xp=500000, xp_next=200000))
    assert card.progress == 100
    assert dict(card.rows)['До следующего'] == 'Максимальный уровень'
    assert 'MAX' in dict(card.rows)['Опыт']


def test_gif_has_multiple_readable_bounded_frames():
    from src.widgets.animation import to_gif
    card = profile_card(dict(level=1, xp=600, xp_next=900, has_katana=True))
    result = to_gif(card)
    with Image.open(BytesIO(result)) as image:
        assert image.format == 'GIF'
        assert image.width == 660
        assert image.n_frames == 12
        assert image.info['loop'] == 0
        image.seek(0)
        first = image.convert('RGB')
        image.seek(6)
        middle = image.convert('RGB')
        # Only highlights change: statistics below the animated accent stay readable.
        from src.widgets.rendering import render_image
        _, geometry = render_image(card)
        y = round((geometry.accent[3] + 30) * .75)
        assert first.crop((0, y, 660, y + 60)).tobytes() == middle.crop((0, y, 660, y + 60)).tobytes()
        assert first.tobytes() != middle.tobytes()
    assert len(result) < 5 * 1024 * 1024
    assert to_gif(card) is result  # Same snapshot does not rerender on refresh.


@pytest.mark.asyncio
async def test_new_animated_card_sends_animation_with_buttons():
    message = SimpleNamespace(answer_animation=AsyncMock())
    with patch('src.bot.handlers.widgets.to_gif', return_value=b'GIF89a'):
        await show_card(message, profile_card({}), 7, 'profile', animate=True)
    message.answer_animation.assert_awaited_once()
    assert message.answer_animation.call_args.args[0].filename.endswith('.gif')


@pytest.mark.asyncio
async def test_animated_refresh_uses_edit_media_not_edit_text():
    message = SimpleNamespace(photo=None, animation=object(), edit_media=AsyncMock())
    with patch('src.bot.handlers.widgets.to_gif', return_value=b'GIF89a'):
        await show_card(message, top_card([]), 7, 'top', edit=True, animate=True)
    assert message.edit_media.call_args.args[0].type == 'animation'


@pytest.mark.asyncio
async def test_old_png_can_upgrade_to_animation():
    message = SimpleNamespace(photo=[object()], animation=None, edit_media=AsyncMock())
    with patch('src.bot.handlers.widgets.to_gif', return_value=b'GIF89a'):
        await show_card(message, profile_card({}), 7, 'profile', edit=True, animate=True)
    assert message.edit_media.call_args.args[0].type == 'animation'


@pytest.mark.asyncio
async def test_gif_render_failure_falls_back_to_png():
    message = SimpleNamespace(answer_photo=AsyncMock())
    with patch('src.bot.handlers.widgets.to_gif', side_effect=ValueError('GIF budget')):
        await show_card(message, profile_card({}), 7, 'profile', animate=True)
    message.answer_photo.assert_awaited_once()


@pytest.mark.asyncio
async def test_animation_refused_by_telegram_falls_back_to_png():
    from aiogram.exceptions import TelegramBadRequest
    from aiogram.methods import SendAnimation
    error = TelegramBadRequest(method=SendAnimation(chat_id=1, animation='test'), message='animation forbidden')
    message = SimpleNamespace(answer_animation=AsyncMock(side_effect=error), answer_photo=AsyncMock())
    with patch('src.bot.handlers.widgets.to_gif', return_value=b'GIF89a'):
        await show_card(message, profile_card({}), 7, 'profile', animate=True)
    message.answer_photo.assert_awaited_once()


@pytest.mark.asyncio
async def test_text_refresh_does_not_render_animation():
    message = SimpleNamespace(photo=None, animation=None, edit_text=AsyncMock())
    with patch('src.bot.handlers.widgets.to_gif') as render:
        await show_card(message, profile_card({}), 7, 'profile', edit=True, animate=True)
    render.assert_not_called()
    message.edit_text.assert_awaited_once()


@pytest.mark.parametrize('view,expected', [
    ('profile', ('profile', 'dark', True)),
    ('open', ('profile', 'dark', True)),
    ('top.l.s', ('top', 'light', False)),
    ('profile.d.a', ('profile', 'dark', True)),
])
def test_view_preferences_and_legacy_callbacks(view, expected):
    from src.bot.handlers.widgets import decode_view
    assert decode_view(view) == expected


@pytest.mark.parametrize('value', ['daily.l.a', 'profile.red.a', 'top.d.pay', 'profile.l', 'top.l.a.extra'])
def test_unknown_preferences_are_rejected(value):
    from src.bot.handlers.widgets import decode_view
    with pytest.raises(ValueError):
        decode_view(value)


def test_navigation_preserves_palette_and_motion():
    from src.bot.handlers.widgets import decode_view
    markup = keyboard(7, 'profile', theme='light', animate=False)
    navigation, controls, refresh = markup.inline_keyboard
    for button in navigation + refresh:
        view = WidgetAction.unpack(button.callback_data).view
        _, theme, motion = decode_view(view)
        assert theme == 'light' and motion is False
    assert decode_view(WidgetAction.unpack(controls[0].callback_data).view) == ('profile', 'dark', False)
    assert decode_view(WidgetAction.unpack(controls[1].callback_data).view) == ('profile', 'light', True)
    assert len(keyboard(7, 'top', allow_animation=False).inline_keyboard[1]) == 1


def test_light_and_dark_palettes_really_change_pixels():
    from dataclasses import replace
    card = profile_card({})
    dark = Image.open(BytesIO(to_png(card)))
    light = Image.open(BytesIO(to_png(replace(card, theme='light'))))
    assert dark.getpixel((0, 0)) != light.getpixel((0, 0))
    assert dark.size == light.size
    with pytest.raises(ValueError):
        replace(card, theme='unknown')


def test_measured_wrap_preserves_long_values():
    from PIL import ImageDraw
    from src.widgets.rendering import font, wrap, render_image
    draw = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    value = 'Ш' * 48
    lines = wrap(draw, value, 24, 352)
    assert ''.join(lines) == value
    assert all(draw.textlength(line, font=font(24)) <= 352 for line in lines)
    long = Card('Profile', value, (('Роль', value),), progress=30)
    image, geometry = render_image(long)
    assert geometry.progress[1] < image.height - 80


def test_html_accessibility_and_host_tokens():
    source = to_html(profile_card({}))
    assert 'prefers-reduced-motion:reduce' in source
    assert '--tg-text-font-size' in source
    assert 'env(safe-area-inset-bottom)' in source
    assert '--tg-content-safe-area-corner-right' in source


def test_missing_next_threshold_does_not_show_full_progress():
    card = profile_card(dict(level=0, xp=0))
    assert card.progress == 0
    assert dict(card.rows)['До следующего'] == '300 XP'


def callback_fixture():
    from unittest.mock import MagicMock
    from aiogram.types import Message
    message = MagicMock(spec=Message)
    message.chat = SimpleNamespace(id=123)
    message.message_id = 456
    message.answer = AsyncMock()
    query = SimpleNamespace(from_user=SimpleNamespace(id=7), message=message, answer=AsyncMock())
    container = SimpleNamespace(settings=SimpleNamespace(widgets_enabled=True, widget_animations_enabled=True))
    return query, container


@pytest.mark.asyncio
async def test_callback_applies_preferences():
    query, container = callback_fixture()
    with patch('src.bot.handlers.widgets.load_card', new_callable=AsyncMock, return_value=profile_card({})), \
         patch('src.bot.handlers.widgets.show_card', new_callable=AsyncMock) as show:
        await widget_callback(query, WidgetAction(owner=7, view='profile.l.s'), container)
    assert show.call_args.args[1].theme == 'light'
    assert show.call_args.kwargs['animate'] is False


@pytest.mark.asyncio
async def test_parallel_refresh_is_rejected_and_guard_released():
    import asyncio
    from src.bot.handlers.widgets import _inflight
    query, container = callback_fixture()
    started, release = asyncio.Event(), asyncio.Event()
    async def load(*args):
        started.set()
        await release.wait()
        return profile_card({})
    with patch('src.bot.handlers.widgets.load_card', side_effect=load) as service, \
         patch('src.bot.handlers.widgets.show_card', new_callable=AsyncMock):
        first = asyncio.create_task(widget_callback(query, WidgetAction(owner=7, view='profile'), container))
        await started.wait()
        await widget_callback(query, WidgetAction(owner=7, view='top'), container)
        assert service.call_count == 1
        release.set()
        await first
    assert not _inflight
    assert 'уже обновляется' in query.answer.call_args.args[0]


@pytest.mark.asyncio
async def test_cancelled_refresh_releases_guard():
    import asyncio
    from src.bot.handlers.widgets import _inflight
    query, container = callback_fixture()
    with patch('src.bot.handlers.widgets.load_card', side_effect=asyncio.CancelledError):
        with pytest.raises(asyncio.CancelledError):
            await widget_callback(query, WidgetAction(owner=7, view='profile'), container)
    assert not _inflight


def test_palette_text_contrast_is_readable():
    from src.widgets.rendering import PALETTES
    def luminance(hex_color):
        channels = [int(hex_color[i:i+2], 16) / 255 for i in (1, 3, 5)]
        linear = [c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4 for c in channels]
        return sum(c * weight for c, weight in zip(linear, (.2126, .7152, .0722)))
    for colors in PALETTES.values():
        for foreground, background in [('text', 'tile'), ('muted', 'tile'), ('muted', 'panel'), ('accent', 'panel')]:
            a, b = sorted([luminance(colors[foreground]), luminance(colors[background])])
            assert (b + .05) / (a + .05) >= 4.5
