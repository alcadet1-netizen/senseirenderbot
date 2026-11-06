"""Katana receipts: real outcomes, readable animation, safe post-payment fallback."""
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from PIL import Image
import pytest

from src.widgets.katana import KatanaUpgrade, render_upgrade, to_upgrade_gif, to_upgrade_html, to_upgrade_png
from src.bot.presenters.katana_presenter import send_katana_upgrade
from src.bot.handlers.user_commands import cmd_upkatana
from src.core.exceptions import CooldownError, NoKatanaError, InsufficientFundsError


def result(success=True, before=20.4, after=20.76):
    return dict(is_upgraded=success, old_length=before, new_length=after,
                growth=abs(after - before), cost=100)


@pytest.mark.parametrize('success,before,after,delta', [
    (True, 20.4, 20.76, .36), (False, 20.4, 20.22, -.18),
    (False, .05, 0, -.05), (False, 0, 0, 0),
])
def test_actual_delta_and_zero_floor(success, before, after, delta):
    data = result(success, before, after)
    data['growth'] = .2 if not success else .36
    receipt = KatanaUpgrade.from_result('Name', data)
    assert receipt.delta == delta
    assert receipt.before == before
    assert dict(receipt.as_card().rows)['Изменение'] == f'{delta:+.2f} см'


def test_legacy_result_compatibility():
    data = result()
    del data['old_length']
    assert KatanaUpgrade.from_result('Name', data).before == pytest.approx(20.4)


@pytest.mark.parametrize('success,before,after', [(True, 20.4, 20.76), (False, 20.4, 20.22)])
def test_gif_moves_blade_not_numeric_result(success, before, after):
    receipt = KatanaUpgrade('Name', before, after, 100, success)
    payload = to_upgrade_gif(receipt)
    assert len(payload) < 5 * 1024 * 1024
    with Image.open(BytesIO(payload)) as gif:
        assert gif.format == 'GIF' and gif.n_frames > 1
        assert gif.size == (760, 490)
        gif.seek(0)
        first = gif.convert('RGB')
        gif.seek(gif.n_frames - 1)
        last = gif.convert('RGB')
        assert first.crop((0, 280, 760, 490)).tobytes() == last.crop((0, 280, 760, 490)).tobytes()
        # Count bright blade pixels along its centre; grows on success, shrinks on failure.
        def blade_pixels(image):
            return sum(min(image.getpixel((x, 188))) > 180 for x in range(168, 700))
        assert (blade_pixels(last) > blade_pixels(first)) is success


def test_png_and_html_are_bounded_and_escaped():
    receipt = KatanaUpgrade.from_result('<script>oops</script>', result())
    image = Image.open(BytesIO(to_upgrade_png(receipt)))
    assert image.size == (760, 490)
    html = to_upgrade_html(receipt)
    assert '&lt;script&gt;' in html
    assert 'prefers-reduced-motion' in html
    assert 'animation:forge' in html
    assert '20.76 см' in html


def message():
    return SimpleNamespace(
        from_user=SimpleNamespace(id=7, username='Ronin', full_name='Ronin'),
        delete=AsyncMock(), answer_animation=AsyncMock(), answer_photo=AsyncMock(), answer=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_presenter_sends_animation_and_readable_caption():
    msg = message()
    with patch('src.bot.presenters.katana_presenter.to_upgrade_gif', return_value=b'GIF89a'):
        await send_katana_upgrade(msg, 7, 'Name', result(), animate=True)
    args = msg.answer_animation.call_args
    assert args.args[0].filename.endswith('.gif')
    assert '20.40 → 20.76' in args.kwargs['caption']
    assert args.kwargs['parse_mode'] is None
    assert args.kwargs['reply_markup'].inline_keyboard[0][0].callback_data == 'sw:7:open'


@pytest.mark.asyncio
async def test_motion_disabled_does_not_render_gif():
    msg = message()
    with patch('src.bot.presenters.katana_presenter.to_upgrade_gif') as gif:
        await send_katana_upgrade(msg, 7, 'Name', result(), animate=False)
    gif.assert_not_called()
    msg.answer_photo.assert_awaited_once()


@pytest.mark.asyncio
async def test_both_renderers_fail_still_delivers_receipt_text():
    msg = message()
    with patch('src.bot.presenters.katana_presenter.to_upgrade_gif', side_effect=OSError('GIF failure')), \
         patch('src.bot.presenters.katana_presenter.to_upgrade_png', side_effect=OSError('PNG failure')):
        await send_katana_upgrade(msg, 7, 'Name', result(), animate=True)
    assert '20.76' in msg.answer.call_args.args[0]
    assert msg.answer.call_args.kwargs['parse_mode'] is None


@pytest.mark.asyncio
async def test_telegram_animation_rejection_uses_png():
    from aiogram.exceptions import TelegramBadRequest
    from aiogram.methods import SendAnimation
    msg = message()
    msg.answer_animation.side_effect = TelegramBadRequest(
        method=SendAnimation(chat_id=7, animation='x'), message='animation forbidden',
    )
    with patch('src.bot.presenters.katana_presenter.to_upgrade_gif', return_value=b'GIF89a'):
        await send_katana_upgrade(msg, 7, 'Name', result(), animate=True)
    msg.answer_photo.assert_awaited_once()


@pytest.mark.asyncio
async def test_command_never_retries_economy_when_rendering_fails():
    msg = message()
    service = SimpleNamespace(upgrade_katana=AsyncMock(return_value=result()))
    container = SimpleNamespace(economy_service=service,
                                settings=SimpleNamespace(widgets_enabled=True, widget_animations_enabled=True))
    with patch('src.bot.presenters.katana_presenter.to_upgrade_gif', side_effect=ValueError('size limit')), \
         patch('src.bot.presenters.katana_presenter.to_upgrade_png', side_effect=ValueError('size limit')):
        await cmd_upkatana(msg, container)
    service.upgrade_katana.assert_awaited_once_with(7)
    msg.answer.assert_awaited_once()


@pytest.mark.parametrize('error', [CooldownError(60), NoKatanaError(), InsufficientFundsError(100, 5)])
@pytest.mark.asyncio
async def test_rejected_attempt_does_not_show_growth(error):
    msg = message()
    container = SimpleNamespace(economy_service=SimpleNamespace(upgrade_katana=AsyncMock(side_effect=error)))
    with patch('src.bot.handlers.user_commands.send_katana_upgrade', new_callable=AsyncMock) as send:
        await cmd_upkatana(msg, container)
    send.assert_not_awaited()
    msg.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_service_returns_original_length_on_clamped_failure():
    from src.services.economy_service import EconomyService
    user = dict(id=7, coins=1000, has_katana=True, katana_length=.05)
    users = SimpleNamespace(find_one=AsyncMock(), update_one=AsyncMock())
    users.find_one.side_effect = lambda _: user.copy()
    def update(query, changes):
        user.update(changes.get('$set', {}))
        for key, value in changes.get('$inc', {}).items():
            user[key] += value
    users.update_one.side_effect = update
    db = SimpleNamespace(users=users, bank=MagicMock(), tickets=MagicMock(),
                         transactions=SimpleNamespace(insert_one=AsyncMock()))
    service = EconomyService(SimpleNamespace(database=db))
    service._deposit_to_bank = AsyncMock()
    with patch('src.services.economy_service.random.random', return_value=1), \
         patch('src.services.economy_service.random.uniform', return_value=.2):
        data = await service.upgrade_katana(7)
    assert data['old_length'] == .05
    assert data['new_length'] == 0
    assert data['growth'] == .2
    assert KatanaUpgrade.from_result('Name', data).delta == -.05
    assert db.transactions.insert_one.await_count == 1
