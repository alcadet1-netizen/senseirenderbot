"""Build chat-friendly static previews; run from repository root."""
from pathlib import Path
import sys
import math

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image, ImageDraw, ImageChops, ImageFilter
from src.widgets.katana_models import MODEL_NAMES, model_path, model_preview_path, model_animation_path
from src.widgets.rendering import font


COLORS = ('#ddbf8d', '#9de5ff', '#ff9f57', '#81cfff', '#be9bff',
          '#ff9861', '#a5e8ff', '#b39aff', '#d0bcff', '#b0da7d',
          '#ff9655', '#9ae2ff', '#ff759a', '#c38aff', '#ffe0a0')


def animate_card(card, index):
    """Offline deterministic showcase; no length/state animation on viewing."""
    frames = []
    steel = card.convert('L').crop((360,244,900,396)).point(lambda v: min(255,max(0,(v-95)*2)))
    for frame in range(24):
        phase = frame / 24
        image = card.copy()
        d = ImageDraw.Draw(image)
        color = COLORS[index]
        # Stable border geometry with a gently travelling constellation.
        d.rounded_rectangle((36,188,923,452), radius=16, outline=color, width=2)
        for j in range(10):
            x = 70 + ((j*79+phase*140) % 820)
            y = 216 + math.sin(j*2.4+phase*2*math.pi)*11
            r = 1 + (math.sin(j+phase*2*math.pi)+1)/2
            d.line((x-r,y,x+r,y), fill=color, width=1)
            d.line((x,y-r,x,y+r), fill=color, width=1)
        # A clipped, broad highlight follows the bright steel, never the labels.
        sweep = Image.new('L',(540,152))
        sd = ImageDraw.Draw(sweep)
        x = -100 + phase*820
        sd.polygon([(x-35,0),(x,0),(x+70,152),(x+35,152)],fill=95)
        sweep = sweep.filter(ImageFilter.GaussianBlur(8))
        image.paste(Image.new('RGB',(540,152),'#ffffff'),(360,244),ImageChops.multiply(sweep,steel))
        frames.append(image)
    palette = card.quantize(colors=192)
    frames = [f.quantize(palette=palette,dither=Image.Dither.NONE) for f in frames]
    frames[0].save(model_animation_path(index),format='GIF',save_all=True,
                   append_images=frames[1:],duration=100,loop=0,disposal=1,optimize=False)


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
        animate_card(card, index)


if __name__ == '__main__':
    build()
