"""Verify Telegram Mini App initData; never trust initDataUnsafe or client user IDs."""
import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl


def verify_init_data(raw: str, bot_token: str, *, now=None) -> dict:
    if not isinstance(raw, str) or not raw or len(raw) > 8192:
        raise ValueError('Откройте игру внутри Telegram.')
    pairs = parse_qsl(raw, keep_blank_values=True, strict_parsing=True)
    if len({key for key, _ in pairs}) != len(pairs):
        raise ValueError('Повторяющиеся поля авторизации.')
    fields = dict(pairs)
    supplied = fields.pop('hash', '')
    check = '\n'.join(f'{key}={value}' for key, value in sorted(fields.items()))
    secret = hmac.new(b'WebAppData', bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, supplied):
        raise ValueError('Неверная подпись Telegram.')
    clock = time.time() if now is None else now
    age = clock - int(fields.get('auth_date', '0'))
    if age < -30 or age > 3600:
        raise ValueError('Сессия устарела. Откройте игру заново.')
    user = json.loads(fields.get('user', '{}'))
    if not isinstance(user, dict) or type(user.get('id')) is not int or user['id'] <= 0:
        raise ValueError('Нет пользователя Telegram.')
    return user
