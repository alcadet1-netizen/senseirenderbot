from io import BytesIO
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

from PIL import Image
import pytest

from src.widgets.katana_models import MODEL_NAMES, model_index, model_path, render_model_png
from src.widgets.forge import katana_art
from src.bot.handlers.user_commands import cmd_mykatana


@pytest.mark.parametrize('index', range(15))
def test_all_model_boundaries_and_assets(index):
    assert model_index(index*20) == index
    assert model_index(index*20+19.99) == index
    if index:
        assert model_index(index*20-0.01) == index-1
    assert model_path(index).is_file()
    with Image.open(BytesIO(render_model_png(index*20))) as image:
        assert image.size == (840, 152)
        assert image.convert('RGB').tobytes() == katana_art(index).tobytes()


def test_clamps_and_invalid_values():
    assert model_index(-1) == 0
    assert model_index(100000) == 14
    assert len(set(MODEL_NAMES)) == 15
    for value in (float('nan'), float('inf')):
        with pytest.raises(ValueError):
            model_index(value)


@pytest.mark.asyncio
@pytest.mark.parametrize('has_katana', [True, False])
async def test_my_katana_is_read_only_and_displays_profile_model(has_katana):
    message = NS(from_user=NS(id=7, username='User', full_name='User'), answer=AsyncMock())
    container = NS(user_service=NS(get_profile=AsyncMock(return_value={
        'has_katana': has_katana, 'katana_length': 245.5})))
    with patch('src.bot.handlers.user_commands.send_current_katana', new_callable=AsyncMock) as send:
        await cmd_mykatana(message, container)
    if has_katana:
        send.assert_awaited_once_with(message, 245.5)
        message.answer.assert_not_awaited()
    else:
        send.assert_not_awaited()
        message.answer.assert_awaited_once()


@pytest.mark.parametrize('index', range(15))
@pytest.mark.parametrize('success', [True, False])
def test_all_models_keep_labels_stable_during_forge(index, success):
    from src.widgets.katana import KatanaUpgrade, render_upgrade
    length = index*20+5
    receipt = KatanaUpgrade('Самурай', length, length+(0.3 if success else -0.3), 100, success)
    final = render_upgrade(receipt)
    for phase in (0, 0.22, 0.46, 0.7, 0.85, 0.95):
        frame = render_upgrade(receipt, phase)
        for region in ((0, 0, 760, 90), (0, 201, 760, 320)):
            assert frame.crop(region).tobytes() == final.crop(region).tobytes()


def test_length_motion_is_monotonic_with_soft_start_and_stop():
    from src.widgets.katana import KatanaUpgrade
    from src.widgets.forge import blade_length
    for delta in (0.3, -0.3, 0):
        receipt = KatanaUpgrade('Name', 25, 25+delta, 100, delta>0)
        values = [blade_length(receipt, i/100) for i in range(101)]
        assert all(360 <= v <= 490 for v in values)
        if delta:
            direction = 1 if delta>0 else -1
            assert all((b-a)*direction >= 0 for a,b in zip(values,values[1:]))
            assert abs(values[31]-values[30]) < abs(values[54]-values[53])
            assert abs(values[78]-values[77]) < abs(values[54]-values[53])
        else:
            assert len(set(values)) == 1


@pytest.mark.parametrize('before,after', [(19.9,20.1),(20.1,19.9),(279.9,280.1)])
def test_model_transition_starts_old_and_finishes_new(before, after):
    from src.widgets.forge import model_mix
    old, new, start = model_mix(before, after, 0)
    assert old == model_index(before) and new == model_index(after)
    assert start == 0
    assert model_mix(before, after, 1)[2] == 1
    assert 0 < model_mix(before, after, .64)[2] < 1


@pytest.mark.asyncio
async def test_current_model_sends_local_asset_without_render_queue():
    from src.bot.presenters.katana_presenter import send_current_katana
    from aiogram.types import FSInputFile
    message = NS(answer_animation=AsyncMock(), answer_photo=AsyncMock(), answer=AsyncMock())
    with patch('src.bot.presenters.katana_presenter.render_receipt', new_callable=AsyncMock) as render:
        await send_current_katana(message, 245.5)
    render.assert_not_awaited()
    file = message.answer_animation.call_args.args[0]
    assert isinstance(file, FSInputFile)
    from src.widgets.katana_models import model_animation_path
    assert file.path == model_animation_path(12)
    caption = message.answer_animation.call_args.kwargs['caption']
    assert '14.50 см' in caption and '240 ≤ длина < 260' in caption
    message.answer.assert_not_awaited()


def test_weapon_layers_have_transparent_surroundings():
    from src.widgets.forge import katana_layers
    for index in range(15):
        handle, blade = katana_layers(index)
        assert handle.getpixel((0,0))[3] == 0
        assert blade.getpixel((0,0))[3] == 0
        assert blade.getchannel('A').getextrema() == (0,255)


@pytest.mark.parametrize('index', range(15))
def test_chat_preview_has_safe_ratio_and_entire_model(index):
    from src.widgets.katana_models import model_preview_path
    with Image.open(model_preview_path(index)) as preview, Image.open(model_path(index)) as source:
        assert preview.size == (960, 640)
        assert preview.crop((60,244,900,396)).convert('RGB').tobytes() == source.convert('RGB').tobytes()
        assert preview.width / preview.height == 1.5
        assert model_preview_path(index).stat().st_size < 5*1024*1024


@pytest.mark.parametrize('index', range(15))
def test_showcase_gif_keeps_entire_card_and_labels(index):
    from src.widgets.katana_models import model_animation_path
    path = model_animation_path(index)
    assert path.stat().st_size < 5*1024*1024
    with Image.open(path) as gif:
        assert gif.size == (960,640) and gif.n_frames == 24
        first = gif.convert('RGB')
        gif.seek(12)
        other = gif.convert('RGB')
        assert first.crop((0,0,960,180)).tobytes() == other.crop((0,0,960,180)).tobytes()
        assert first.crop((0,480,960,640)).tobytes() == other.crop((0,480,960,640)).tobytes()
        assert first.tobytes() != other.tobytes()
        assert gif.info['duration'] == 100


@pytest.mark.asyncio
async def test_showcase_definitive_rejection_falls_back_to_one_static_card():
    from aiogram.exceptions import TelegramBadRequest
    from src.bot.presenters.katana_presenter import send_current_katana
    message = NS(answer_animation=AsyncMock(side_effect=TelegramBadRequest(method='sendAnimation',message='rejected')),
                 answer_photo=AsyncMock(),answer=AsyncMock())
    await send_current_katana(message, 25)
    message.answer_animation.assert_awaited_once()
    message.answer_photo.assert_awaited_once()
    message.answer.assert_not_awaited()


@pytest.mark.asyncio
async def test_showcase_ambiguous_network_failure_is_not_retried():
    from aiogram.exceptions import TelegramNetworkError
    from src.bot.presenters.katana_presenter import send_current_katana
    message = NS(answer_animation=AsyncMock(side_effect=TelegramNetworkError(method='sendAnimation',message='timeout')),
                 answer_photo=AsyncMock(),answer=AsyncMock())
    with pytest.raises(TelegramNetworkError):
        await send_current_katana(message, 25)
    message.answer_photo.assert_not_awaited()
    message.answer.assert_not_awaited()
