"""Generate demo data only; never export real users or secrets into the repo."""
import argparse
from pathlib import Path

from src.widgets.cards import profile_card, top_card, to_html, to_png


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='.cache/widget-samples')
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    cards = {
        'profile': profile_card(dict(username='Ученик Сенсея', level=4, xp=5300,
                                     xp_next=7500, coins=12540, tickets=3,
                                     messages=640, streak=7, katana_length=28.5)),
        'top': top_card([dict(username=name, xp=xp) for name, xp in
                         [('Ронин', 28450), ('Самурай', 21320), ('Ученик', 12500)]]),
    }
    for name, card in cards.items():
        (output / f'{name}.html').write_text(to_html(card), encoding='utf-8')
        (output / f'{name}.png').write_bytes(to_png(card))
        print(output / f'{name}.html')


if __name__ == '__main__':
    main()
