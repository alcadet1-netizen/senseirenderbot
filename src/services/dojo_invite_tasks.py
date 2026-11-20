"""One lifetime quest card. Pay each direct referral milestone once."""
from datetime import datetime, timezone

from src.services.hedgehog_service import GameError
from src.services.referral_economy import transaction

TIERS = ((1, 1000), (5, 6000), (25, 30000))
SLUGS = {f'invite_friends_{goal}' for goal, _ in TIERS}


def card(stage, count):
    goal, reward = TIERS[min(stage, len(TIERS) - 1)]
    return {'slug': f'invite_friends_{goal}', 'kind': 'invite_friends', 'goal': goal,
            'progress': min(goal, count), 'reward_coins': reward, 'energy_bonus': 0,
            'claimed': stage == len(TIERS)}


class InviteTasks:
    def __init__(self, mongo):
        self.mongo = mongo
        self.db = mongo.database

    async def progress(self, uid, session=None):
        user = await self.db.users.find_one({'id': uid}, session=session)
        if not user or user.get('is_banned'):
            raise GameError('Профиль недоступен.')
        count = await self.db.users.count_documents({'referrer_id': uid, 'id': {'$ne': uid},
            'is_bot': {'$ne': True}, 'is_banned': {'$ne': True}}, limit=25, session=session)
        return user, count

    async def current(self, uid):
        user, count = await self.progress(uid)
        return card(user.get('dojo_invite_stage', 0), count)

    async def claim(self, uid, slug):
        async def work(session):
            user, count = await self.progress(uid, session)
            stage = user.get('dojo_invite_stage', 0)
            task = card(stage, count)
            if task['claimed'] or slug != task['slug']:
                raise GameError('Этот этап не активен. Обнови задания.')
            if count < task['goal']:
                raise GameError(f"Приглашено друзей: {count} из {task['goal']}.")
            reward = task['reward_coins']
            debit = await self.db.bank.update_one({'_id': 'single', 'coins': {'$gte': reward}},
                {'$inc': {'coins': -reward}}, session=session)
            if not debit.matched_count:
                raise GameError('SenseiBank не может выплатить награду. Попробуй позже.')
            await self.db.users.update_one({'id': uid}, {'$inc': {'coins': reward, 'dojo_invite_stage': 1}}, session=session)
            await self.db.transactions.insert_one({'_id': f'dojo:{uid}:{slug}', 'user_id': uid,
                'tx_type': 'dojo_invite_task', 'coins_change': reward, 'created_at': datetime.now(timezone.utc)}, session=session)
            return {'task': card(stage + 1, count), 'energy_bonus': 0, 'reward_coins': reward,
                    'new_coins': user.get('coins', 0) + reward}
        return await transaction(self.mongo, work)
