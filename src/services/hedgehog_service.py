"""Server-owned 12-second daily game. One persisted outcome per user / UTC day."""
import secrets
import time
from datetime import datetime, timedelta, timezone

from pymongo import ReturnDocument

from src.core.exceptions import DailyAlreadyClaimedError

GAME_SECONDS = 12
WIN_PERCENT = 95
FAILURE_MESSAGE = (
    'Вы не смогли погладить ежа! 🦔 Ёж включил режим кактуса и ушёл по делам. '
    'Ежедневная серия сброшена. Монеты и XP остались при вас. Реванш — завтра!'
)


def utc_day() -> str:
    return datetime.now(timezone.utc).date().isoformat()


class GameError(ValueError):
    pass


class HedgehogService:
    def __init__(self, mongo, daily_service, reward_mode="tap_bonus"):
        self.reward_mode = reward_mode
        self.games = mongo.database.hedgehog_games
        self.users = mongo.database.users
        self.daily = daily_service

    async def ensure_indexes(self):
        await self.games.create_index('token', unique=True)
        await self.games.create_index('expires_at', expireAfterSeconds=0)

    async def issue(self, user_id: int) -> dict:
        user = await self.users.find_one({'id': user_id})
        if not user or user.get('is_banned'):
            raise GameError('Профиль недоступен. Откройте /start.')
        day = utc_day()
        if user.get('hedgehog_day') == day:
            raise DailyAlreadyClaimedError('завтра после 00:00 UTC')
        available, remaining = await self.daily.can_claim(user_id)
        if not available:
            raise DailyAlreadyClaimedError(remaining)
        game = await self.games.find_one_and_update(
            {'_id': f'{user_id}:{day}'},
            {'$setOnInsert': {
                'user_id': user_id, 'day': day, 'mode': self.reward_mode, 'token': secrets.token_urlsafe(24),
                'state': 'issued', 'expires_at': datetime.now(timezone.utc) + timedelta(days=7),
            }}, upsert=True, return_document=ReturnDocument.AFTER,
        )

        # Unstarted invitations can adopt the new rules without choosing or
        # rerolling an outcome. Never rewrite playing/done historical sessions.
        if self.reward_mode == 'tap_bonus' and game['state'] == 'issued' and game.get('mode') != 'tap_bonus':
            updated = await self.games.find_one_and_update(
                {'_id': game['_id'], 'state': 'issued'}, {'$set': {'mode': 'tap_bonus'}},
                return_document=ReturnDocument.AFTER,
            )
            game = updated or await self.games.find_one({'_id': game['_id']})
        return game

    async def owned(self, token: str, user_id: int) -> dict:
        if not isinstance(token, str) or len(token) > 64:
            raise GameError('Неверная ссылка игры.')
        game = await self.games.find_one({'token': token, 'user_id': user_id, 'day': utc_day()})
        if not game:
            raise GameError('Игра не найдена или наступил новый день. Откройте /senseidaily.')
        return game

    async def start(self, token: str, user_id: int) -> dict:
        game = await self.owned(token, user_id)
        if game['state'] == 'issued':
            # CAS makes reloads/tabs keep the original start and random outcome.
            updated = await self.games.find_one_and_update(
                {'_id': game['_id'], 'state': 'issued'},
                {'$set': {'state': 'playing', 'started_at': time.time(),
                          'taps': 0, 'tap_seq': 0,
                          'won': True if game.get('mode') == 'tap_bonus' else secrets.randbelow(100) < WIN_PERCENT}},
                return_document=ReturnDocument.AFTER,
            )
            game = updated or await self.owned(token, user_id)
        if game['state'] == 'done':
            return {'state': 'done', 'result': game['result']}
        return {'state': 'playing', 'remaining_ms': max(0, round(
            (GAME_SECONDS - (time.time() - game['started_at'])) * 1000)),
                'tap_seq': game.get('tap_seq', 0), 'taps': game.get('taps', 0), 'bonus_percent': game.get('taps', 0) * 10}

    async def tap(self, token: str, user_id: int, sequence: int) -> dict:
        """Credit bounded server-timed taps, never a client-supplied tap count."""
        game = await self.owned(token, user_id)
        if type(sequence) is not int or not 1 <= sequence <= 100:
            raise GameError('Неверный номер поглаживания.')
        if game['state'] != 'playing' or time.time() - game['started_at'] >= GAME_SECONDS:
            return await self.finish(token, user_id)
        if game.get('mode') != 'tap_bonus':
            return await self.start(token, user_id)
        now = time.time()
        previous = game.get('last_tap_at', game['started_at'])
        if (sequence > game.get('tap_seq', 0) and game.get('taps', 0) < 5
                and now - previous >= 1.5):
            await self.games.find_one_and_update(
                {'_id': game['_id'], 'state': 'playing', 'taps': game.get('taps', 0),
                 'tap_seq': game.get('tap_seq', 0)},
                {'$inc': {'taps': 1}, '$set': {'tap_seq': sequence, 'last_tap_at': now}},
                return_document=ReturnDocument.AFTER,
            )
        game = await self.owned(token, user_id)
        return {'state': 'playing', 'remaining_ms': max(0, round(
            (GAME_SECONDS - (time.time() - game['started_at'])) * 1000)),
                'tap_seq': game.get('tap_seq', 0), 'taps': game.get('taps', 0), 'bonus_percent': game.get('taps', 0) * 10}

    async def finish(self, token: str, user_id: int) -> dict:
        game = await self.owned(token, user_id)
        if game['state'] == 'done':
            return {'state': 'done', 'result': game['result']}
        if game['state'] not in {'playing', 'settling'}:
            raise GameError('Сначала поздоровайтесь с ежом!')
        remaining = GAME_SECONDS - (time.time() - game['started_at'])
        if remaining > 0:
            return {'state': 'playing', 'remaining_ms': max(100, round(remaining * 1000))}
        frozen = await self.games.find_one_and_update(
            {'_id': game['_id'], 'state': 'playing'}, {'$set': {'state': 'settling'}},
            return_document=ReturnDocument.AFTER,
        )
        game = frozen or await self.owned(token, user_id)
        if game['state'] == 'done':
            return {'state': 'done', 'result': game['result']}
        # The user document is the atomic financial receipt. Retrying after a
        # disconnect or restart returns it without adding rewards a second time.
        result = await self.daily.settle_hedgehog(
            user_id, game['won'], game['day'],
            tap_count=game.get('taps', 0) if game.get('mode') == 'tap_bonus' else 0,
        )
        await self.games.update_one({'_id': game['_id']}, {'$set': {'state': 'done', 'result': result}})
        return {'state': 'done', 'result': result}
