"""Durable, transactional player-funded duel escrow (no bank or emission)."""
import logging
from datetime import datetime, timezone

from pymongo.errors import DuplicateKeyError

from src.services.bank_ledger import _matched
from src.services.referral_economy import transaction


logger = logging.getLogger(__name__)


class DuelEscrow:
    def __init__(self, mongo):
        self.mongo = mongo
        self.users = mongo.database.users
        self.escrows = mongo.database.duel_escrows
        self.transactions = mongo.database.transactions

    async def reserve(self, escrow_id, cid, oid, bet, duel_id):
        async def apply(tx):
            previous = await self.escrows.find_one({'_id': escrow_id}, session=tx)
            if previous:
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
                'state': 'reserved', 'created_at': now}, session=tx)
            for uid in (cid, oid):
                await self.transactions.insert_one({'user_id': uid, 'tx_type': 'duel_escrow',
                    'coins_change': -float(bet), 'xp_change': 0, 'escrow_id': escrow_id,
                    'description': f'Ставка в дуэли #{duel_id}', 'created_at': now}, session=tx)
            return True
        try:
            return await transaction(self.mongo, apply)
        except DuplicateKeyError:
            prior = await self.escrows.find_one({'_id': escrow_id})
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
            result = await self.escrows.update_one({'_id': escrow_id, 'state': 'decided'},
                {'$set': {'state': 'settled', 'winner_id': winner_id, 'settled_at': now}}, session=tx)
            if not _matched(result):
                raise RuntimeError('Duel escrow state changed')
            return {**entry, 'state': 'settled', 'winner_id': winner_id, 'settled_at': now}
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
