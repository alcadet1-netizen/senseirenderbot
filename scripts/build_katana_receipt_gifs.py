"""Bake ready-made /upkatana receipt GIFs for every model and outcome.

Run from the repository root:

    python scripts/build_katana_receipt_gifs.py            # write 15 models x 2 outcomes
    python scripts/build_katana_receipt_gifs.py --check    # fail if bundled files are stale

The presenter only reads the bundled files, so a chat notification is a file
send instead of a live 40-frame render.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.widgets.katana import (  # noqa: E402
    baked_labels,
    baked_receipt,
    baked_summary,
    encode_upgrade_gif,
)
from src.widgets.katana_models import MODEL_NAMES, model_receipt_path  # noqa: E402


def payloads():
    for index, _name in enumerate(MODEL_NAMES):
        for success in (True, False):
            receipt = baked_receipt(index, success)
            yield index, success, encode_upgrade_gif(
                receipt,
                labels=baked_labels(index, success),
                summary=baked_summary(index),
            )


def build(check: bool = False) -> int:
    stale = []
    for index, success, payload in payloads():
        path = model_receipt_path(index, success)
        if check:
            if not path.is_file() or path.read_bytes() != payload:
                stale.append(path)
                print(f"stale {path}")
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        print(f"{path} {len(payload)} bytes")
    if stale:
        print(f"{len(stale)} receipt GIF(s) out of date; rerun without --check")
        return 1
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bake bundled katana receipt GIFs")
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the bundled GIFs match the renderer instead of writing them",
    )
    sys.exit(build(parser.parse_args().check))
