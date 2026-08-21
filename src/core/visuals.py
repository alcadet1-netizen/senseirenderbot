"""
🎨 Визуальное оформление для Telegram (HTML, mobile-first).
"""

import html
import math
import random
import hashlib
from typing import List, Dict, Any, Tuple, Sequence, Optional


def _clamp_int(n: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, n))


class CompactTheme:
    glows: List[str] = ["◇", "◆", "◈", "⬡", "⟡", "✶"]
    symbol: str = "BTCUSDT"
    exchange: str = "NEON"
    mode: str = "WCS"
    cursor: str = "▌"


class Visuals:
    """Класс для визуала Telegram HTML."""

    STYLE: str = "classic"

    FRAME_W_PROFILE: int = 30
    FRAME_W_LEVELUP: int = 28
    FRAME_W_MENU: int = 30

    TAUNTS = [
        "перехватил корону! 👑",
        "обнулил таймер! ⏳",
        "украл победу! 🦝",
        "сказал 'БАН-ЗАЙ!' 💢",
        "вломился без стука! 🚪",
        "появился из тени! 🌑",
        "появился из тени! 🌑",
        "вышел из темноты! 🌙",
        "ударил как ниндзя! 🥷",
        "атаковал бесшумно! 👤",
        "похитил корону! 👑",
        "стащил первенство! 🏆",
        "отобрал лидерство! 🥇",
        "перехватил инициативу! 🎮",
        "угнал победу! 🚗",
        "своровал момент славы! ✨",
        "забрал себе всё! 💰",
        "присвоил трон! 🪑",
        "конфисковал победу! 📋",
        "экспроприировал корону! 🎪",
        "пошёл против системы! 🔄",
        "сломал все правила! 📜",
        "переписал историю! 📖",
        "изменил ход игры! 🎲",
        "перевернул стол! 🙃",
        "сказал своё слово! 💬",
        "поставил точку! ⚫",
        "закрыл гештальт! 🔮",
        "завершил эпоху молчания! 📅",
        "открыл новую эру! 🌅",
        "вписал себя в историю! 🖊️",
        "стал легендой! 🌟",
        "вошёл в зал славы! 🏛️",
        "достиг просветления! ☀️",
        "познал дзен перехвата! ☯️",
        "увёл приз из-под носа! 👃",
        "выхватил первенство! 🤺",
        "утащил лавры! 🌿",
        "прикарманил выигрыш! 💎",
        "захапал корону! 🤑",
        "слямзил победу! 😏",
        "умыкнул трофей! 🏅",
        "стянул золото! 🥇",
        "хапнул главный приз! 🎁",
        "нанёс удар из ниоткуда! 👻",
        "возник как призрак! 👻",
        "подкрался незаметно! 🐱",
        "скрывался в тенях! 🦇",
        "действовал как тень! 🌚",
        "был невидимкой! 🫥",
        "прятался до последнего! 🙈",
        "выскочил из засады! 🐯",
        "напал исподтишка! 🐍",
        "сработал скрытно! 🕵️",
        "прокрался к победе! 🦊",
        "двигался как кошка! 🐈‍⬛",
        "был тише воды! 💧",
        "разрушил все планы! 😈",
        "устроил переворот! ⚔️",
        "хочет выиграть! 😤",
        "сказал: 'Не сегодня!' 🛑",
        "ворвался в игру! 🚀",
        "сбил серию! 💥"
    ]

    @staticmethod
    def _render_block(lines: List[str]) -> str:
        if Visuals.STYLE == "crypto":
            return "\n".join(lines)
        return "<pre>\n" + "\n".join(lines) + "\n</pre>"

    WISDOM: List[str] = [
        "Путь к вершине начинается с первого шага.",
        "Терпение — это тоже оружие.",
        "Истинная сила — в контроле над собой.",
        "Если путь сложен — значит идёшь по блокчейну.",
        "Настоящий Сенсей не объясняет — он шлёт стикер.",
        "Не поймёшь крипту, пока не потеряешь на ней всё.",
        "Телеграм — не мессенджер, а состояние духа.",
        "Чёрный пояс по трейдингу бывает только у тех, кто обанкротился 3 раза.",
        "Когда душно в жизни — создавай свой канал.",
        "Кто рано шиллит, тот скамит фастом.",
        "Даже вода в крипте — это токенизированная жидкость.",
        "Павел Дуров не носит плащ. Это воздух сам уходит с его пути.",
        "Иногда, единственный путь к просветлению — это /start.",
        "Следуй за тем, кто знает путь. Но проверь его транзакции на BscScan.",
        "Путь к богатству тернист... особенно если ты холдер SHIBA.",
        "Мудрый не спорит — он кидает мем.",
        "Разумный человек не спорит с крипточатом — он мьютит его навсегда.",
        "Хочешь изменить мир? Начни с чата на 3 участника.",
        "Если не можешь победить медвежий рынок — прикинься пухлым бычком.",
        "Даже DAO нуждается в мудром Сенсее... или хотя бы модере.",
        "Ночи в крипте длиннее, чем у обычных смертных.",
        "Кто последним нажмёт 'присоединиться к аирдропу', тот получит рефку.",
        "Не трогай злого трейдера до первой чашки лонга.",
        "Сидящий в Телеге весь день — не бездельник, а стратег.",
        "Лучше один NFT, чем сто фоток в инсте.",
        "Мудрый инвестор не холдит токены. Он холдит терпение.",
        "Кто называет токен скамом — тот сам был скамнут трижды.",
        "Не каждый, кто просвещён, купил на дне.",
        "Быть богатым — не цель. Цель — выйти в плюс хотя бы раз.",
        "Портфель без минусов — иллюзия. Даже у Сенсея фотошоп.",
        "Даже у Дурова зависает Wi-Fi.",
        "Только тот, кто пережил даунтренд, знает, что такое дзен.",
        "Слишком быстро идёшь — попадёшь на скам-проект.",
        "Все дороги ведут в Telegram Premium.",
        "Откроешь канал — станешь сенсеем. Не откроешь — останешься логом.",
        "Хорошая сделка — та, о которой ты не рассказываешь в чате.",
        "Иногда, молчание в чате громче любого пампа.",
        "Умный трейдер не торгует по ночам. Он просто не спит.",
        "Сомневаешься — не лей. Верь в проект хотя бы до следующего рендера.",
        "Каждый потерянный доллар — монета в копилке мудрости.",
        "Никто никогда не продаёт на хаях. Даже Будда держал в минусе.",
        "Даже Луна когда-то падала. Но DOGE ещё летает.",
        "Ты не просёк рынок — рынок просёк тебя.",
        "Своё найти тяжело. Особенно среди 20.000 шиткойнов.",
        "Только слив научит ценить профит.",
        "Мастерство — это когда открываешь график и просто вздыхаешь.",
        "Путь к богатству начинается с MetaMask.",
        "Сделал ошибку — стань аналитиком.",
        "Дуров создал Telegram, но ты создал 13 каналов без смысла.",
        "Успех не всегда памп. Иногда — это индикатор отключить.",
        "Если токен не растёт — может, это ты падаешь?",
        "Настоящий криптоинвестор не теряет. Он переучивается.",
        "Волатильность — это танец рынка. Танцуй красиво или упади с грацией.",
        "Сомнение — тень трейда.",
        "Прыгай в рынок, как ниндзя. Бесшумно и незаметно для ликвидности.",
        "Лучший совет — тот, который ты сам проигнорировал год назад.",
        "Терпение — не добродетель. Это стратегия.",
        "Облако в Гималаях похоже на график SHIBA.",
        "Купи на хаях — стань сенсеем любви к убыткам.",
        "Чем больше крипты в жизни — тем меньше реальной еды.",
        "Даже твой кот знает, что этот токен был скамом.",
        "Тот, кто троллит в чате, не нашёл себе DAO.",
        "Телега — храм, где каждый может создать культ и верить в него.",
        "Если спросил в чате, стоит ли покупать — ты уже проиграл.",
        "Даже Дуров не знает, как работает его алгоритм.",
        "Истинный hodler живёт между Pump и Dump.",
        "Гуру не спит. Он ждёт сигнал.",
        "Каждому своему сливу — по чашке смирения.",
        "Кто встал в 6 утра ради крипты, тот опоздал на 2 часа.",
        "Мемы — это тоже свечи, только в душе.",
        "Не суди по объёму, если не знаешь уровня боли.",
        "Кто пишет BULL — не всегда знает, где вверх.",
        "Даже Satoshi задумывался: стоило ли вообще это начинать?",
        "Один whitelist не делает тебя избранным.",
        "Тишина в чате — знак беды или медитации.",
        "Чем больше ты шлёшь проект друзьям, тем больше он похож на пирамиду.",
        "Не каждый, кто в маске анонима, знает хоть что-то.",
        "Лучшая инвестиция — в воздух после падения.",
        "Мудрый видит тренд даже в графике из кофе.",
        "Настоящий трейдер не читает новости — он их чувствует.",
        "Каждому падению есть отмазка. Уму — нет.",
        "Всё, что идёт вверх, обычно скамится на второй неделе.",
        "Не бывает плохих монет. Бывают плохие покупки.",
        "Тот, кто гнал за иксами — догонит печаль.",
        "Монета без сайта — путь в никуда. Или путь домой.",
        "Дуров говорит немного. Но его багфиксы — священны.",
        "Запомни: если токен твой взломали — значит заслужено.",
        "Хочешь быть мудрым — удали CoinMarketCap с телефона.",
        "Всё, что не пампает — закаляет.",
        "Настоящий Сенсей торгует в тишине, пересылая мемы.",
        "Каждый токен — это путь. Но не каждый путь с хэппи-эндом.",
        "Даже сквиз — это возможность. Или повод поплакать.",
        "Найди ликвидность в себе — и тебя не остановит ни один дамп.",
        "Сила Degen-а — в принятии хаоса.",
        "Больше ордеров — меньше надежд.",
        "Легенда гласит: Дуров проснулся, когда сбрили волну.",
        "Фома — это не слабость, а карма новичка.",
        "В каждом проседе ищи мудрость… или хотя бы урок.",
        "Когда не знаешь, что делать — создай токен.",
        "За каждым холдером — история боли.",
        "Даже если токен не взлетел, ты можешь взлететь с дивана.",
        "Манипуляция рынком — это искусство. Или преступление. Иногда оба.",
        "Курс битка не отражает курс жизни.",
        "Когда не можешь объяснить убытки — скажи, что 'фаза накопления'.",
        "Пусть твоя душа будет легче твоей просадки.",
        "Тот, кто удалил CoinGecko, может быть счастлив.",
        "Даже мудрый трейдер не объяснит, зачем купил этот токен.",
        "Не в цене счастье — а в количестве желудков, переваривших рис через убытки.",
        "Мудр тот, кто заработал в крипте и ушёл. Глуп тот, кто остался проверить ещё раз.",
        "Не бойся проиграть, бойся не попробовать.",
        "Даже мастер когда-то был учеником.",
        "Сила не в мышцах, а в духе.",
        "Падая, мы учимся летать.",
        "Путь к вершине начинается с первого шага. И VPN.",
        "Терпение — это когда ждёшь, пока Дуров добавит видеокружочки.",
        "Истинная сила — в двухфакторной аутентификации.",
        "Не бойся проиграть, бойся забыть seed-фразу.",
        "Даже Дуров когда-то был просто Пашей.",
        "Сила не в мышцах, а в количестве подписчиков.",
        "Падая на 90%, мы учимся холдить.",
        "Мудрость приходит с опытом (и ликвидациями).",
        "Кто контролирует стикеры — контролирует мир.",
        "Мудрый отключает уведомления на ночь.",
        "Не тот силён, кто в тысяче чатов, а тот, кто всё прочитал.",
        "Путь в тысячу каналов начинается с одной подписки.",
        "Истинный мастер архивирует, а не удаляет.",
        "Голосовое на 10 минут — признак слабости духа.",
        "Сенсей сказал: 'Читай, но не отвечай' — это и есть дзен.",
        "Кто первый поставил реакцию — тот и прав.",
        "В споре рождается истина, в чате — бан.",
        "Не суди о человеке по аватарке.",
        "Мастер отвечает не сразу, создавая интригу.",
        "Тишина в чате — предвестник важного сообщения.",
        "Покупай на страхе, продавай на жадности. Или наоборот. Я уже запутался.",
        "To the moon — сказал сенсей, и потерял депозит.",
        "HODL — это не упрямство, это философия.",
        "Diamond hands куются в огне маржин-колла.",
        "Не тот богат, кто имеет биткоин, а тот, кто купил его в 2010.",
        "Шиткоин сегодня — lambo никогда.",
        "Мудрый не шортит на бычьем рынке.",
        "Когда все кричат 'покупай' — уже поздно.",
        "Сенсей учил: 'DYOR'. Я погуглил, что это значит.",
        "Зелёная свеча радует, красная — закаляет.",
        "Терпение — это смотреть на -80% и не продавать.",
        "Путь трейдера — это путь самурая без денег.",
        "Не гонись за иксами — иксы придут сами. Или нет.",
        "Кто понял рынок — тот ничего не понял.",
        "Лучше синица в кошельке, чем NFT обезьяны.",
        "Сенсей сказал 'диверсифицируй', я купил 10 мемкоинов.",
        "Стоп-лосс — признак мудрости, а не трусости.",
        "Бычий рынок делает всех гениями. Медвежий — философами.",
        "Не спрашивай, когда moon. Спрашивай, зачем moon.",
        "Истинный мастер не проверяет портфель каждые 5 минут. Каждые 3.",
        "Дуров ушёл из ВК, чтобы мы могли быть свободными.",
        "Когда Дуров молчит — жди обновления.",
        "Сила Дурова — в минимализме гардероба.",
        "Чёрная водолазка скрывает тысячу эмоций.",
        "Дуров постит раз в месяц — и этого достаточно.",
        "Не тот крут, кто критикует Apple, а тот, кто создал альтернативу.",
        "Мудрый не ест мясо и сахар. Но я не мудрый.",
        "Семь сыновей — семь наследников Telegram.",
        "Дуров в Дубае, а мы с вами где?",
        "Сенсей Дуров учит молча, постами раз в квартал.",
        "Истинная свобода — это когда нет синей галочки.",
        "Не гонись за Дуровым, стань лучшей версией себя.",
        "Бот, который не отвечает — учит терпению.",
        "Админ канала видит всё, знает всё, банит всех.",
        "Мудрый бот не спамит, мудрый бот ждёт.",
        "Подписка на канал — это обязательство.",
        "Отписка — тоже путь.",
        "Не количество подписчиков красит канал, а качество мемов.",
        "Истинный мастер создаёт ботов, а не пользуется чужими.",
        "Inline-режим — высшая ступень просветления.",
        "Кнопка 'Отписаться' — всегда рядом.",
        "Канал без постов — как сенсей без учеников.",
        "VPN — щит современного воина.",
        "Приватность — это не паранойя, это гигиена.",
        "Кто читает terms of service — тот истинный мастер.",
        "Пароль '123456' — путь к страданиям.",
        "Облако хранит всё, но помнит ли оно?",
        "Мудрый не кликает на подозрительные ссылки.",
        "Фишинг — это тест на внимательность.",
        "Сенсей всегда проверяет URL дважды.",
        "Бэкап — это любовь к будущему себе.",
        "Кто архивирует чаты — тот контролирует историю.",
        "Печатает... печатает... — и ничего не отправляет.",
        "Оставить на 'прочитано' — искусство границ.",
        "Войс вместо текста — признак доверия. Или лени.",
        "Кто умеет в краткость — тот уважает чужое время.",
        "Много эмодзи — пустота внутри.",
        "Точка в конце сообщения пугает.",
        "Мем вовремя — тысячи слов.",
        "GIF заменяет эмоции, которые мы боимся показать.",
        "Тот, кто не использует тёмную тему — не знает покоя.",
        "Не тот чат главный, где больше людей, а где тебя понимают.",
        "Удалённое сообщение интригует больше отправленного.",
        "Пересланное сообщение — это мост между мирами.",
        "Закреплённое сообщение — якорь канала.",
        "Мут на год — это не наказание, это медитация.",
        "Ник без цифр — признак олда.",
        "Bio — это хайку цифровой эпохи.",
        "Юзернейм занят — вселенная говорит 'подумай ещё'.",
        "Премиум — это не понты, это поддержка Дурова.",
        "Галочка верификации не делает тебя настоящим.",
        "Истинный путь — между онлайном и оффлайном.",
        "Сенсей учил: 'Выйди из интернета, подыши воздухом'.",
        "Но мы всё равно здесь, читаем эти мудрости.",
        "Потому что путь бесконечен, а чат вечен.",
        "И помни: Дуров следит за тобой. Шучу. Или нет.",
        "Телеграм — это не мессенджер, это образ жизни.",
        "Последняя мудрость: не ищи мудрость — создавай мемы.",
        "P.S. Не забудь поставить реакцию 🔥",
        "Мудрость приходит с опытом (и шишками).",
    ]

    @staticmethod
    def _esc(text: Any) -> str:
        if text is None:
            return ""
        return html.escape(str(text))

    @staticmethod
    def _ellipsize(text: str, limit: int) -> str:
        if not text:
            return ""
        text = str(text)
        if len(text) > limit:
            return text[:limit-1] + "…"
        return text

    @classmethod
    def _frame(cls, lines: List[str], width: int) -> str:
        """Создает рамку вокруг списка строк (Left-only style)."""
        out = [cls.frame_top_left(width)]
        for line in lines:
            out.append(cls.frame_line_left(line, width))
        out.append(cls.frame_bottom_left(width))
        return cls._render_block(out)

    @staticmethod
    def _mention(username: str) -> str:
        if not username:
            return ""
        return f"@{username}"

    @staticmethod
    def _fmt_coins(amount: Optional[float]) -> str:
        if amount is None:
            return "—"
        return f"{int(amount):,.0f}".replace(",", " ")

    @staticmethod
    def cross() -> str:
        return "❌"

    @staticmethod
    def cross_raw() -> str:
        return "❌"

    @staticmethod
    def wait_raw() -> str:
        return "⏳"

    @staticmethod
    def trophy_raw() -> str:
        return "🏆"

    @staticmethod
    def fire_raw() -> str:
        return "🔥"

    @staticmethod
    def escape(text: str) -> str:
        """Экранирование HTML-спецсимволов."""
        if text is None:
            return ""
        return html.escape(str(text))

    @staticmethod
    def progress_bar(current: int, maximum: int, length: int = 10, style: str = "block") -> str:
        """📊 Статический прогресс-бар (без деления на ноль)."""
        length = _clamp_int(int(length), 6, 14)
        if maximum <= 0:
            percent = 0
            filled = 0
        else:
            ratio = max(0.0, min(1.0, current / maximum))
            percent = int(ratio * 100)
            filled = int(ratio * length)

        styles = {
            "block": ("█", "░"),
            "arrow": ("▶", "▷"),
            "circle": ("●", "○"),
            "square": ("■", "□"),
            "star": ("★", "☆"),
        }

        full, empty = styles.get(style, styles["block"])
        bar = full * filled + empty * (length - filled)
        return f"{bar} {percent}%"

    @staticmethod
    def frame_top(width: int = 28) -> str:
        return Visuals.frame_top_left(width)

    @staticmethod
    def frame_bottom(width: int = 28) -> str:
        return Visuals.frame_bottom_left(width)

    @staticmethod
    def frame_line(text: str, width: int = 28, align: str = "left") -> str:
        return Visuals.frame_line_left(text, width, align)

    @staticmethod
    def frame_separator(width: int = 28) -> str:
        return Visuals.frame_separator_left(width)

    @staticmethod
    def frame_top_left(width: int = 28) -> str:
        if Visuals.STYLE in ("clean", "crypto"):
            return ""
        return "┏" + "━" * width

    @staticmethod
    def frame_bottom_left(width: int = 28) -> str:
        if Visuals.STYLE in ("clean", "crypto"):
            return ""
        return "┗" + "━" * width

    @staticmethod
    def frame_line_left(text: str, width: int = 28, align: str = "left") -> str:
        text = str(text)
        if Visuals.STYLE == "crypto":
            return text.strip()

        if Visuals.STYLE == "clean":
            if align == "center":
                if width < len(text):
                    width = len(text)
                return text.center(width).rstrip()
            return text

        if align == "center":
            # "┃ " takes 2 chars. We aim for `width` total chars? 
            # Original frame_line returned width chars exactly.
            # Here we might just want to center relative to the implied width.
            content_w = width - 2
            if content_w < len(text):
                content_w = len(text)
            padded = text.center(content_w)
            return f"┃ {padded}"
        return f"┃ {text}"

    @staticmethod
    def frame_separator_left(width: int = 28) -> str:
        if Visuals.STYLE == "crypto":
            return ""
        if Visuals.STYLE == "clean":
            return "─" * width
        return "┣" + "━" * width
        
    @staticmethod
    def get_katana_art_ascii(length: float) -> str:
        """
        Получить только ASCII арт катаны (без HTML тегов)
        """
        def clamp(n: int, lo: int, hi: int) -> int:
            return max(lo, min(hi, n))

        blade_len = clamp(int(round(length * 0.28)) + 6, 6, 16)

        tiers = [
            (5,  "⟦■⟧",     "╦", "",  "I",  "НОЖ Дно-Копателя"),
            (7,  "⟦■■⟧",    "╦", "",  "I",  "Шард-лезвие"),
            (10, "⟦■■■⟧",   "╬", "",  "II", "Великий HODL-Меч"),
            (14, "⟦▣▣⟧",    "╬", "",  "III","Нейронный вакидзаси"),
            (19, "⟦▣✦▣⟧",   "╬", "✦", "IV", "КАТАНА ДУРОВА"),
            (23, "⟦≣▣▣≣⟧",  "╬", "✦", "V",  "ГОЙСКИЙ КЛИНОК"),
            (29, "⟦✦✦✦⟧",   "◈", "✦", "VI", "Red Blood Tanto"),
            (38, "⟦☾☾⟧",    "◈", "☾", "VII","Хеш-клинок Сатоши"),
            (48, "⟦☯☯☯⟧",   "◈", "☯", "VIII","DAO-клинок"),
            (60, "⟦⚔⚔⟧",    "✦", "⚔", "IX", "НАГАМАКИ ЧЕРНЫЙ-ЛЕБЕДЬ"),
            (80, "⟦⚔⚔⚔⟧",   "✦", "⚔", "X",  "НАГИНАТО-СБРИВАТОР"),
            (math.inf, "⟦☯⚔☯⟧","✧", "☯", "XI", "УБИЙЦА БОГОВ"),
        ]

        for limit, hilt, guard, rune, rank, name in tiers:
            if length < limit:
                if not rune or blade_len <= 10:
                    blade = "═" * blade_len
                else:
                    left = blade_len // 2 - 1
                    blade = ("═" * left) + rune + ("═" * (blade_len - left - 1))

                art = f"{hilt}{guard}{blade}►"
                return art

        return ""

    @staticmethod
    def get_katana_art(length: float) -> str:
        # НАЗВАНИЯ КЛИНКОВ НЕ ТРОГАЕМ
        def clamp(n: int, lo: int, hi: int) -> int:
            return max(lo, min(hi, n))

        # На телефонах длинное лезвие часто ломает перенос — сделаем чуть короче,
        # но оставим "характер" арта. (Если хочешь старую длину — скажешь.)
        blade_len = clamp(int(round(length * 0.28)) + 6, 6, 16)

        tiers = [
            (5,  "⟦■⟧",     "╦", "",  "I",  "НОЖ Дно-Копателя"),
            (7,  "⟦■■⟧",    "╦", "",  "I",  "Шард-лезвие"),
            (10, "⟦■■■⟧",   "╬", "",  "II", "Великий HODL-Меч"),
            (14, "⟦▣▣⟧",    "╬", "",  "III","Нейронный вакидзаси"),
            (19, "⟦▣✦▣⟧",   "╬", "✦", "IV", "КАТАНА ДУРОВА"),
            (23, "⟦≣▣▣≣⟧",  "╬", "✦", "V",  "ГОЙСКИЙ КЛИНОК"),
            (29, "⟦✦✦✦⟧",   "◈", "✦", "VI", "Red Blood Tanto"),
            (38, "⟦☾☾⟧",    "◈", "☾", "VII","Хеш-клинок Сатоши"),
            (48, "⟦☯☯☯⟧",   "◈", "☯", "VIII","DAO-клинок"),
            (60, "⟦⚔⚔⟧",    "✦", "⚔", "IX", "НАГАМАКИ ЧЕРНЫЙ-ЛЕБЕДЬ"),
            (80, "⟦⚔⚔⚔⟧",   "✦", "⚔", "X",  "НАГИНАТО-СБРИВАТОР"),
            (math.inf, "⟦☯⚔☯⟧","✧", "☯", "XI", "УБИЙЦА БОГОВ"),
        ]
        
        for limit, hilt, guard, rune, rank, name in tiers:
            if length < limit:
                return name, rank
        
        return "Unknown", "I"

    @classmethod
    def crypto_price_card(
        cls,
        symbol: str,
        usd: float,
        rub: float,
        change: float,
        market_cap: Optional[float] = None,
        market_cap_rub: Optional[float] = None
    ) -> str:
        """Карточка курса криптовалюты."""
        w = cls.FRAME_W_PROFILE
        emoji = "📈" if change >= 0 else "📉"
        change_sign = "+" if change >= 0 else ""
        
        lines = [
            cls.frame_top_left(w),
            cls.frame_line_left(f"📊 {symbol.upper()} MARKET", w),
            cls.frame_separator_left(w),
            cls.frame_line_left(f"🇺🇸 {usd:,.4f} $", w),
            cls.frame_line_left(f"🇷🇺 {rub:,.2f} ₽", w),
            cls.frame_line_left(f"{emoji} {change_sign}{change:.2f}% (24h)", w),
            cls.frame_separator_left(w),
            cls.frame_line_left("💰 Капитализация:", w),
        ]
        
        if market_cap:
             lines.append(cls.frame_line_left(f"🇺🇸 ${market_cap:,.0f}", w))
             if market_cap_rub:
                 lines.append(cls.frame_line_left(f"🇷🇺 ₽{market_cap_rub:,.0f}", w))
        else:
             lines.append(cls.frame_line_left("❓ Неизвестно", w))

        lines.append(cls.frame_bottom_left(w))
        return cls._render_block(lines)

    @classmethod
    def exchange_info_card(cls) -> str:
        """Информационная карточка обмена."""
        w = cls.FRAME_W_PROFILE
        lines = [
            cls.frame_top_left(w),
            cls.frame_line_left("💱 ОБМЕН ВАЛЮТ", w, "center"),
            cls.frame_separator_left(w),
            cls.frame_line_left("Курсы обмена:", w),
            cls.frame_line_left("", w),
            cls.frame_line_left("💰 1000 -> 🎫 1", w),
            cls.frame_line_left("🎫 1 -> 💰 900", w),
            cls.frame_bottom_left(w),
        ]
        return cls._render_block(lines)

    @classmethod
    def profile_card(
        cls,
        username: str,
        level: int,
        level_name: str,
        xp: int,
        xp_next: int,
        coins: float,
        tickets: int,
        messages: int,
        streak: int,
        has_katana: bool,
        achievements_count: int,
        katana_length: float = 0.0,
        wins: int = 0,
        losses: int = 0,
        role: Optional[str] = None,
    ) -> str:
        """Карточка профиля пользователя."""
        username_short = cls._ellipsize(username, 14)
        name_line = cls._ellipsize(level_name, 20)
        
        # Progress bar
        xp_bar = cls.progress_bar(xp, xp_next, length=12)
        
        # Katana info
        katana_name = "Нет катаны"
        if has_katana:
            name, _ = cls.get_katana_art(katana_length)
            katana_name = name
            
        katana_title_short = cls._ellipsize(katana_name, 20)

        box_lines = [
            f"ПРОФИЛЬ {username_short}",
        ]
        
        if role:
            box_lines.append(f"👺 {role}")
            
        box_lines.extend([
            f"⭐ Уровень: {level}",
            f"👤 {name_line}",
            f"🔥 XP: {int(xp)}/{int(xp_next)}",
            f"{xp_bar}",
            f"💰{int(coins)}  🎫{tickets}  💬{messages}",
            f"💱 ≈ {coins * 0.0002:,.2f} USDT",
        ])
        
        if has_katana:
            box_lines.append(f"🗡 {katana_length:.1f} см")
            box_lines.append(f"{katana_title_short}")
            
        box_lines.append(f"⚔ W{wins} / L{losses}")

        # Основная карточка + катана-арт ниже (как "деталь")
        art_ascii = ""
        if has_katana:
             art_ascii = cls.get_katana_art_ascii(katana_length)
             
        if cls.STYLE == "crypto":
             art_block = f"<code>{art_ascii}</code>" if art_ascii else ""
        else:
             art_block = f"<pre>{art_ascii}</pre>" if art_ascii else ""

        return (
            f"<b>📈 {cls._esc(username_short)}</b>\n"
            f"{cls._frame(box_lines, width=cls.FRAME_W_PROFILE)}\n"
            f"{art_block}\n"
            f"<i>{cls._esc(random.choice(cls.WISDOM))}</i>"
        )

    @classmethod
    def get_level_up_animation(cls, level: int, level_name: str, username: str = "") -> str:
        """Анимация повышения уровня."""
        # фикс: нормальная индентация + mobile-friendly рамка
        level = int(level)
        level_name = str(level_name or "")

        user = (username or "").strip()
        user = cls._ellipsize(user, 22) if user else "🎯"

        # компактный прогресс
        progress = min(level / 100.0, 1.0)
        w = 12
        bar_filled = "█" * int(progress * w)
        bar_empty = "░" * (w - len(bar_filled))
        p_line = f"[{bar_filled}{bar_empty}] {progress * 100:.0f}%"

        lines = [
            "✨ УРОВЕНЬ ПОВЫШЕН! ✨",
            f"{user}",
            f"⭐ Уровень: {level}",
            f"🗡 {cls._ellipsize(level_name, 24)}",
            p_line,
        ]
        
        return cls._frame(lines, width=cls.FRAME_W_LEVELUP)

    @classmethod
    def bank_card(cls, stats: dict) -> str:
        """Карточка статистики банка."""
        w = cls.FRAME_W_PROFILE
        bank = stats.get("bank", {})
        tickets = stats.get("tickets", {})
        tx_stats = stats.get("transactions", {})
        circulation = stats.get("circulation", 0)

        balance = bank.get("balance", 0)
        collected = bank.get("total_collected", 0)
        distributed = bank.get("total_distributed", 0)
        
        # Transactions stats
        tickets_bought = tx_stats.get("exchange_in", {}).get("count", 0)
        tickets_burned = tx_stats.get("exchange_out", {}).get("count", 0)

        lines = [
            cls.frame_top_left(w),
            cls.frame_line_left("🏦 SENSEI BANK", w, "center"),
            cls.frame_separator_left(w),
            cls.frame_line_left(f"💰 Баланс: {balance:,.0f}", w),
            cls.frame_line_left(f"🪙 В обороте: {circulation:,.0f}", w),
            cls.frame_separator_left(w),
            cls.frame_line_left("📊 Статистика:", w),
            cls.frame_line_left(f"📥 Собрано: {collected:,.0f}", w),
            cls.frame_line_left(f"📤 Выдано: {distributed:,.0f}", w),
            cls.frame_separator_left(w),
            cls.frame_line_left("🎫 Билеты:", w),
            cls.frame_line_left(f"🛒 Куплено: {tickets_bought}", w),
            cls.frame_line_left(f"🔥 Сожжено: {tickets_burned}", w),
            cls.frame_line_left(f"🏷 Активно: {tickets.get('active', 0)}", w),
            cls.frame_bottom_left(w),
        ]
        return cls._render_block(lines)

    @classmethod
    def top_table(cls, title: str, emoji: str, items: List[Dict[str, Any]], value_key: str) -> str:
        """Таблица топа."""
        if cls.STYLE == "crypto":
            lines = [f"<b>{emoji} {title}</b>"]
            if not items:
                lines.append("Пока пусто...")
            else:
                for i, item in enumerate(items, 1):
                    username = cls.escape(item.get("username", "Unknown"))
                    val = item.get(value_key, 0)
                    if isinstance(val, (int, float)):
                        val_str = f"{val:,.0f}" if val >= 10000 else f"{val}"
                    else:
                        val_str = str(val)
                    
                    lines.append(f"{i}. <b>{username}</b>: <code>{val_str}</code>")
            return "\n".join(lines)

        w = cls.FRAME_W_MENU
        lines = [
            cls.frame_top_left(w),
            cls.frame_line_left(f"{emoji} {title}", w, "center"),
            cls.frame_separator_left(w),
        ]

        if not items:
            lines.append(cls.frame_line_left("Пока пусто...", w, "center"))
        else:
            for i, item in enumerate(items, 1):
                username = cls.escape(item.get("username", "Unknown"))
                val = item.get(value_key, 0)
                
                if isinstance(val, (int, float)):
                    val_str = f"{val:,.0f}" if val >= 10000 else f"{val}"
                else:
                    val_str = str(val)

                rank_str = f"{i}."
                
                # Width calc
                # Frame content width = w - 2 (border "┃ ")
                # We just need to fit text into w - 2 chars.
                
                available_w = w - 2
                
                # Strategy: "1. Name...    Value"
                
                max_name_len = available_w - len(rank_str) - len(val_str) - 2
                if max_name_len < 3:
                    max_name_len = 3
                
                short_name = username[:max_name_len]
                
                left_part = f"{rank_str} {short_name}"
                spaces_count = max(1, available_w - len(left_part) - len(val_str))
                
                full_row = f"{left_part}{' ' * spaces_count}{val_str}"
                
                lines.append(cls.frame_line_left(full_row, w))

        lines.append(cls.frame_bottom_left(w))
        return cls._render_block(lines)

    @classmethod
    def top_katana_table(cls, title: str, emoji: str, items: List[Dict[str, Any]], offset: int = 0) -> str:
        """Таблица топа катан с артами."""
        if cls.STYLE == "crypto":
            lines = [f"<b>{emoji} {title}</b>"]
            if not items:
                lines.append("Пока пусто...")
            else:
                for i, item in enumerate(items, 1 + offset):
                    username = cls.escape(item.get("username", "Unknown"))
                    length = item.get("katana_length", 0.0)
                    val_str = f"{length:.1f} см"
                    art = cls.get_katana_art_ascii(length)
                    lines.append(f"{i}. <b>{username}</b>: <code>{val_str}</code>")
                    lines.append(f"<code>{art}</code>")
            return "\n".join(lines)

        w = cls.FRAME_W_MENU
        lines = [
            cls.frame_top_left(w),
            cls.frame_line_left(f"{emoji} {title}", w, "center"),
            cls.frame_separator_left(w),
        ]

        if not items:
            lines.append(cls.frame_line_left("Пока пусто...", w, "center"))
        else:
            for i, item in enumerate(items, 1 + offset):
                username = cls.escape(item.get("username", "Unknown"))
                length = item.get("katana_length", 0.0)
                
                val_str = f"{length:.1f} см"
                rank_str = f"{i}."
                
                # Line 1: Rank Name Length
                available_w = w - 4
                
                max_name_len = available_w - len(rank_str) - len(val_str) - 2
                if max_name_len < 3:
                    max_name_len = 3
                
                short_name = username[:max_name_len]
                
                left_part = f"{rank_str} {short_name}"
                spaces_count = max(1, available_w - len(left_part) - len(val_str))
                
                full_row = f"{left_part}{' ' * spaces_count}{val_str}"
                lines.append(cls.frame_line_left(full_row, w))
                
                # Line 2: Art (centered)
                art = cls.get_katana_art_ascii(length)
                # Cut art if too long for frame (should fit, but safety first)
                if len(art) > w - 4:
                     art = art[:w-4]
                
                lines.append(cls.frame_line_left(art, w, "center"))
                
                # Separator if not last
                if i < len(items) + offset:
                     lines.append(cls.frame_separator_left(w))

        lines.append(cls.frame_bottom_left(w))
        return cls._render_block(lines)

    @classmethod
    def katana_info(cls, length: float) -> str:
        w = cls.FRAME_W_PROFILE
        art = cls.get_katana_art_ascii(length)
        name, rank = cls.get_katana_art(length)
        
        lines = [
            cls.frame_top_left(w),
            cls.frame_line_left("🗡️ ТВОЯ КАТАНА", w, "center"),
            cls.frame_separator_left(w),
            cls.frame_line_left(f"📏 Длина: {length:.1f} см", w),
            cls.frame_line_left(f"🎖 Ранг: {rank}", w),
            cls.frame_line_left(f"🏷 {name}", w),
            cls.frame_separator_left(w),
            cls.frame_line_left(art, w, "center"),
            cls.frame_bottom_left(w),
        ]
        return cls._render_block(lines)

    @classmethod
    def katana_upgrade_result(cls, is_success: bool, growth: float, length: float, cost: float) -> str:
        if is_success:
            status = f"✅ +{growth:.2f}"
        else:
            status = f"💔 -{abs(growth):.2f}"
            
        _, rank = cls.get_katana_art(length)
        art = cls.get_katana_art_ascii(length)
        
        # Line 1: Status | Length | Rank | Cost
        line1 = f"{status} см | 📏 {length:.1f} см ({rank}) | 💰 -{int(cost)}"
        # Line 2: Art
        line2 = f"{art}"
        
        return f"<code>{line1}\n{line2}</code>"

    @classmethod
    def help_card(cls) -> str:
        """Карточка помощи."""
        w = cls.FRAME_W_PROFILE
        lines = [
            cls.frame_top_left(w),
            cls.frame_line_left("🥋 SENSEI 2.3", w, "center"),
            cls.frame_bottom_left(w),
        ]
        header = "<pre>\n" + "\n".join(lines) + "\n</pre>"
        
        body = (
            "<b>📋 Основные:</b>\n"
            "• /start — перезапустить бота\n"
            "• /mysensei — профиль\n"
            "• /senseitop — топ игроков\n"
            "• /senseidaily — ежедневный бонус\n"
            "• /senseiobmen — обмен валют\n"
            "• /senseibank — банк сенсея\n"
            "• /senseireferal — рефералы\n"
            "• /senseihelp — справка\n\n"
            
            "<b>⚔️ Игры и Активности:</b>\n"
            "• /mykatana — моя катана\n"
            "• /upkatana — улучшить катану\n"
            "• /topkatana — топ катан\n"
            "• /senseislots [ставка] — казино\n"
            "• /trade [ставка] — трейдинг\n"
            "• /duel [ставка] — дуэль (reply)\n"
            "• /senseiviktorina — викторина\n\n"
            
            "<b>🗞️ Чат:</b>\n"
            "• /digest — краткая сводка (admin)\n"
            "• /stats — статистика чата\n"
            "• /music [трек] — поиск музыки\n"
            "• <code>сенсей мудрец [вопрос]</code> — ИИ ответ\n\n"

            "<b>💬 Триггеры:</b>\n"
            "• <code>ежа</code> / <code>фарма</code> — бонус\n"
            "• <code>+fire [сумма]</code> — раздача монет\n"
            "• <code>сенсей дай курс</code> — топ крипты\n"
            "• <code>курс TON</code> — цена монеты\n"
            "• <code>курс № TON № 100</code> — калькулятор\n\n"
            "<i>💾 SENSEI.AI v2.3</i>"
        )
        return f"{header}\n{body}"

    @classmethod
    def start_menu(cls, name: str) -> str:
        """Стартовое меню."""
        w = cls.FRAME_W_PROFILE
        safe_name = cls.escape(name)[:20]
        
        lines = [
            cls.frame_top_left(w),
            cls.frame_line_left("🥋 SENSEI 2.3", w, "center"),
            cls.frame_separator_left(w),
            cls.frame_line_left(f"Привет, {safe_name}!", w, "center"),
            cls.frame_line_left("Я помогу тебе стать", w, "center"),
            cls.frame_line_left("легендой этого чата!", w, "center"),
            cls.frame_separator_left(w),
            cls.frame_line_left("👇 Выбери действие:", w, "center"),
            cls.frame_bottom_left(w),
        ]
        menu = "<pre>\n" + "\n".join(lines) + "\n</pre>"
        link = '<a href="https://telegra.ph/SENSEI-BOT-ULTIMATE-GUIDE-01-05">🏯 SENSEI BOT: ULTIMATE GUIDE</a>'
        return f"{menu}\n{link}"

    @classmethod
    def welcome_message(cls, name: str, phrase: str) -> str:
        """Сообщение приветствия."""
        return f"🥋 НОВЕНЬКИЙ\n{phrase}"

    @classmethod
    def daily_reward(cls, xp: int, coins: float, streak: int, bonus_xp: int = 0, bonus_coins: float = 0.0) -> str:
        w = cls.FRAME_W_PROFILE
        
        lines = [
            cls.frame_top_left(w),
            cls.frame_line_left("🎁 ЕЖЕДНЕВНЫЙ БОНУС", w, "center"),
            cls.frame_separator_left(w),
            cls.frame_line_left(f"⚡ +{xp} XP", w),
            cls.frame_line_left(f"💰 +{coins:.2f} монет", w),
            cls.frame_separator_left(w),
            cls.frame_line_left(f"🔥 Страйк: {streak} дн.", w),
        ]
        
        if bonus_xp > 0 or bonus_coins > 0:
             lines.append(cls.frame_separator_left(w))
             lines.append(cls.frame_line_left("✨ БОНУС СТРАЙКА ✨", w, "center"))
             if bonus_xp > 0:
                 lines.append(cls.frame_line_left(f"⚡ +{bonus_xp} XP", w))
             if bonus_coins > 0:
                 lines.append(cls.frame_line_left(f"💰 +{bonus_coins:.2f} монет", w))

        lines.append(cls.frame_bottom_left(w))
        return "<pre>\n" + "\n".join(lines) + "\n</pre>"

    @classmethod
    def referral_card(cls, stats: Any, link: str) -> str:
        """Карточка реферальной системы."""
        w = cls.FRAME_W_PROFILE
        rank_title = stats.rank.title
        rank_emoji = stats.rank.emoji
        
        lines = [
            cls.frame_top_left(w),
            cls.frame_line_left("🤝 РЕФЕРАЛЬНАЯ СИСТЕМА", w, "center"),
            cls.frame_separator_left(w),
            cls.frame_line_left(f"{rank_emoji} Ранг: {rank_title}", w),
            cls.frame_separator_left(w),
            cls.frame_line_left("👥 Приглашено:", w),
            cls.frame_line_left(f"   L1: {stats.level_1_count} чел.", w),
            cls.frame_line_left(f"   L2: {stats.level_2_count} чел.", w),
            cls.frame_separator_left(w),
            cls.frame_line_left("💰 Заработано:", w),
            cls.frame_line_left(f"   {stats.total_coins_earned:,.0f} монет", w),
            cls.frame_line_left(f"   {stats.total_xp_earned} XP", w),
            cls.frame_separator_left(w),
            cls.frame_line_left("🔗 Твоя ссылка:", w),
            cls.frame_bottom_left(w),
        ]
        
        card = "<pre>\n" + "\n".join(lines) + "\n</pre>"
        return f"{card}\n{link}"

    @staticmethod
    def _trade_terminal(
        screen: str | Sequence[str],
        *,
        glow: str,
        username: str = "",
        # HUD
        symbol: str = "BTCUSDT",
        price: str = "—",
        change: str = "—",
        mode: str = "AIR",
        exch: str = "SENSEI",
        ping_ms: int | None = None,
        spread: str = "—",
    ) -> str:
        """
        Telegram HTML: <pre><code>...</code></pre>
        ВАЖНО: кликабельный <a> лучше добавлять СНАРУЖИ <pre>.
        """
        INNER_W = 30            # ширина между ┃ ┃
        PAD = 1
        SCREEN_W = INNER_W - PAD * 2  # 28

        def fit(s: str, w: int) -> str:
            s = (s or "")
            return s[:w].ljust(w)

        def cut(s: str, w: int) -> str:
            s = (s or "")
            return s[:w]

        def top(label: str) -> str:
            label = cut(label, INNER_W)
            fill = INNER_W - len(label)
            L = fill // 2
            R = fill - L
            return "┏" + ("━" * L) + label + ("━" * R)

        def sep() -> str:
            return "┣" + ("━" * INNER_W)

        def bot() -> str:
            return "┗" + ("━" * INNER_W)

        # screen: 3 строки
        if isinstance(screen, str):
            parts = screen.splitlines()
        else:
            parts = list(screen)

        s1 = fit(parts[0] if len(parts) > 0 else "", SCREEN_W)
        s2 = fit(parts[1] if len(parts) > 1 else "", SCREEN_W)
        s3 = fit(parts[2] if len(parts) > 2 else "", SCREEN_W)

        # HUD
        # glow лучше не emoji, чтобы не "ломать" ширину в моноширине
        label = f"[{mode} {exch} TERM {glow}]"
        label = cut(label, INNER_W)

        ping_txt = f"{int(ping_ms):03d}ms" if ping_ms is not None else "—ms"
        hud1 = f"● LIVE  PING:{ping_txt}  SPR:{spread}"
        hud1 = fit(hud1, INNER_W)

        sym = cut(symbol, 10)
        hud2 = f"{sym:<10} PX:{cut(price,10):<10} Δ:{cut(change,7):<7}"
        hud2 = fit(hud2, INNER_W)

        footer = fit("KEYS: /buy /sell /sl /tp /close", INNER_W)

        lines = [
            top(label),
            f"┃{hud1}",
            f"┃{hud2}",
            sep(),
            f"┃{' '*PAD}{s1}{' '*PAD}",
            f"┃{' '*PAD}{s2}{' '*PAD}",
            f"┃{' '*PAD}{s3}{' '*PAD}",
            sep(),
            f"┃{footer}",
            bot(),
        ]

        terminal_html = "<pre><code>" + Visuals._esc("\n".join(lines)) + "</code></pre>"
        if username:
            terminal_html += "\n" + Visuals._mention(username)
        return terminal_html

    @staticmethod
    def get_trade_animation(
        username: str = "",
        *,
        frames_count: int = 8,
        theme: "CompactTheme" = None,
        rng: Optional[random.Random] = None,
    ) -> List[str]:
        rng = rng or random.Random()
        frames_count = max(1, min(int(frames_count), 12))
        theme = theme or CompactTheme()

        glows = getattr(theme, "glows", None) or ["◇", "◆", "◈", "⬡", "⟡", "✶"]
        glow = rng.choice(glows)

        symbol = getattr(theme, "symbol", "BTCUSDT")
        exch = getattr(theme, "exchange", "NEON")
        mode = getattr(theme, "mode", "WCS")

        cursor = getattr(theme, "cursor", "▌")
        W = 28  # SCREEN_W в _trade_terminal

        def fit(s: str) -> str:
            return (s or "")[:W].ljust(W)

        def clamp(x: float, a: float, b: float) -> float:
            return a if x < a else b if x > b else x

        def sparkline(vals: List[float], width: int) -> str:
            # ▁▂▃▄▅▆▇█
            blocks = "▁▂▃▄▅▆▇█"
            if not vals:
                return " " * width
            lo = min(vals)
            hi = max(vals)
            if hi - lo < 1e-9:
                return blocks[0] * width
            out = []
            n = len(vals)
            for i in range(width):
                # сэмплинг по ширине
                idx = int(i * (n - 1) / max(1, width - 1))
                v = vals[idx]
                t = (v - lo) / (hi - lo)
                k = int(clamp(t, 0.0, 1.0) * (len(blocks) - 1) + 1e-9)
                out.append(blocks[k])
            return "".join(out)

        def bar(n: int, width: int, ch_full: str = "█", ch_empty: str = "░") -> str:
            n = max(0, min(int(n), width))
            return (ch_full * n) + (ch_empty * (width - n))

        def glitch_noise(i: int, width: int) -> str:
            pool = "·•:;=+*x"
            out = []
            for x in range(width):
                v = (x * 17 + i * 31) % 97
                out.append(pool[(v + x) % len(pool)] if (v % 6 == 0) else " ")
            return "".join(out)

        def with_cursor(s: str, i: int) -> str:
            if not cursor:
                return s
            pos = i % max(1, W)
            s = fit(s)
            return s[:pos] + cursor + s[pos + 1:]

        # "кинематографичный" сценарий: chart -> book -> execution -> victory
        base = rng.randint(45_000, 125_000)
        vol = rng.randint(40, 140)  # амплитуда качки
        drift = rng.choice([-1, 1]) * rng.randint(5, 25)

        hist: List[float] = []
        frames: List[str] = []

        for i in range(frames_count):
            # псевдо-рынок: синус + дрейф + небольшой шум
            px = base + drift * i + int(math.sin(i * 0.9) * vol) + rng.randint(-12, 12)
            hist.append(float(px))
            if len(hist) > 32:
                hist = hist[-32:]

            price = f"{px:,}".replace(",", " ")
            ref = hist[0]
            chg = ((px - ref) / ref) * 100.0 if ref else 0.0
            change = f"{chg:+.2f}%"

            ping = 18 + (i * 7) % 67
            spread = f"{(6 + (i * 3) % 19):02d}bp"

            # SCREEN: 3 строки, каждая по 28
            # 1) CHART
            sl = sparkline(hist, 20)
            s1 = f"CHART {sl}  "
            s1 = fit(s1)

            # 2) BOOK (две стороны в одной строке)
            # делаем "псевдостакан": bid растёт, ask падает, чтобы была динамика
            bid = 4 + (i * 3) % 10
            ask = 12 - (i * 2) % 9
            left = bar(bid, 10, "▓", "░")
            right = bar(ask, 10, "▓", "░")
            s2 = f"BOOK  B:{left} A:{right}"
            s2 = fit(s2)

            # 3) FLOW / EXEC (глитч + курсор)
            if i < frames_count - 2:
                msg = "FLOW  " + glitch_noise(i, W - 6)
            else:
                # финальные кадры: "EXECUTED" как победный акцент
                stamp = "EXECUTED @ MARKET"
                msg = "FLOW  " + stamp.ljust(W - 6)
            s3 = with_cursor(fit(msg), i)

            screen = "\n".join([s1, s2, s3])

            frames.append(
                Visuals._trade_terminal(
                    screen,
                    glow=glow,
                    username=username,
                    symbol=symbol,
                    price=price,
                    change=change,
                    mode=mode,
                    exch=exch,
                    ping_ms=ping,
                    spread=spread,
                )
            )

        return frames

    @staticmethod
    def get_trade_result(
        direction: str,
        is_win: bool,
        profit: int = 0,
        remaining_coins: Optional[int] = None,
        username: str = "",
        bet: int = 0,
        fee: int = 0,
        theme: CompactTheme = CompactTheme(),
        rng: Optional[random.Random] = None,
    ) -> str:
        rng = rng or random.Random()
        theme = theme or CompactTheme()

        # --- style knobs (как у терминала) ---
        INNER_W = 30
        PAD = 1
        SCREEN_W = INNER_W - PAD * 2  # 28

        def fit(s: str, w: int) -> str:
            s = (s or "")
            return s[:w].ljust(w)

        def cut(s: str, w: int) -> str:
            s = (s or "")
            return s[:w]

        def top(label: str) -> str:
            label = cut(label, INNER_W)
            fill = INNER_W - len(label)
            L = fill // 2
            R = fill - L
            return "┏" + ("━" * L) + label + ("━" * R)

        def sep() -> str:
            return "┣" + ("━" * INNER_W)

        def bot() -> str:
            return "┗" + ("━" * INNER_W)

        def bar(n: int, width: int, full: str = "▓", empty: str = "░") -> str:
            n = max(0, min(int(n), width))
            return (full * n) + (empty * (width - n))

        # --- direction ---
        d = (direction or "").strip().lower()
        long_ = d in ("long", "buy", "up", "лонг")
        short_ = d in ("short", "sell", "down", "шорт")
        if not long_ and not short_:
            long_ = True  # дефолт
        dir_tag = "LONG ▲" if long_ else "SHORT ▼"

        # --- theme fields ---
        glows = getattr(theme, "glows", None) or ["◇", "◆", "◈", "⬡", "⟡", "✶"]
        glow = rng.choice(glows)
        mode = getattr(theme, "mode", "WCS")
        exch = getattr(theme, "exchange", "NEON")

        # --- pnl / balance ---
        amt = abs(int(profit or 0))
        if amt == 0:
            pnl_signed = "±0"
        else:
            pnl_signed = ("+" if is_win else "-") + Visuals._fmt_coins(amt)

        bal_str = Visuals._fmt_coins(remaining_coins) if remaining_coins is not None else "—"

        # --- chart direction: "правильно угадал" = тренд в сторону позиции ---
        chart_up = (long_ and is_win) or ((not long_) and (not is_win))
        arrow = "▲" if chart_up else "▼"
        base_wave = "▁▂▃▄▅▆▇███▇▆▅▄▃▂"
        wave = base_wave if chart_up else base_wave[::-1]
        wave = cut(wave, 21)

        # --- power/edge ---
        # win выглядит "мощнее", но чуть шевелим RNG, чтобы не было статично
        strength = (8 if is_win else 3) + rng.randint(-1, 1)
        strength = max(0, min(strength, 10))
        pwr = strength * 10

        win_notes = ["SYSTEM BREACHED", "ALPHA CONFIRMED", "EXEC CLEAN", "EDGE LOCKED", "SIGNAL TRUE"]
        loss_notes = ["STOP HIT", "RISK FAILED", "SLIPPAGE", "EDGE BROKE", "RECALIBRATE"]
        note = rng.choice(win_notes if is_win else loss_notes)

        # --- build terminal ---
        label = f"[{mode} {exch} RESULT {glow}]"
        label = cut(label, INNER_W)

        res_word = "WIN" if is_win else "LOSS"
        hud1 = fit(f"● SETTLED   {dir_tag:<7}   {res_word}", INNER_W)
        hud2 = fit(f"P/L:{cut(pnl_signed,10):<10} BAL:{cut(bal_str,11):<11}", INNER_W)

        s1 = fit(f"CHART {wave}{arrow}", SCREEN_W)
        s2 = fit(f"EDGE  {bar(strength, 10)}  PWR:{pwr:02d}%", SCREEN_W)
        s3 = fit(f"NOTE  {note}", SCREEN_W)

        footer = fit("NEXT: /again /share /stats", INNER_W)

        lines = [
            top(label),
            f"┃{hud1}",
            f"┃{hud2}",
            sep(),
            f"┃{' '*PAD}{s1}{' '*PAD}",
            f"┃{' '*PAD}{s2}{' '*PAD}",
            f"┃{' '*PAD}{s3}{' '*PAD}",
            sep(),
            f"┃{footer}",
            bot(),
        ]

        terminal_html = "<pre><code>" + Visuals._esc("\n".join(lines)) + "</code></pre>"

        # кликабельное упоминание и "карточка баланса" — СНАРУЖИ <pre>
        extras: List[str] = []
        if username:
            extras.append(Visuals._mention(username))
        if remaining_coins is not None:
            extras.append(f"💳 BAL <code>{Visuals._fmt_coins(remaining_coins)}</code>")

        return terminal_html + (("\n" + "\n".join(extras)) if extras else "")

        w = cls.FRAME_W_PROFILE
        lines = [
            cls.frame_top(w),
            cls.frame_line(f"{emoji} {title}", w, "center"),
            cls.frame_separator(w),
        ]
        
        for i, item in enumerate(items, 1):
            name = cls.escape(item.get("username", "Unknown"))
            val = item.get(value_key, 0)
            if isinstance(val, float):
                val_str = f"{val:,.0f}"
            else:
                val_str = f"{val:,}"
            
            rank_str = f"{i}."
            content_w = w - 4
            
            # Simple layout: "1. Name... Value"
            left_part = f"{rank_str} {name}"
            # Cut name if too long
            
            # max length for left part to leave room for value and 1 space
            max_left = content_w - len(val_str) - 1
            if len(left_part) > max_left:
                left_part = left_part[:max_left-1] + "…"
            
            spaces = content_w - len(left_part) - len(val_str)
            if spaces < 1: spaces = 1
            
            line_content = f"{left_part}{' ' * spaces}{val_str}"
            lines.append(cls.frame_line(line_content, w))
            
        lines.append(cls.frame_bottom(w))
        return "<pre>\n" + "\n".join(lines) + "\n</pre>"

    @classmethod
    def exchange_result(cls, direction: str, amount_from: float, amount_to: float, currency_from: str, currency_to: str) -> str:
        w = cls.FRAME_W_PROFILE
        lines = [
            cls.frame_top_left(w),
            cls.frame_line_left("💱 ОБМЕН УСПЕШЕН", w, "center"),
            cls.frame_separator_left(w),
            cls.frame_line_left(f"Отдано:", w),
            cls.frame_line_left(f"  {currency_from} {amount_from:,.2f}", w),
            cls.frame_line_left(f"Получено:", w),
            cls.frame_line_left(f"  {currency_to} {amount_to:,.2f}", w),
            cls.frame_bottom_left(w),
        ]
        return "<pre>\n" + "\n".join(lines) + "\n</pre>"

    # -------------------------
    # 🎰 SLOTS VISUALS
    # -------------------------

    SYMBOLS: Tuple[str, ...] = ("🍒", "🍋", "🍊", "💎", "⭐", "7️⃣", "👁️", "🟣")
    FX: Tuple[str, ...] = ("⟡", "✶", "⌁", "⚡️", "🌀", "🌪")
    WILD = "🟣"

    @staticmethod
    def _vwidth(s: str) -> int:
        return len(s) # Simplified for now, as we don't have wcwidth

    @staticmethod
    def _pad_to_vwidth(s: str, w: int) -> str:
        s = s or ""
        cur = len(s)
        if cur >= w:
            return s
        return s + (" " * (w - cur))

    @staticmethod
    def _fit_ascii(s: str, w: int) -> str:
        s = (s or "")
        return s[:w].ljust(w)

    @staticmethod
    def _fit_tokens(tokens: Sequence[str], w: int) -> str:
        out = ""
        for t in tokens:
            t = t or ""
            cand = out + t
            if len(cand) > w:
                break
            out = cand
        return Visuals._pad_to_vwidth(out, w)

    @staticmethod
    def _bar(n: int, width: int, full: str = "█", empty: str = "░") -> str:
        n = max(0, min(int(n), width))
        return (full * n) + (empty * (width - n))

    @staticmethod
    def _reels_line(a: str, b: str, c: str, w: int, *, lock: int = 0) -> str:
        def reel(sym: str, locked: bool) -> List[str]:
            return (["⟦", sym, "⟧"] if locked else [" ", sym, " "])

        return Visuals._fit_tokens(
            ["▶"]
            + reel(a, lock >= 1) + ["│"]
            + reel(b, lock >= 2) + ["│"]
            + reel(c, lock >= 3) + ["◀"],
            w,
        )

    @staticmethod
    def _combo_info(a: str, b: str, c: str) -> Tuple[str, bool, bool]:
        wild = Visuals.WILD
        s = [a, b, c]
        has_wild = wild in s
        uniq = {x for x in s if x != wild}

        if len(uniq) == 0:
            return ("OMEGA WILD", True, True)
        if len(uniq) == 1:
            return ("TRIPLE", has_wild, True)
        if len(uniq) == 2:
            return ("PAIR", has_wild, False)
        return ("MISS", has_wild, False)

    @staticmethod
    def _slots_terminal(
        screen: Sequence[str],
        *,
        glow: str,
        username: str = "",
        bet: int = 0,
        fee: int = 0,
        prize: int = 0,
        balance: Optional[float] = None,
        state: str = "IDLE",
        note: str = "",
    ) -> str:
        INNER_W = 30
        PAD = 1
        SCREEN_W = INNER_W - PAD * 2

        def cut(s: str, w: int) -> str:
            s = (s or "")
            return s[:w]

        def top(label: str) -> str:
            label = cut(label, INNER_W)
            fill = INNER_W - len(label)
            L = fill // 2
            R = fill - L
            return "┏" + ("━" * L) + label + ("━" * R)

        def sep() -> str:
            return "┣" + ("━" * INNER_W)

        def bot() -> str:
            return "┗" + ("━" * INNER_W)

        label = cut(f"[SENSEI SLOTS {glow}]", INNER_W)

        hud1 = Visuals._fit_ascii(f"● LIVE  BET:{bet:>6}  FEE:{fee:>6}", INNER_W)

        bal_txt = f"{balance:,.0f}" if balance is not None else "—"
        pot_txt = f"{prize:,.0f}" if prize else "—"
        hud2 = Visuals._fit_ascii(
            f"BAL:{cut(bal_txt,12):<12} POT:{cut(pot_txt,12):<12}", INNER_W
        )

        scr = list(screen)[:3]
        while len(scr) < 3:
            scr.append("")
        s1 = Visuals._fit_ascii(scr[0], SCREEN_W)
        s2 = Visuals._fit_ascii(scr[1], SCREEN_W)
        s3 = Visuals._fit_ascii(scr[2], SCREEN_W)

        state_line = Visuals._fit_ascii(f"STATE: {state}", INNER_W)
        note_line = Visuals._fit_ascii(note, INNER_W) if note else Visuals._fit_ascii("", INNER_W)
        footer = Visuals._fit_ascii("KEYS: /spin /bet /cashout", INNER_W)

        lines = [
            top(label),
            f"┃{hud1}",
            f"┃{hud2}",
            sep(),
            f"┃{' ' * PAD}{s1}{' ' * PAD}",
            f"┃{' ' * PAD}{s2}{' ' * PAD}",
            f"┃{' ' * PAD}{s3}{' ' * PAD}",
            sep(),
            f"┃{state_line}",
            f"┃{note_line}",
            f"┃{footer}",
            bot(),
        ]

        html_code = "<pre><code>" + Visuals.escape("\n".join(lines)) + "</code></pre>"

        extras: List[str] = []
        if username:
            extras.append(f"👤 {Visuals.escape(username)}")
        # if balance is not None:
        #     extras.append(f"💳 <code>{balance:,.0f}</code>")
        # if bet:
        #     extras.append(f"🎫 BET <code>{bet}</code>")
        # if fee:
        #     extras.append(f"🏦 FEE <code>{fee}</code>")
        if prize and prize > 0:
            extras.append(f"💰 WIN <code>+{prize:,.0f}</code>")

        return html_code + (("\n" + "\n".join(extras)) if extras else "")

    @staticmethod
    def get_slots_animation(
        username: str,
        balance: float,
        *,
        bet: int = 0,
        fee: int = 0,
        spins: int = 6,
        final_symbols: Optional[Sequence[str]] = None,
        rng: Optional[random.Random] = None,
    ) -> List[str]:
        rng = rng or random.Random()
        spins = max(1, min(int(spins), 12))

        glows = ["◇", "◆", "◈", "⬡", "⟡", "✶"]
        glow = rng.choice(glows)

        symbols_pool = Visuals.SYMBOLS
        fx = Visuals.FX

        frames: List[str] = []
        run_id = f"{rng.getrandbits(16):04X}-{rng.getrandbits(16):04X}"

        fin = list(final_symbols[:3]) if final_symbols else []
        while fin and len(fin) < 3:
            fin.append("❔")
        fin_a = fin[0] if fin else None
        fin_b = fin[1] if fin else None
        fin_c = fin[2] if fin else None

        lock_plan = 0
        if fin:
            combo, has_wild, triple_like = Visuals._combo_info(fin_a, fin_b, fin_c)
            if combo == "OMEGA WILD" or triple_like:
                lock_plan = 2
            elif combo == "PAIR" or has_wild:
                lock_plan = 1
            else:
                lock_plan = 0

        lock_at = max(1, spins - 2)
        reveal_at = spins - 1

        for i in range(spins):
            fxi = fx[i % len(fx)]
            rpm = 700 + i * 170 + rng.randint(-40, 40)
            heat = min(10, 2 + i)
            jitter = (i * 9 + rng.randint(0, 9)) % 10

            lock_now = 0
            if fin and i >= lock_at:
                lock_now = min(lock_plan, 1 + (i - lock_at))

            if fin:
                a = fin_a if lock_now >= 1 else rng.choice(symbols_pool)
                b = fin_b if lock_now >= 2 else rng.choice(symbols_pool)
                c = fin_c if i == reveal_at else rng.choice(symbols_pool)
            else:
                a = rng.choice(symbols_pool)
                b = rng.choice(symbols_pool)
                c = rng.choice(symbols_pool)

            if i == 0:
                state = "BOOT"
                l1 = Visuals._fit_ascii(f"{fxi} BOOT SEQUENCE  RUN:{run_id}", 28)
            elif i < lock_at:
                state = "OVERCLOCK"
                l1 = Visuals._fit_ascii(f"{fxi} OVERCLOCK  HEAT:{heat:02d}/10", 28)
            elif i == lock_at:
                state = "LOCKING"
                l1 = Visuals._fit_ascii(f"{fxi} LOCK-IN  HOLD YOUR BREATH", 28)
            else:
                state = "REVEAL"
                l1 = Visuals._fit_ascii(f"{fxi} REVEAL  RPM:{rpm:04d}", 28)

            l2 = Visuals._reels_line(a, b, c, 28, lock=lock_now)
            l3 = Visuals._fit_ascii(
                f"CORE  {Visuals._bar(heat, 10, '▓', '░')}  J:{jitter}",
                28,
            )

            frames.append(
                Visuals._slots_terminal(
                    [l1, l2, l3],
                    glow=glow,
                    username=username,
                    bet=bet,
                    fee=fee,
                    balance=balance,
                    state=state,
                    note=f"SYNC:OK  RUN:{run_id}",
                )
            )

        return frames

    @staticmethod
    def get_slots_result(
        result_symbols: Sequence[str],
        is_win: bool,
        prize: float,
        username: str,
        remaining_coins: float,
        bet: int,
        fee: int,
    ) -> str:
        
        state = "WINNER!" if is_win else "WASTED"
        glow = "✨" if is_win else "💀"
        
        a, b, c = result_symbols[:3]
        
        l1 = Visuals._fit_ascii(f"RESULT: {state}", 28)
        l2 = Visuals._reels_line(a, b, c, 28, lock=3)
        l3 = Visuals._fit_ascii(f"PRIZE: {prize:,.0f}", 28)
        
        return Visuals._slots_terminal(
            [l1, l2, l3],
            glow=glow,
            username=username,
            bet=bet,
            fee=fee,
            balance=remaining_coins,
            prize=prize,
            state=state,
            note="GAME OVER"
        )
