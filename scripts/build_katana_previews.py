"""Build chat-friendly static previews; run from repository root."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image, ImageDraw
from src.widgets.katana_models import MODEL_NAMES, model_path, model_preview_path
from src.widgets.rendering import font


def build():
    for index, name in enumerate(MODEL_NAMES):
        card = Image.new('RGB', (960, 640), '#0e1621')
        draw = ImageDraw.Draw(card)
        draw.rounded_rectangle((20, 20, 939, 619), radius=24, fill='#17212b', outline='#304354', width=2)
        draw.text((60, 72), 'SENSEI / КОЛЛЕКЦИЯ КАТАН', font=font(20), fill='#a4b6c7')
        draw.text((60, 112), name, font=font(36), fill='#f0f5fa')
        with Image.open(model_path(index)) as art:
            # Preserve every source pixel, with 60 px safe margins on both sides.
            card.paste(art.convert('RGB'), (60, 244))
        draw.text((60, 500), f'МОДЕЛЬ {index+1:02d} / 15', font=font(20), fill='#a4b6c7')
        draw.text((60, 540), 'Длина и прогресс — в подписи к карточке', font=font(20), fill='#a4b6c7')
        path = model_preview_path(index)
        path.parent.mkdir(parents=True, exist_ok=True)
        card.save(path, format='PNG', optimize=True)


if __name__ == '__main__':
    build()
