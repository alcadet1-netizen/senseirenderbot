"""Katana receipts: real outcomes, readable animation, safe post-payment fallback."""

from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from PIL import Image
import pytest

from src.widgets.katana import (
    KatanaUpgrade,
    render_upgrade,
    to_upgrade_gif,
    to_upgrade_html,
    to_upgrade_png,
)
from src.bot.presenters.katana_presenter import send_katana_upgrade
from src.bot.handlers.user_commands import cmd_upkatana
from src.core.exceptions import CooldownError, NoKatanaError, InsufficientFundsError


def result(success=True, before=20.4, after=20.76):
    return dict(
        is_upgraded=success,
        old_length=before,
        new_length=after,
        growth=abs(after - before),
        cost=100,
    )


@pytest.mark.parametrize(
    "success,before,after,delta",
    [
        (True, 20.4, 20.76, 0.36),
        (False, 20.4, 20.22, -0.18),
        (False, 0.05, 0, -0.05),
        (False, 0, 0, 0),
    ],
)
def test_actual_delta_and_zero_floor(success, before, after, delta):
    data = result(success, before, after)
    data["growth"] = 0.2 if not success else 0.36
    receipt = KatanaUpgrade.from_result("Name", data)
    assert receipt.delta == delta
    assert receipt.before == before
    assert dict(receipt.as_card().rows)["Изменение"] == f"{delta:+.2f} см"


def test_legacy_result_compatibility():
    data = result()
    del data["old_length"]
    assert KatanaUpgrade.from_result("Name", data).before == pytest.approx(20.4)


@pytest.mark.parametrize("success,before,after", [(True, 20.4, 20.76), (False, 20.4, 20.22)])
def test_gif_moves_blade_not_numeric_result(success, before, after):
    receipt = KatanaUpgrade("Name", before, after, 100, success)
    payload = to_upgrade_gif(receipt)
    assert len(payload) < 5 * 1024 * 1024
    with Image.open(BytesIO(payload)) as gif:
        assert gif.format == "GIF" and gif.n_frames > 1
        assert gif.size == (760, 320)
        gif.seek(0)
        first = gif.convert("RGB")
        gif.seek(gif.n_frames - 1)
        last = gif.convert("RGB")
        assert first.crop((0, 201, 760, 320)).tobytes() == last.crop((0, 201, 760, 320)).tobytes()

        # Count bright blade pixels along its centre; grows on success, shrinks on failure.
        def blade_pixels(image):
            return sum(
                min(image.getpixel((x, y))) > 180 for x in range(188, 720) for y in range(120, 166)
            )

        assert (blade_pixels(last) > blade_pixels(first)) is success


def test_png_and_html_are_bounded_and_escaped():
    receipt = KatanaUpgrade.from_result("<script>oops</script>", result())
    image = Image.open(BytesIO(to_upgrade_png(receipt)))
    assert image.size == (760, 320)
    html = to_upgrade_html(receipt)
    assert "&lt;script&gt;" in html
    assert "prefers-reduced-motion" in html
    assert "animation:forge" in html
    assert "20.76 см" in html


def message():
    return SimpleNamespace(
        from_user=SimpleNamespace(id=7, username="Ronin", full_name="Ronin"),
        delete=AsyncMock(),
        answer_animation=AsyncMock(),
        answer_photo=AsyncMock(),
        answer=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_presenter_sends_animation_and_readable_caption():
    msg = message()
    with patch("src.bot.presenters.katana_presenter.to_upgrade_gif", return_value=b"GIF89a"):
        await send_katana_upgrade(msg, 7, "Name", result(), animate=True)
    args = msg.answer_animation.call_args
    assert args.args[0].filename.endswith(".gif")
    assert "20.40 → 20.76" in args.kwargs["caption"]
    assert args.kwargs["parse_mode"] is None
    assert "reply_markup" not in args.kwargs


@pytest.mark.asyncio
async def test_motion_disabled_does_not_render_gif():
    msg = message()
    with patch("src.bot.presenters.katana_presenter.to_upgrade_gif") as gif:
        await send_katana_upgrade(msg, 7, "Name", result(), animate=False)
    gif.assert_not_called()
    msg.answer_photo.assert_awaited_once()
    assert "reply_markup" not in msg.answer_photo.call_args.kwargs


@pytest.mark.asyncio
async def test_both_renderers_fail_still_delivers_receipt_text():
    msg = message()
    with (
        patch(
            "src.bot.presenters.katana_presenter.to_upgrade_gif", side_effect=OSError("GIF failure")
        ),
        patch(
            "src.bot.presenters.katana_presenter.to_upgrade_png", side_effect=OSError("PNG failure")
        ),
    ):
        await send_katana_upgrade(msg, 7, "Name", result(), animate=True)
    assert "20.76" in msg.answer.call_args.args[0]
    assert msg.answer.call_args.kwargs["parse_mode"] is None
    assert "reply_markup" not in msg.answer.call_args.kwargs


@pytest.mark.asyncio
async def test_telegram_animation_rejection_uses_png():
    from aiogram.exceptions import TelegramBadRequest
    from aiogram.methods import SendAnimation

    msg = message()
    msg.answer_animation.side_effect = TelegramBadRequest(
        method=SendAnimation(chat_id=7, animation="x"),
        message="animation forbidden",
    )
    with patch("src.bot.presenters.katana_presenter.to_upgrade_gif", return_value=b"GIF89a"):
        await send_katana_upgrade(msg, 7, "Name", result(), animate=True)
    msg.answer_photo.assert_awaited_once()
    assert "reply_markup" not in msg.answer_photo.call_args.kwargs


@pytest.mark.asyncio
async def test_command_never_retries_economy_when_rendering_fails():
    msg = message()
    service = SimpleNamespace(upgrade_katana=AsyncMock(return_value=result()))
    container = SimpleNamespace(
        economy_service=service,
        settings=SimpleNamespace(widgets_enabled=True, widget_animations_enabled=True),
    )
    with (
        patch(
            "src.bot.presenters.katana_presenter.to_upgrade_gif",
            side_effect=ValueError("size limit"),
        ),
        patch(
            "src.bot.presenters.katana_presenter.to_upgrade_png",
            side_effect=ValueError("size limit"),
        ),
    ):
        await cmd_upkatana(msg, container)
    service.upgrade_katana.assert_awaited_once_with(7)
    msg.answer.assert_awaited_once()


@pytest.mark.parametrize(
    "error", [CooldownError(60), NoKatanaError(), InsufficientFundsError(100, 5)]
)
@pytest.mark.asyncio
async def test_rejected_attempt_does_not_show_growth(error):
    msg = message()
    container = SimpleNamespace(
        economy_service=SimpleNamespace(upgrade_katana=AsyncMock(side_effect=error))
    )
    with patch(
        "src.bot.handlers.user_commands.send_katana_upgrade", new_callable=AsyncMock
    ) as send:
        await cmd_upkatana(msg, container)
    send.assert_not_awaited()
    msg.answer.assert_awaited_once()
    text = msg.answer.call_args.args[0]
    if isinstance(error, InsufficientFundsError):
        assert "/donate" in text
        assert "SenseiCoin за Stars" in text
        assert "Нужно: 100" in text and "У тебя: 5" in text
        from src.texts.donate_prompts import KATANA_DONATE_PHRASES
        assert any(text.endswith(phrase) for phrase in KATANA_DONATE_PHRASES)
    else:
        assert "/donate" not in text
    container.economy_service.upgrade_katana.assert_awaited_once_with(7)


@pytest.mark.asyncio
async def test_service_returns_original_length_on_clamped_failure():
    from src.services.economy_service import EconomyService

    user = dict(id=7, coins=1000, has_katana=True, katana_length=0.05)
    users = SimpleNamespace(find_one=AsyncMock(), update_one=AsyncMock())
    users.find_one.side_effect = lambda _: user.copy()

    def update(query, changes):
        user.update(changes.get("$set", {}))
        for key, value in changes.get("$inc", {}).items():
            user[key] += value

    users.update_one.side_effect = update
    db = SimpleNamespace(
        users=users,
        bank=MagicMock(),
        tickets=MagicMock(),
        transactions=SimpleNamespace(insert_one=AsyncMock()),
    )
    service = EconomyService(SimpleNamespace(database=db))
    service._deposit_to_bank = AsyncMock()
    with (
        patch("src.services.economy_service.random.random", return_value=1),
        patch("src.services.economy_service.random.uniform", return_value=0.2),
    ):
        data = await service.upgrade_katana(7)
    assert data["old_length"] == 0.05
    assert data["new_length"] == 0
    assert data["growth"] == 0.2
    assert KatanaUpgrade.from_result("Name", data).delta == -0.05
    assert db.transactions.insert_one.await_count == 1


def test_receipt_is_35_percent_shorter_and_html_has_no_buttons():
    receipt = KatanaUpgrade("Name", 20, 20.4, 100, True)
    image = render_upgrade(receipt)
    assert image.height <= 490 * 0.66
    html = to_upgrade_html(receipt)
    assert "<button" not in html
    assert "<svg" in html and "<ellipse" in html


def test_blade_has_curved_spine_and_asymmetric_kissaki():
    from src.widgets.forge import blade_outline

    points = blade_outline(450)
    assert points[24][1] < points[0][1] - 15
    assert points[25][0] > points[24][0]
    assert points[25][1] < points[24][1]
    assert points[-1][1] > points[0][1]


def test_strike_heat_and_polish_do_not_obscure_numbers():
    receipt = KatanaUpgrade("Name", 20.4, 20.76, 100, True)
    still = render_upgrade(receipt, 1)
    for phase in (0.22, 0.25, 0.46, 0.57, 0.8):
        frame = render_upgrade(receipt, phase)
        assert frame.crop((0, 0, 760, 90)).tobytes() == still.crop((0, 0, 760, 90)).tobytes()
        for left in (32, 270, 508):
            area = (left, 207, left + 212, 254)
            assert frame.crop(area).tobytes() == still.crop(area).tobytes()
        assert (
            frame.crop((185, 95, 700, 190)).tobytes() != still.crop((185, 95, 700, 190)).tobytes()
        )


def test_forging_gif_has_enough_frames_and_a_final_hold():
    receipt = KatanaUpgrade("Name", 20.4, 20.76, 100, True)
    with Image.open(BytesIO(to_upgrade_gif(receipt))) as gif:
        assert gif.n_frames >= 20
        gif.seek(gif.n_frames - 1)
        assert gif.info["duration"] >= 1400


@pytest.mark.asyncio
async def test_caption_is_compact_and_notification_has_no_controls():
    msg = message()
    with patch("src.bot.presenters.katana_presenter.to_upgrade_gif", return_value=b"GIF89a"):
        await send_katana_upgrade(msg, 7, "Name", result(), animate=True)
    kwargs = msg.answer_animation.call_args.kwargs
    assert kwargs.get("reply_markup") is None
    assert kwargs["caption"].count("\n") == 1


@pytest.mark.parametrize("index", range(12))
@pytest.mark.asyncio
async def test_each_katana_donate_variant_is_used_in_single_response(index):
    from src.texts.donate_prompts import KATANA_DONATE_PHRASES

    assert len(set(KATANA_DONATE_PHRASES)) >= 10
    phrase = KATANA_DONATE_PHRASES[index]
    assert "/donate" in phrase and "SenseiCoin за Stars" in phrase
    assert len(phrase) < 250 and "<" not in phrase
    msg = message()
    service = SimpleNamespace(upgrade_katana=AsyncMock(side_effect=InsufficientFundsError(100, 5)))
    with patch("src.texts.donate_prompts.random.choice", return_value=phrase) as choose:
        await cmd_upkatana(msg, SimpleNamespace(economy_service=service))
    choose.assert_called_once_with(KATANA_DONATE_PHRASES)
    msg.answer.assert_awaited_once()
    text = msg.answer.call_args.args[0]
    assert text.endswith(phrase)
    assert "Нужно: 100" in text and "У тебя: 5" in text
    service.upgrade_katana.assert_awaited_once_with(7)


@pytest.mark.parametrize('length', [5, 25, 45, 65, 85])
def test_enchanted_styles_are_deterministic_and_keep_receipt_readable(length):
    receipt = KatanaUpgrade('Name', length, length + 0.3, 100, True)
    final = render_upgrade(receipt)
    assert final.tobytes() == render_upgrade(receipt).tobytes()
    for phase in (0.23, 0.47, 0.66, 0.85):
        frame = render_upgrade(receipt, phase)
        assert frame.crop((0, 201, 760, 320)).tobytes() == final.crop((0, 201, 760, 320)).tobytes()
        assert frame.crop((0, 0, 760, 90)).tobytes() == final.crop((0, 0, 760, 90)).tobytes()


def test_five_blade_styles_are_visually_distinct():
    images = [render_upgrade(KatanaUpgrade('Name', n, n + 0.3, 100, True))
              .crop((40, 115, 700, 180)).tobytes() for n in (5, 25, 45, 65, 85)]
    assert len(set(images)) == 5


@pytest.mark.parametrize('school', range(5))
def test_reference_art_is_bundled_and_used_without_mutating_cached_source(school):
    from src.widgets.forge import katana_art
    art = katana_art(school)
    original = art.tobytes()
    length = school * 20 + 5
    frame = render_upgrade(KatanaUpgrade('Name', length, length + 0.3, 100, True))
    assert frame.size == (760, 320)
    assert katana_art(school).tobytes() == original
    assert art.width > 500 and art.height > 100


@pytest.mark.asyncio
async def test_busy_render_queue_returns_text_receipt_without_starting_more_threads():
    import asyncio
    msg = message()
    with (
        patch('src.bot.presenters.katana_presenter.RENDER_SLOTS', asyncio.Semaphore(0)),
        patch('src.bot.presenters.katana_presenter.to_upgrade_gif') as gif,
        patch('src.bot.presenters.katana_presenter.to_upgrade_png') as png,
    ):
        await send_katana_upgrade(msg, 7, 'Name', result(), animate=True)
    gif.assert_not_called()
    png.assert_not_called()
    msg.answer.assert_awaited_once()
    assert '20.40 → 20.76' in msg.answer.call_args.args[0]
    msg.answer_animation.assert_not_awaited()
    msg.answer_photo.assert_not_awaited()


@pytest.mark.asyncio
async def test_profile_upgrade_uses_same_animation_without_repeating_economy():
    from src.bot.handlers.callbacks import cb_do_upgrade_katana
    from src.bot.keyboards.inline import MenuCb
    msg = message()
    query = SimpleNamespace(from_user=msg.from_user, message=msg, answer=AsyncMock())
    service = SimpleNamespace(upgrade_katana=AsyncMock(return_value=result()))
    container = SimpleNamespace(economy_service=service,
        settings=SimpleNamespace(widgets_enabled=True, widget_animations_enabled=True))
    with patch('src.bot.handlers.callbacks.send_katana_upgrade', new_callable=AsyncMock) as send:
        await cb_do_upgrade_katana(query, MenuCb(action='confirm_upgrade_katana', user_id=7), container)
    service.upgrade_katana.assert_awaited_once_with(7)
    send.assert_awaited_once()
    assert send.call_args.kwargs['animate'] is True
