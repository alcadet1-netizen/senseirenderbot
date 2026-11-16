import pytest
from src.services.fly_censor import censor_fly_reply


@pytest.mark.parametrize('source,expected', [
    ('Иди на хуй!', 'Иди на х№й!'),
    ('заебал', 'з"еб%л'),
    ('не еби мозги', 'не е#и мозги'),
    ('Нахуй?', 'Нах№й?'),
    ('ХУЙ', 'Х№Й'),
    ('хуёвый', 'х№ёвый'),
    ('пиздец', 'п%здец'),
    ('блядь', 'бл*дь'),
    ('сука', 'с*ка'),
    ('Страхуй корабля у берега. Учебник стоит три рубля.',
     'Страхуй корабля у берега. Учебник стоит три рубля.'),
    ('Сенсей всё видит 🥋', 'Сенсей всё видит 🥋'),
])
def test_fly_profanity_mask(source, expected):
    assert censor_fly_reply(source) == expected
    assert censor_fly_reply(expected) == expected
