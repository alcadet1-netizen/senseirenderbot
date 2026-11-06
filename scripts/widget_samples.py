"""Generate demo data only; never export real users or secrets into the repo."""
import argparse
from dataclasses import replace
from pathlib import Path

from src.widgets.animation import to_gif
from src.widgets.katana import KatanaUpgrade, to_upgrade_gif, to_upgrade_html, to_upgrade_png
from src.widgets.cards import profile_card, top_card, to_html, to_png


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='.cache/widget-samples')
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    cards = {
        'profile': profile_card(dict(username='Ученик Сенсея', level=7, xp=5300,
                                     xp_next=5500, coins=12540, tickets=3,
                                     messages=640, streak=7, has_katana=True, katana_length=28.5,
                                     achievements_count=12, wins=19, losses=4, role='Ронин',
                                     level_name='Жертва Рагпулла')),
        'top': top_card([dict(username=name, xp=xp) for name, xp in
                         [('Ронин', 28450), ('Самурай', 21320), ('Ученик', 12500)]]),
    }
    for name, card in cards.items():
        (output / f'{name}.html').write_text(to_html(card), encoding='utf-8')
        (output / f'{name}.png').write_bytes(to_png(card))
        (output / f'{name}.gif').write_bytes(to_gif(card))
        (output / f'{name}-light.png').write_bytes(to_png(replace(card, theme='light')))
        print(output / f'{name}.html')
    for name, receipt in {
        'katana-success': KatanaUpgrade('Ученик Сенсея', 20.4, 20.76, 100, True),
        'katana-failure': KatanaUpgrade('Ученик Сенсея', 20.4, 20.22, 100, False),
    }.items():
        (output / f'{name}.html').write_text(to_upgrade_html(receipt), encoding='utf-8')
        (output / f'{name}.png').write_bytes(to_upgrade_png(receipt))
        (output / f'{name}.gif').write_bytes(to_upgrade_gif(receipt))
        print(output / f'{name}.html')


if __name__ == '__main__':
    main()
