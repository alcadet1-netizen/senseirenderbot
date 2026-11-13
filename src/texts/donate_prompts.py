"""Short factual Stars/Coin invitations; selection frequency belongs to callers."""
import random

DONATE_CHAT_PHRASES = (
    '🥋 Сенсей достиг дзена. Теперь копит SenseiCoin. /donate — пакеты за Stars, если хочется поддержать проект.',
    '⭐ Звёзды с неба не хватаю — Stars принимаю через /donate. Взамен SenseiCoin из SenseiBank, без финансового просветления.',
    '🦔 Ёж советует не колоться, а заглянуть в /donate: там SenseiCoin за Stars. Покупать необязательно, гладить воздух бесплатно.',
    '💰 Кошелёк самурая тоже хочет приключений. /donate покажет пакеты SenseiCoin за Stars — решение за тобой.',
    '🥢 Палочками монеты ловить неудобно. В /donate есть SenseiCoin за Stars — без акробатики и обещаний разбогатеть.',
    '🧘 Просветление не продаётся. SenseiCoin за Stars — да: /donate. Не перепутай покупки.',
    '🏯 В додзё ремонт кармы. Кто хочет поддержать проект и взять SenseiCoin за Stars — /donate. Остальным можно просто болтать.',
    '🐉 Дракон охраняет сокровища, я охраняю кнопку /donate. Там пакеты SenseiCoin за Stars, а не билет в миллионеры.',
)

DONATE_INACTIVE_PHRASES = (
    '🦗 Пока вы молчали, сверчки попросили зарплату. Хочешь поддержать проект? /donate — SenseiCoin за Stars. Без обязательств.',
    '💤 Чат медитирует, Сенсей считает пылинки. /donate покажет пакеты SenseiCoin за Stars, если захочется поддержать додзё.',
    '🥋 Тишина такая, что слышно, как ёж думает. Его мысль: «А что там в /donate?» SenseiCoin за Stars, колючий ты маркетолог.',
    '⭐ Все ушли в астрал? Если вернёшься со Stars, /donate покажет пакеты SenseiCoin. Можно и без Stars — просто напиши что-нибудь.',
    '🏯 В додзё тихо. Сенсей открыл ларёк: /donate — SenseiCoin за Stars. Вход свободный, покупать не обязательно.',
    '🧘 Час тишины — бесплатный курс дзена. /donate — уже не курс, а пакеты SenseiCoin за Stars. Не путай духовное с игровым.',
    '🦔 Ёж дежурит, чат спит. /donate поможет поддержать проект покупкой SenseiCoin за Stars. Ежу процент не положен.',
    '🐉 Даже дракон уснул от тишины. Проснётся — спросит про /donate. Там SenseiCoin за Stars, а не гарантированный клад.',
)


def get_random_donate_phrase():
    return random.choice(DONATE_CHAT_PHRASES)


def get_inactive_donate_phrase():
    return random.choice(DONATE_INACTIVE_PHRASES)
