"""Durable, transactional player-funded duel escrow (no bank or emission)."""
import logging
from datetime import datetime, timezone

from pymongo.errors import DuplicateKeyError

from src.services.bank_ledger import _matched
from src.services.referral_economy import transaction
from src.services.transaction_retry import retry_initial_namespace


logger = logging.getLogger(__name__)


class DuelRequestAlreadyUsed(Exception):
    """A prior Telegram update already created this escrow."""


class DuelEscrow:
    def __init__(self, mongo):
        self.mongo = mongo
        self.users = mongo.database.users
        self.escrows = mongo.database.duel_escrows
        self.transactions = mongo.database.transactions

    async def reserve(self, escrow_id, cid, oid, bet, duel_id, *, reject_existing=False):
        async def apply(tx):
            previous = await self.escrows.find_one({'_id': escrow_id}, session=tx)
            if previous:
                if reject_existing:
                    raise DuelRequestAlreadyUsed()
                if (previous['challenger_id'], previous['opponent_id'], previous['bet']) != (cid, oid, bet):
                    raise RuntimeError('Duel escrow identifier conflict')
                return True
            first = await self.users.find_one({'id': cid}, session=tx)
            second = await self.users.find_one({'id': oid}, session=tx)
            if not first or not second or first.get('coins', 0) < bet or second.get('coins', 0) < bet:
                return False
            for uid in (cid, oid):
                result = await self.users.update_one({'id': uid, 'coins': {'$gte': bet}},
                    {'$inc': {'coins': -float(bet)}}, session=tx)
                if not _matched(result):
                    raise RuntimeError('Duel stake debit missed')
            now = datetime.now(timezone.utc)
            await self.escrows.insert_one({'_id': escrow_id, 'duel_id': duel_id,
                'challenger_id': cid, 'opponent_id': oid, 'bet': bet,
                'state': 'reserved', 'award_version': 1, 'created_at': now}, session=tx)
            for uid in (cid, oid):
                await self.transactions.insert_one({'user_id': uid, 'tx_type': 'duel_escrow',
                    'coins_change': -float(bet), 'xp_change': 0, 'escrow_id': escrow_id,
                    'description': f'Ставка в дуэли #{duel_id}', 'created_at': now}, session=tx)
            return True
        try:
            return await retry_initial_namespace(transaction, self.mongo, apply)
        except DuplicateKeyError:
            prior = await self.escrows.find_one({'_id': escrow_id})
            if prior and reject_existing:
                raise DuelRequestAlreadyUsed()
            if prior and (prior['challenger_id'], prior['opponent_id'], prior['bet']) == (cid, oid, bet):
                return True
            raise

    async def settle(self, escrow_id, winner_id=None):
        """Winner gets both held stakes; None returns each stake to its owner."""
        # Persist the decision first, so a crash between outcome and payout
        # cannot turn a win into a refund or choose a different winner.
        async def decide(tx):
            entry = await self.escrows.find_one({'_id': escrow_id}, session=tx)
            if not entry:
                raise RuntimeError('Duel escrow not found')
            ids = (entry['challenger_id'], entry['opponent_id'])
            if winner_id is not None and winner_id not in ids:
                raise ValueError('Invalid duel winner')
            if entry['state'] in ('decided', 'settled'):
                if entry.get('winner_id') != winner_id:
                    raise RuntimeError('Duel escrow already decided differently')
                return
            if entry['state'] != 'reserved':
                raise RuntimeError('Invalid duel escrow state')
            changed = await self.escrows.update_one({'_id': escrow_id, 'state': 'reserved'},
                {'$set': {'state': 'decided', 'winner_id': winner_id}}, session=tx)
            if not _matched(changed):
                raise RuntimeError('Duel escrow decision changed')
        await transaction(self.mongo, decide)

        async def apply(tx):
            entry = await self.escrows.find_one({'_id': escrow_id}, session=tx)
            if not entry or entry.get('winner_id') != winner_id:
                raise RuntimeError('Duel escrow decision missing or changed')
            if entry['state'] == 'settled':
                return entry
            if entry['state'] != 'decided':
                raise RuntimeError('Invalid duel escrow state')
            ids = (entry['challenger_id'], entry['opponent_id'])
            payouts = [(winner_id, 2 * entry['bet'])] if winner_id is not None else [(uid, entry['bet']) for uid in ids]
            now = datetime.now(timezone.utc)
            for uid, amount in payouts:
                credit = await self.users.update_one({'id': uid}, {'$inc': {'coins': float(amount)}}, session=tx)
                if not _matched(credit):
                    raise RuntimeError('Duel payout recipient missing')
                await self.transactions.insert_one({'user_id': uid,
                    'tx_type': 'duel_bet_payout' if winner_id is not None else 'duel_bet_refund',
                    'coins_change': float(amount), 'xp_change': 0, 'escrow_id': escrow_id,
                    'description': f'Ставка в дуэли #{entry["duel_id"]}', 'created_at': now}, session=tx)
            details = None
            if winner_id is not None and entry.get('award_version') == 1:
                loser_id = ids[1] if winner_id == ids[0] else ids[0]
                winner = await self.users.find_one({'id': winner_id}, session=tx)
                loser = await self.users.find_one({'id': loser_id}, session=tx)
                if not winner or not loser:
                    raise RuntimeError('Duel result participant missing')
                winner_update = {'$inc': {'wins': 1, 'xp': 50}}
                loser_update = {'$inc': {'losses': 1}}
                if winner.get('has_katana', False):
                    winner_update['$set'] = {'katana_length': round((winner.get('katana_length', 0.0) or 0.0) + 0.01, 2)}
                if loser.get('has_katana', False):
                    loser_update['$set'] = {'katana_length': round(max(0.0, (loser.get('katana_length', 0.0) or 0.0) - 0.01), 2)}
                if not _matched(await self.users.update_one({'id': winner_id}, winner_update, session=tx)):
                    raise RuntimeError('Duel winner missing')
                if not _matched(await self.users.update_one({'id': loser_id}, loser_update, session=tx)):
                    raise RuntimeError('Duel loser missing')
                for uid, tx_type, xp in ((winner_id, 'duel_win', 50), (loser_id, 'duel_loss', 0)):
                    await self.transactions.insert_one({'user_id': uid, 'tx_type': tx_type,
                        'xp_change': xp, 'coins_change': 0, 'escrow_id': escrow_id,
                        'description': f'Результат дуэли #{entry["duel_id"]}', 'created_at': now}, session=tx)
                details = {'winner_name': winner.get('username') or winner.get('first_name') or str(winner_id),
                           'loser_name': loser.get('username') or loser.get('first_name') or str(loser_id),
                           'winner_has_katana': bool(winner.get('has_katana', False)),
                           'loser_has_katana': bool(loser.get('has_katana', False))}
            result = await self.escrows.update_one({'_id': escrow_id, 'state': 'decided'},
                {'$set': {'state': 'settled', 'winner_id': winner_id, 'settled_at': now,
                          'result_details': details}}, session=tx)
            if not _matched(result):
                raise RuntimeError('Duel escrow state changed')
            return {**entry, 'state': 'settled', 'winner_id': winner_id, 'settled_at': now, 'result_details': details}
        return await transaction(self.mongo, apply)

    async def recover_decided(self):
        """Complete recorded decisions only; never decide or refund live fights.

        Multiple workers may scan the same rows: settle is idempotent and
        the Mongo transaction serializes credits against the escrow document.
        A corrupt record or missing recipient cannot prevent other recoveries.
        """
        recovered = 0
        async for entry in self.escrows.find({'state': 'decided'}):
            try:
                if 'winner_id' not in entry:
                    raise ValueError('Duel decision has no winner field')
                await self.settle(entry['_id'], entry['winner_id'])
                recovered += 1
            except Exception:
                logger.exception('Duel decision recovery failed: escrow=%s', entry.get('_id'))
        return recovered
