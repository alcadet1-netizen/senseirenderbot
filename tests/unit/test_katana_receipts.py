"""Bundled /upkatana animations: every model ships a ready GIF, no live render.

Only environment-independent checks belong here: shipped files are decoded, not
byte-compared against a fresh encode, because GIF rasterisation differs between
Pillow/font builds. Bundle freshness is verified with
`scripts/build_katana_receipt_gifs.py --check` in the baking environment.
"""

from io import BytesIO
from unittest.mock import patch

import pytest
from PIL import Image

from src.widgets.katana import (
    KatanaUpgrade,
    baked_labels,
    baked_receipt,
    baked_summary,
    to_upgrade_gif,
)
from src.widgets.katana_models import MODEL_NAMES, model_index, model_receipt_path


@pytest.mark.parametrize("index", range(15))
@pytest.mark.parametrize("success", [True, False])
def test_every_model_outcome_has_a_ready_gif(index, success):
    path = model_receipt_path(index, success)
    assert path.is_file()
    assert path.stat().st_size < 5 * 1024 * 1024
    with Image.open(path) as gif:
        assert gif.format == "GIF" and gif.size == (760, 290)
        assert gif.n_frames >= 20
        first = gif.convert("RGB")
        gif.seek(gif.n_frames - 1)
        assert gif.info["duration"] >= 1400
        last = gif.convert("RGB")
        # Result labels never animate; only the blade moves.
        assert first.crop((0, 201, 760, 290)).tobytes() == last.crop((0, 201, 760, 290)).tobytes()
        assert first.crop((0, 0, 760, 90)).tobytes() == last.crop((0, 0, 760, 90)).tobytes()


def test_receipt_lookup_is_a_file_read_never_a_render():
    receipt = KatanaUpgrade("Ronin", 20.4, 20.76, 100, True)
    with patch(
        "src.widgets.katana.render_upgrade",
        side_effect=AssertionError("bundled GIF must not render"),
    ):
        payload = to_upgrade_gif(receipt)
    assert payload == model_receipt_path(model_index(20.76), True).read_bytes()
    failure = KatanaUpgrade("Ronin", 20.4, 20.22, 100, False)
    assert to_upgrade_gif(failure) == model_receipt_path(1, False).read_bytes()


def test_bundled_lookup_follows_the_final_model_of_the_receipt():
    # A level-up receipt must send the new model's animation.
    receipt = KatanaUpgrade("Ronin", 19.7, 20.1, 100, True)
    assert model_index(receipt.after) == 1
    assert to_upgrade_gif(receipt) == model_receipt_path(1, True).read_bytes()


@pytest.mark.parametrize("index", range(15))
def test_baked_tiles_describe_the_model_not_one_user(index):
    ok = dict(baked_labels(index, True))
    fail = dict(baked_labels(index, False))
    assert ok["УРОВЕНЬ"] == fail["УРОВЕНЬ"] == f"{index + 1}/15"
    assert ok["ИЗМЕНЕНИЕ"] == "▲ рост" and fail["ИЗМЕНЕНИЕ"] == "▼ спад"
    assert ok["ДИАПАЗОН"] == fail["ДИАПАЗОН"]
    assert "см" in ok["ДИАПАЗОН"]
    summary = baked_summary(index)
    assert summary.startswith(MODEL_NAMES[index])
    assert "Попытка:" in summary and "монет" in summary


def test_baked_receipt_keeps_the_real_outcome_direction():
    ok = baked_receipt(4, True)
    fail = baked_receipt(4, False)
    assert ok.success and ok.delta > 0 and model_index(ok.after) == 4
    assert not fail.success and fail.delta < 0 and model_index(fail.after) == 4
    assert ok.name == MODEL_NAMES[4] == fail.name


def test_encoder_contract_stays_bundled_sized():
    # The offline encoder is what --check re-runs; it must stay bounded and
    # structurally valid so a baked file can never exceed Telegram's limit.
    # Compared structurally only: byte equality is not portable across builds.
    from src.widgets.katana import encode_upgrade_gif

    receipt = baked_receipt(0, True)
    payload = encode_upgrade_gif(
        receipt, labels=baked_labels(0, True), summary=baked_summary(0)
    )
    assert len(payload) < 5 * 1024 * 1024
    with Image.open(BytesIO(payload)) as gif:
        assert gif.format == "GIF" and gif.size == (760, 290)
        assert gif.n_frames >= 20
