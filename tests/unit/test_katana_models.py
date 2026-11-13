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
