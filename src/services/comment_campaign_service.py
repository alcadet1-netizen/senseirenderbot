"""Durable MongoDB-backed comment campaigns; transactions and fenced batch work."""
import asyncio
import html
import logging
import secrets
import uuid
from contextlib import suppress
from datetime import datetime, timedelta, timezone

from aiogram.types import MessageOriginChannel, ReplyParameters, Update
from src.infra.comment_campaign_inbox import CampaignInbox
from pymongo import ASCENDING, ReturnDocument
from pymongo.errors import DuplicateKeyError
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern

logger = logging.getLogger(__name__)
UTC = timezone.utc

START_TEXT = ('🎉 Розыгрыш Coin начался!\n\n'
              'За каждый комментарий под этим постом вы получите 100 Coin.\n'
              'Один случайный комментарий получит 2000 Coin!\n\n'
              '⏳ Итоги и начисление наград — через 4 часа.')
USER_CONTENT_TYPES = frozenset('text,photo,video,animation,audio,voice,video_note,document,sticker,poll,contact,location,venue,dice'.split(','))
EMPTY_TEXT = '🏁 Розыгрыш завершён. За 4 часа не было подходящих комментариев, поэтому награды не начислены.'


def utc(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class LeaseLost(RuntimeError):
    pass


class CommentCampaignService:
    def __init__(self, container, *, clock=None):
        self.container = container
        self.cfg = container.settings
        self.db = container.mongo_client.database
        self.campaigns = self.db.comment_campaigns
        self.comments = self.db.campaign_comments
        self.routes = self.db.campaign_message_routes
        self.rewards = self.db.campaign_rewards
        self.posts = self.db.campaign_posts
        self.deleted = self.db.campaign_deleted_messages
        self.users = self.db.users
        self.journal = self.db.transactions
        self.clock = clock or (lambda: datetime.now(UTC))
        self.channel_id = self.cfg.target_channel_id
        self.discussion_id = self.cfg.discussion_chat_id
        self.ready = False
        self.task = None
        self.bot = None
        self.bot_id = None
        self.enabled_at = None
        self.inbox = None

    def now(self):
        return utc(self.clock())

    async def transaction(self, callback):
        async with await self.db.client.start_session() as session:
            return await session.with_transaction(callback, read_concern=ReadConcern('snapshot'),
                                                  write_concern=WriteConcern('majority'))

    async def ensure_indexes(self):
        # Existing wallet, no parallel balance. Duplicate user IDs must be fixed
        # by an operator, never silently merged/deleted during a migration.
        await self.users.create_index('id', unique=True)
        await self.campaigns.create_index([('channel_id', 1), ('post_id', 1)], unique=True)
        await self.campaigns.create_index([('discussion_chat_id', 1), ('discussion_message_id', 1)], unique=True)
        await self.campaigns.create_index([('terminal', 1), ('status', 1), ('due_at', 1)])
        await self.campaigns.create_index([('discussion_chat_id', 1), ('discussion_media_group_id', 1)], unique=True,
            partialFilterExpression={'discussion_media_group_id': {'$type': 'string'}})
        await self.comments.create_index([('campaign_id', 1), ('message_id', 1)], unique=True)
        await self.comments.create_index([('campaign_id', 1), ('eligible', 1), ('user_id', 1)])
        await self.routes.create_index([('chat_id', 1), ('message_id', 1)], unique=True)
        await self.rewards.create_index([('status', 1), ('user_id', 1)])
        await self.rewards.create_index([('campaign_id', 1), ('status', 1)])
        await self.posts.create_index([('state', 1), ('check_at', 1)])

    async def initialize(self, bot):
        hello = await self.db.command('hello')
        if not hello.get('logicalSessionTimeoutMinutes') or not (hello.get('setName') or hello.get('msg') == 'isdbgrid'):
            raise RuntimeError('Comment campaigns require MongoDB replica set/mongos transactions')
        await self.ensure_indexes()
        pinned = await self.db.settings.find_one({'_id': 'comment_campaign_channel'}) or {}
        channel = await bot.get_chat(self.channel_id or pinned.get('channel_id') or '@SenseiDurova')
        if channel.type != 'channel':
            raise RuntimeError('Target is not a channel')
        discussion_id = self.discussion_id or pinned.get('discussion_id') or channel.linked_chat_id
        if not discussion_id or channel.linked_chat_id != discussion_id:
            raise RuntimeError('Configured discussion is not linked to target channel')
        discussion = await bot.get_chat(discussion_id)
        if discussion.type != 'supergroup' or (discussion.linked_chat_id and discussion.linked_chat_id != channel.id):
            raise RuntimeError('Discussion/channel link mismatch')
        me = await bot.get_me()
        for chat_id in (channel.id, discussion.id):
            member = await bot.get_chat_member(chat_id, me.id)
            if member.status not in {'administrator', 'creator'}:
                raise RuntimeError(f'Bot must be administrator in {chat_id}')
            if chat_id == channel.id and member.status != 'creator' and not member.can_post_messages:
                raise RuntimeError('Bot needs channel post permission')
        pinned = await self.db.settings.find_one_and_update({'_id': 'comment_campaign_channel'},
            {'$set': {'channel_id': channel.id, 'discussion_id': discussion.id},
             '$setOnInsert': {'enabled_at': self.now().replace(microsecond=0)}},
            upsert=True, return_document=ReturnDocument.AFTER)
        self.channel_id, self.discussion_id, self.bot_id = channel.id, discussion.id, me.id
        self.enabled_at = utc(pinned['enabled_at'])
        self.bot = bot
        self.inbox = CampaignInbox(self.cfg.campaign_inbox_path, me.id)
        await self.inbox.open()
        self.ready = True
        logger.info('Comment campaigns ready channel=%s discussion=%s', self.channel_id, self.discussion_id)

    async def start(self, bot):
        if not self.cfg.comment_campaigns_enabled or self.task:
            return
        try:
            await self.initialize(bot)
        except Exception:
            logger.exception('Comment campaigns DISABLED: startup validation failed')
            return
        self.task = asyncio.create_task(self.run(), name='comment-campaign-worker')

    async def stop(self):
        self.ready = False
        if self.task:
            self.task.cancel()
            with suppress(asyncio.CancelledError):
                await self.task
            self.task = None
        if self.inbox:
            await self.inbox.close()

    def campaign_id(self, post_id):
        return f'{self.channel_id}:{post_id}'

    async def observe_post(self, message):
        if message.chat.id != self.channel_id or utc(message.date) < self.enabled_at:
            return
        await self.posts.update_one({'_id': self.campaign_id(message.message_id)}, {'$setOnInsert': {
            'post_id': message.message_id, 'channel_id': self.channel_id, 'state': 'awaiting_discussion',
            'published_at': message.date, 'check_at': self.now()+timedelta(seconds=60)}}, upsert=True)

    async def observe_root(self, message):
        origin = message.forward_origin
        if (message.chat.id != self.discussion_id or not message.is_automatic_forward
                or not isinstance(origin, MessageOriginChannel) or origin.chat.id != self.channel_id
                or utc(origin.date) < self.enabled_at):
            return None
        cid = self.campaign_id(origin.message_id)
        end = utc(origin.date)+timedelta(hours=self.cfg.campaign_duration_hours)
        if end <= self.now():
            logger.warning('Discussion received after campaign window; no retroactive launch post=%s', cid)
            return None
        album = getattr(message, 'media_group_id', None)
        existing_album = await self.campaigns.find_one({'discussion_chat_id': self.discussion_id,
            'discussion_media_group_id': album}) if album else None
        if existing_album:
            cid = existing_album['_id']
        document = {
            'channel_id': self.channel_id, 'post_id': origin.message_id,
            'discussion_chat_id': self.discussion_id, 'discussion_message_id': message.message_id,
            'started_at': origin.date, 'deadline': end, 'status': 'active', 'phase': 'announcement',
            'due_at': self.now(), 'lease_until': self.now(), 'terminal': False,
            'sealed': False, 'comment_version': 0, 'plan_cursor': 0, 'payout_cursor': 0,
            'eligible_count': 0, 'winner': None, 'plan_complete': False,
            'start_message_id': None, 'final_message_id': None, 'payouts_done': False,
            'rules': dict(base=self.cfg.base_reward, winner=self.cfg.winner_reward,
                unique=self.cfg.reward_per_unique_user, winner_mode=self.cfg.winner_reward_mode,
                duration=self.cfg.campaign_duration_hours, grace=self.cfg.campaign_settlement_grace_seconds,
                content_types=[v.strip() for v in self.cfg.campaign_allowed_content_types.split(',')])}
        if album:
            document['discussion_media_group_id'] = album
        try:
            await self.campaigns.update_one({'_id': cid}, {'$setOnInsert': document}, upsert=True)
        except DuplicateKeyError:
            if not album:
                raise
            canonical = await self.campaigns.find_one({'discussion_chat_id': self.discussion_id, 'discussion_media_group_id': album})
            if not canonical:
                raise
            cid = canonical['_id']
        await self.routes.update_one({'_id': f'{self.discussion_id}:{message.message_id}'},
            {'$setOnInsert': dict(chat_id=self.discussion_id, message_id=message.message_id, campaign_id=cid)}, upsert=True)
        await self.posts.update_one({'_id': self.campaign_id(origin.message_id)}, {'$set': {
            'state': 'discussion_found', 'campaign_id': cid, 'channel_id': self.channel_id,
            'post_id': origin.message_id, 'published_at': origin.date}}, upsert=True)
        logger.info('Campaign observed post=%s root=%s deadline=%s', cid, message.message_id, end.isoformat())
        return cid

    async def collect(self, message):
        if message.chat.id != self.discussion_id or message.is_automatic_forward:
            return False
        candidates = []
        if message.message_thread_id:
            candidates.append(message.message_thread_id)
        if message.reply_to_message:
            candidates.append(message.reply_to_message.message_id)
        route = None
        for mid in candidates:
            route = await self.routes.find_one({'_id': f'{self.discussion_id}:{mid}'})
            if not route:
                # Metadata is authoritative even if the route-cache write failed
                # after Telegram accepted our announcement.
                for field in ('discussion_message_id', 'start_message_id'):
                    found = await self.campaigns.find_one({'discussion_chat_id': self.discussion_id, field: mid})
                    if found:
                        route = {'campaign_id': found['_id']}
                        break
            if route:
                break
        if not route:
            return False
        cid = route['campaign_id']
        # Persist ancestry even for bots/services: a later reply to such a
        # message can still be a valid human comment under the original post.
        await self.routes.update_one({'_id': f'{self.discussion_id}:{message.message_id}'},
            {'$setOnInsert': dict(chat_id=self.discussion_id, message_id=message.message_id, campaign_id=cid)}, upsert=True)
        user = message.from_user
        if (not user or user.is_bot or user.id <= 0 or user.id == self.bot_id or message.sender_chat
                or message.content_type not in USER_CONTENT_TYPES):
            return False

        async def insert(tx):
            campaign = await self.campaigns.find_one({'_id': cid}, session=tx)
            if (not campaign or campaign['sealed'] or campaign.get('terminal')
                    or not utc(campaign['started_at']) <= utc(message.date) < utc(campaign['deadline'])
                    or message.content_type not in campaign['rules']['content_types']):
                return False
            key = f'{cid}:{message.message_id}'
            if await self.comments.find_one({'_id': key}, session=tx):
                return False
            await self.comments.insert_one(dict(_id=key, campaign_id=cid, message_id=message.message_id,
                chat_id=self.discussion_id, user_id=user.id, date=message.date,
                first_name=user.first_name, last_name=user.last_name, username=user.username,
                content_type=message.content_type, eligible=None, deleted=bool(await self.deleted.find_one(
                    {'_id': f'{self.discussion_id}:{message.message_id}'}, session=tx))), session=tx)
            # A write fence serializes comment acceptance against sealing.
            await self.campaigns.update_one({'_id': cid}, {'$inc': {'comment_version': 1}}, session=tx)
            return True
        accepted = await self.transaction(insert)
        if accepted:
            logger.info('Comment collected campaign=%s comment=%s user=%s', cid, message.message_id, user.id)
            try:
                await self.container.user_service.get_or_create(user_id=user.id, username=user.username,
                    first_name=user.first_name, last_name=user.last_name, is_bot=False)
            except Exception:
                # Comment remains durable; a reward waits for registration if needed.
                logger.exception('Comment registration deferred user=%s campaign=%s', user.id, cid)
        return accepted

    async def capture(self, event):
        if not self.ready:
            return
        relevant = ((event.channel_post and event.channel_post.chat.id == self.channel_id)
                    or (event.message and event.message.chat.id == self.discussion_id))
        if relevant:
            # Commit locally before acknowledging the middleware; Mongo outages
            # do not discard updates already admitted to this durable queue.
            await self.inbox.put(event)

    async def drain_inbox(self):
        if not self.inbox:
            return False
        processed = False
        for update_id, payload in await self.inbox.batch(self.cfg.campaign_batch_size):
            await self.ingest(Update.model_validate_json(payload))
            await self.inbox.ack(update_id)
            processed = True
        for chat_id, mid in await self.inbox.deletion_batch(self.cfg.campaign_batch_size):
            await self.mark_deleted(chat_id, mid)
            await self.inbox.ack_deletion(chat_id, mid)
            processed = True
        return processed

    async def note_deleted(self, chat_id, mid):
        if self.ready and chat_id == self.discussion_id:
            await self.inbox.deleted(chat_id, mid)

    async def mark_deleted(self, chat_id, mid):
        async def mark(tx):
            await self.deleted.update_one({'_id': f'{chat_id}:{mid}'},
                {'$setOnInsert': {'deleted_at': self.now()}}, upsert=True, session=tx)
            route = await self.routes.find_one({'_id': f'{chat_id}:{mid}'}, session=tx)
            if not route:
                return
            camp = await self.campaigns.find_one({'_id': route['campaign_id']}, session=tx)
            if camp and not camp['sealed']:
                await self.comments.update_one({'campaign_id': camp['_id'], 'message_id': mid},
                    {'$set': {'deleted': True}}, session=tx)
                await self.campaigns.update_one({'_id': camp['_id']}, {'$inc': {'comment_version': 1}}, session=tx)
        await self.transaction(mark)

    async def ingest(self, event):
        if not self.ready:
            return
        if event.channel_post:
            await self.observe_post(event.channel_post)
        message = event.message
        if message and message.chat.id == self.discussion_id:
            if message.is_automatic_forward:
                await self.observe_root(message)
            else:
                await self.collect(message)

    async def claim_work(self):
        now = self.now()
        return await self.campaigns.find_one_and_update({
            'terminal': False, 'status': {'$in': ['active', 'processing', 'failed']}, 'due_at': {'$lte': now},
            'lease_until': {'$lte': now}}, {'$set': {'lease_owner': uuid.uuid4().hex,
                'lease_until': now+timedelta(seconds=self.cfg.campaign_lease_seconds)}},
            sort=[('due_at', ASCENDING)], return_document=ReturnDocument.AFTER)

    async def fence(self, cid, owner, tx=None):
        campaign = await self.campaigns.find_one({'_id': cid, 'lease_owner': owner,
            'lease_until': {'$gt': self.now()}}, session=tx)
        if not campaign:
            raise LeaseLost(cid)
        return campaign

    async def update_owned(self, campaign, values):
        result = await self.campaigns.update_one({'_id': campaign['_id'], 'lease_owner': campaign['lease_owner'],
            'lease_until': {'$gt': self.now()}}, {'$set': values})
        if result.matched_count != 1:
            raise LeaseLost(campaign['_id'])

    async def touch(self, campaign):
        await self.update_owned(campaign, {'lease_until': self.now()+timedelta(seconds=self.cfg.campaign_lease_seconds)})

    async def plan_batch(self, cid, owner):
        async def plan(tx):
            camp = await self.fence(cid, owner, tx)
            rows = await self.comments.find({'campaign_id': cid, 'message_id': {'$gt': camp['plan_cursor']}},
                session=tx).sort('message_id', 1).limit(self.cfg.campaign_batch_size).to_list(length=self.cfg.campaign_batch_size)
            count, winner, cursor = camp['eligible_count'], camp['winner'], camp['plan_cursor']
            for row in rows:
                profile = await self.users.find_one({'id': row['user_id']}, session=tx)
                eligible = not row.get('deleted', False) and not (profile or {}).get('is_banned', False)
                if eligible and camp['rules']['unique']:
                    eligible = not await self.comments.find_one({'campaign_id': cid,
                        'user_id': row['user_id'], 'eligible': True}, session=tx)
                await self.comments.update_one({'_id': row['_id']}, {'$set': {'eligible': eligible}}, session=tx)
                if eligible:
                    count += 1
                    if secrets.randbelow(count) == 0:
                        winner = dict(message_id=row['message_id'], user_id=row['user_id'], first_name=row['first_name'])
                cursor = row['message_id']
            complete = len(rows) < self.cfg.campaign_batch_size
            await self.campaigns.update_one({'_id': cid}, {'$set': dict(eligible_count=count,
                winner=winner, plan_cursor=cursor, plan_complete=complete,
                phase='payout' if complete else 'plan')}, session=tx)
            return complete
        done = await self.transaction(plan)
        if done:
            frozen = await self.campaigns.find_one({'_id': cid})
            logger.info('Winner fixed campaign=%s winner=%s eligible=%s', cid, frozen['winner'], frozen['eligible_count'])

    def reward_operations(self, camp, row):
        rules = camp['rules']
        winner = camp['winner'] and row['message_id'] == camp['winner']['message_id']
        if winner and rules['winner_mode'] == 'total':
            return [('winner_total', rules['winner'])]
        ops = [('base', rules['base'])]
        if winner:
            ops.append(('winner_bonus', rules['winner']))
        return ops

    async def credit(self, cid, owner, row, kind, amount):
        key = f'comment_campaign:{cid}:{row["message_id"]}:{kind}'

        async def apply(tx):
            camp = await self.fence(cid, owner, tx)
            if not camp['plan_complete']:
                raise RuntimeError('Winner must be fixed before any payouts')
            existing = await self.rewards.find_one({'_id': key}, session=tx)
            if existing and existing['status'] == 'paid':
                return
            profile = await self.users.find_one({'id': row['user_id']}, session=tx)
            status = 'pending_registration' if not profile else 'blocked_banned' if profile.get('is_banned') else 'paid'
            record = dict(campaign_id=cid, channel_id=camp['channel_id'], post_id=camp['post_id'],
                comment_id=row['message_id'], user_id=row['user_id'], kind=kind, amount=amount, status=status, next_check_at=self.now())
            await self.rewards.update_one({'_id': key}, {'$setOnInsert': record}, upsert=True, session=tx)
            if status == 'paid':
                await self.users.update_one({'id': row['user_id']}, {'$inc': {'coins': amount}}, session=tx)
                await self.journal.insert_one(dict(_id=key, user_id=row['user_id'],
                    tx_type='comment_campaign_reward', coins_change=amount, xp_change=0,
                    campaign_id=cid, comment_id=row['message_id'], reward_kind=kind, created_at=self.now()), session=tx)
                await self.rewards.update_one({'_id': key}, {'$set': {'status': 'paid', 'paid_at': self.now()}}, session=tx)
            # Fence also writes: a lease takeover must conflict with this commit.
            await self.campaigns.update_one({'_id': cid}, {'$inc': {'settlement_version': 1}}, session=tx)
        await self.transaction(apply)
        logger.info('Reward recorded campaign=%s comment=%s kind=%s amount=%s', cid, row['message_id'], kind, amount)

    async def payout_batch(self, campaign):
        cid, owner = campaign['_id'], campaign['lease_owner']
        camp = await self.fence(cid, owner)
        rows = await self.comments.find({'campaign_id': cid, 'eligible': True,
            'message_id': {'$gt': camp['payout_cursor']}}).sort('message_id', 1).limit(self.cfg.campaign_batch_size).to_list(length=self.cfg.campaign_batch_size)
        for row in rows:
            await self.touch(campaign)
            for kind, amount in self.reward_operations(camp, row):
                await self.credit(cid, owner, row, kind, amount)
            await self.update_owned(campaign, {'payout_cursor': row['message_id']})
        if len(rows) < self.cfg.campaign_batch_size:
            await self.update_owned(campaign, {'payouts_done': True, 'phase': 'final'})

    def start_text(self, campaign):
        rules = campaign['rules']
        unit = 'первый комментарий каждого участника' if rules['unique'] else 'каждый комментарий'
        mode = 'дополнительно получит' if rules['winner_mode'] == 'bonus' else 'получит'
        duration = f'{rules["duration"]:g}'
        return (f'🎉 Розыгрыш Coin начался!\n\nЗа {unit} под этим постом вы получите {rules["base"]} Coin.\n'
                f'Один случайный комментарий {mode} {rules["winner"]} Coin!\n\n'
                f'⏳ Итоги и начисление наград — через {duration} часа.')

    async def final_text(self, camp):
        rules = camp['rules']
        if not camp['eligible_count']:
            return EMPTY_TEXT.replace('4 часа', f'{rules["duration"]:g} часа')
        winner = camp['winner']
        mention = f'<a href="tg://user?id={winner["user_id"]}">{html.escape(winner["first_name"] or "Участник")}</a>'
        total = rules['winner'] + (rules['base'] if rules['winner_mode'] == 'bonus' else 0)
        text = (f'🏆 Розыгрыш завершён!\n\n💰 Награды по {rules["base"]} Coin начислены участникам.\n'
                f'🎊 Победитель случайного розыгрыша: {mention}\n💎 Награда победителя: {total} Coin.\n\nСпасибо за участие!')
        pending = await self.rewards.count_documents({'campaign_id': camp['_id'], 'status': 'pending_registration'})
        blocked = await self.rewards.count_documents({'campaign_id': camp['_id'], 'status': 'blocked_banned'})
        if pending:
            text = text.replace('начислены участникам.', 'начислены зарегистрированным участникам.')
            text += '\n\nНаграды незарегистрированных участников сохранены: откройте бота и нажмите /start.'
        if blocked:
            text += '\n\nНачисления заблокированным профилям приостановлены.'
        return text

    async def process(self, campaign):
        cid, owner = campaign['_id'], campaign['lease_owner']
        camp = await self.fence(cid, owner)
        if camp['phase'] == 'announcement':
            if utc(camp['deadline']) <= self.now():
                await self.update_owned(camp, {'status': 'failed', 'terminal': True,
                    'last_error': 'Announcement not delivered before deadline'})
                return
            sent = await asyncio.wait_for(self.bot.send_message(chat_id=camp['discussion_chat_id'],
                text=self.start_text(camp), parse_mode=None,
                reply_parameters=ReplyParameters(message_id=camp['discussion_message_id'], allow_sending_without_reply=False)), timeout=20)
            await self.update_owned(camp, {'start_message_id': sent.message_id, 'status': 'active', 'last_error': None,
                'phase': 'wait', 'due_at': utc(camp['deadline'])+timedelta(seconds=self.cfg.campaign_settlement_grace_seconds)})
            await self.routes.update_one({'_id': f'{camp["discussion_chat_id"]}:{sent.message_id}'},
                {'$setOnInsert': dict(chat_id=camp['discussion_chat_id'], message_id=sent.message_id, campaign_id=cid)}, upsert=True)
            logger.info('Campaign announced campaign=%s message=%s', cid, sent.message_id)
        elif camp['phase'] == 'wait':
            close_at = utc(camp['deadline'])+timedelta(seconds=camp['rules'].get('grace', 0))
            if self.now() < close_at:
                await self.update_owned(camp, {'due_at': close_at, 'status': 'active'})
                return
            if self.inbox and await self.inbox.pending():
                # Never close over comments still awaiting durable ingestion.
                await self.update_owned(camp, {'due_at': self.now()+timedelta(seconds=self.cfg.campaign_poll_seconds)})
                return
            async def seal(tx):
                await self.fence(cid, owner, tx)
                await self.campaigns.update_one({'_id': cid}, {'$set': {'sealed': True,
                    'status': 'processing', 'phase': 'plan'}}, session=tx)
            await self.transaction(seal)
        elif camp['phase'] == 'plan':
            await self.plan_batch(cid, owner)
        elif camp['phase'] == 'payout':
            await self.payout_batch(camp)
        elif camp['phase'] == 'final':
            if not camp['payouts_done']:
                raise RuntimeError('Final announcement before payout plan completed')
            text = await self.final_text(camp)
            sent = await asyncio.wait_for(self.bot.send_message(chat_id=camp['discussion_chat_id'], text=text,
                parse_mode='HTML', reply_parameters=ReplyParameters(message_id=camp['discussion_message_id'], allow_sending_without_reply=False)), timeout=20)
            await self.update_owned(camp, {'final_message_id': sent.message_id, 'status': 'completed',
                'terminal': True, 'completed_at': self.now(), 'last_error': None})
            logger.info('Campaign completed campaign=%s winner=%s', cid, camp['winner'])

    async def resume_pending_reward(self, record):
        async def release(tx):
            current = await self.rewards.find_one({'_id': record['_id']}, session=tx)
            if not current or current['status'] != 'pending_registration':
                return
            profile = await self.users.find_one({'id': current['user_id']}, session=tx)
            if not profile or profile.get('is_banned'):
                await self.rewards.update_one({'_id': current['_id']}, {'$set': {'next_check_at': self.now()+timedelta(seconds=self.cfg.campaign_retry_seconds)}}, session=tx)
                return
            await self.users.update_one({'id': current['user_id']}, {'$inc': {'coins': current['amount']}}, session=tx)
            await self.journal.insert_one(dict(_id=current['_id'], user_id=current['user_id'],
                tx_type='comment_campaign_reward', coins_change=current['amount'], xp_change=0,
                campaign_id=current['campaign_id'], comment_id=current['comment_id'],
                reward_kind=current['kind'], created_at=self.now()), session=tx)
            await self.rewards.update_one({'_id': current['_id']}, {'$set': {'status': 'paid', 'paid_at': self.now()}}, session=tx)
        await self.transaction(release)

    async def tick(self):
        ingested = await self.drain_inbox()
        camp = await self.claim_work()
        if camp:
            try:
                await self.process(camp)
                current = await self.fence(camp['_id'], camp['lease_owner'])
                due = current['due_at'] if current['phase'] == 'wait' else self.now()
                await self.update_owned(camp, {'lease_until': self.now(), 'due_at': due})
            except LeaseLost:
                logger.warning('Campaign lease lost campaign=%s', camp['_id'])
            except Exception as exc:
                logger.exception('Campaign work failed campaign=%s phase=%s', camp['_id'], camp['phase'])
                with suppress(LeaseLost):
                    await self.update_owned(camp, {'status': 'failed', 'last_error': type(exc).__name__,
                        'last_error_detail': getattr(exc, 'message', 'Infrastructure error; inspect application logs')[:500].replace(self.cfg.bot_token, '[REDACTED]'),
                        'lease_until': self.now(), 'due_at': self.now()+timedelta(seconds=self.cfg.campaign_retry_seconds)})
        pending = await self.rewards.find({'status': 'pending_registration', 'next_check_at': {'$lte': self.now()}}).limit(self.cfg.campaign_batch_size).to_list(length=self.cfg.campaign_batch_size)
        for record in pending:
            await self.resume_pending_reward(record)
        missing = await self.posts.find({'state': 'awaiting_discussion', 'check_at': {'$lte': self.now()}}).limit(self.cfg.campaign_batch_size).to_list(length=self.cfg.campaign_batch_size)
        for post in missing:
            logger.warning('No automatic discussion root observed; comments may be disabled post=%s', post['_id'])
            await self.posts.update_one({'_id': post['_id'], 'state': 'awaiting_discussion'}, {'$set': {'state': 'no_discussion_observed'}})
        return camp is not None or ingested

    async def run(self):
        # A startup drain window lets queued Telegram comments reach the DB.
        await asyncio.sleep(self.cfg.campaign_settlement_grace_seconds)
        while self.ready:
            try:
                worked = await self.tick()
            except Exception:
                logger.exception('Campaign scheduler iteration failed; will retry')
                worked = False
            await asyncio.sleep(.05 if worked else self.cfg.campaign_poll_seconds)
