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
        assert first.crop((0, 100, 660, 200)).tobytes() == middle.crop((0, 100, 660, 200)).tobytes()
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
