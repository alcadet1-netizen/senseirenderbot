"""
Boss resources: phrases, intros, etc.
"""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from src.core.constants import BOSSES


# Boss introduction phrases
BOSS_INTROS = [
    "Кто осмеливается потревожить мой сон?",
    "Свежая кровь! Как давно я не ощущал вкуса победы...",
    "Вы пришли сюда, чтобы умереть. Или нет?",
    "Твоя сила ничто перед моей мощью!",
    "Приготовься к боли, слабак!",
    "Сегодня твой день... последнего вздоха!",
    "Я ждал worthy opponent веками!",
    "Твоя судьба решена ещё до первого удара!",
]

# Boss phrases based on HP percentage thresholds
BOSS_PHRASES = {
    75: [  # When HP <= 75%
        "Вы лишь задели меня. Почувствуйте мой гнев!",
        "Это было лишь разминкой. Готовьтесь к настоящей битве!",
        "Вы злите меня. Это будет вашей последней ошибкой!",
        "Щит дрогнул... Но мой дух непокорен!",
        "Вы сделали первый шаг к своей погибели!",
    ],
    50: [  # When HP <= 50%
        "Вы сильнее, чем я ожидал. Но всё равно слабы!",
        "Половина пути пройдена. Но вы ещё далеко от победы!",
        "Я начинаю серьёзничать. А вы?",
        "Шины трещат под напором моей ярости!",
        "Вы не представляете, что такой ярости способен!"
    ],
    25: [  # When HP <= 25%
        "Вы почти победили меня... Но не сегодня!",
        "Последний рык перед вечной темнотой!",
        "Моя сила иссякает, но дух непокорён!",
        "Вы чувствуете это? Я рядом с падением... Но вы не дождётесь!",
        "Последний шанс отступить... Или принять свою судьбу!"
    ],
    10: [  # When HP <= 10%
        "Последний вздох... Но я уношу вас с собой!",
        "Свет гаснет... Я вижу лишь тьму и ваши лица!",
        "Это конец... для вас!",
        "Моя ярость достигает пика перед прахом!",
        "Вы победили тело... Но дух мой вечен!"
    ]
}


def get_boss_list_keyboard() -> InlineKeyboardMarkup:
    """Generate keyboard for boss selection."""
    buttons = []
    row = []
    for boss_id, boss_info in BOSSES.items():
        # Create callback data string matching BossEditorCallback format: boss_edit:set_boss:<boss_id>
        callback_data = f"boss_edit:set_boss:{boss_id}"
        button = InlineKeyboardButton(
            text=boss_info['name'],
            callback_data=callback_data
        )
        row.append(button)

        # Arrange in rows of 2
        if len(row) == 2:
            buttons.append(row)
            row = []

    # Add remaining buttons if any
    if row:
        buttons.append(row)

    # Add back button
    buttons.append([InlineKeyboardButton(
        text="🔙 Назад",
        callback_data="boss_edit:back"
    )])

    return InlineKeyboardMarkup(inline_keyboard=buttons)