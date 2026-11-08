"""Shared scenarios run against both rollback fake and actual Mongo replica set."""
import asyncio
import copy
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

from aiogram.types import Update
from pymongo.errors import DuplicateKeyError

from src.core.config import Settings
from src.services.comment_campaign_service import CommentCampaignService, START_TEXT
from src.services.user_service import UserService

UTC=timezone.utc


def matches(row, query):
    for key,value in query.items():
        if key=='$or':
            if not any(matches(row,q) for q in value): return False
            continue
        actual=row.get(key)
        if isinstance(value,dict):
            for op,want in value.items():
                if op=='$in' and actual not in want: return False
                if op=='$ne' and actual==want: return False
                if op in ('$gt','$gte','$lt','$lte'):
                    if actual is None: return False
                    if op=='$gt' and not actual>want: return False
                    if op=='$gte' and not actual>=want: return False
                    if op=='$lt' and not actual<want: return False
                    if op=='$lte' and not actual<=want: return False
        elif actual!=value: return False
    return True


class Cursor:
    def __init__(self,rows): self.rows=copy.deepcopy(rows)
    def sort(self,key,direction=1):
        for field,order in reversed(key if isinstance(key,list) else [(key,direction)]):
            self.rows.sort(key=lambda r:r.get(field),reverse=order==-1)
        return self
    def limit(self,n): self.rows=self.rows[:n];return self
    async def to_list(self,length=None): return self.rows if length is None else self.rows[:length]


class Collection:
    def __init__(self): self.docs={}
    async def create_index(self,*args,**kwargs): pass
    def find(self,query=None,**kwargs): return Cursor([r for r in self.docs.values() if matches(r,query or {})])
    async def find_one(self,query,**kwargs):
        rows=await self.find(query).to_list(length=1)
        return rows[0] if rows else None
    async def count_documents(self,query,**kwargs): return len(await self.find(query).to_list())
    async def insert_one(self,row,**kwargs):
        row=copy.deepcopy(row);row.setdefault('_id',uuid.uuid4().hex)
        if row['_id'] in self.docs: raise DuplicateKeyError('duplicate')
        self.docs[row['_id']]=row;return NS(inserted_id=row['_id'])
    async def find_one_and_update(self,query,updates,upsert=False,sort=None,**kwargs):
        rows=self.find(query)
        if sort: rows.sort(sort)
        found=await rows.to_list(length=1)
        if not found and not upsert: return None
        if found: row=self.docs[found[0]['_id']]
        else:
            row={k:v for k,v in query.items() if not k.startswith('$') and not isinstance(v,dict)}
            row.update(copy.deepcopy(updates.get('$setOnInsert',{})));row.setdefault('_id',uuid.uuid4().hex)
            if row['_id'] in self.docs: raise DuplicateKeyError('duplicate upsert')
            self.docs[row['_id']]=row
        row.update(copy.deepcopy(updates.get('$set',{})))
        for k,v in updates.get('$inc',{}).items(): row[k]=row.get(k,0)+v
        return copy.deepcopy(row)
    async def update_one(self,query,updates,**kwargs):
        row=await self.find_one_and_update(query,updates,**kwargs)
        return NS(matched_count=int(row is not None))
    async def delete_many(self,query):
        for key,row in list(self.docs.items()):
            if matches(row,query): del self.docs[key]


class Session:
    def __init__(self,db): self.db=db
    async def __aenter__(self): return self
    async def __aexit__(self,*args): pass
    async def with_transaction(self,callback,**kwargs):
        async with self.db.lock:
            backup={k:copy.deepcopy(v.docs) for k,v in self.db.collections.items()}
            try: return await callback(self)
            except Exception:
                for k,docs in backup.items(): self.db.collections[k].docs=docs
                for k in set(self.db.collections)-set(backup): self.db.collections[k].docs={}
                raise


class FakeDB:
    def __init__(self):
        self.collections={};self.lock=asyncio.Lock();self.client=NS(start_session=self.start_session)
    def __getattr__(self,key):
        if key.startswith('_'): raise AttributeError(key)
        return self.collections.setdefault(key,Collection())
    async def start_session(self): return Session(self)
    async def command(self,*args): return dict(setName='rs0',logicalSessionTimeoutMinutes=30)


class Harness:
    def __init__(self,db,tmp_path,**options):
        self.db=db
        self.clock=[datetime(2026,11,6,12,tzinfo=UTC)]
        self.cfg=Settings(_env_file=None,BOT_TOKEN='123456:TEST',COMMENT_CAMPAIGNS_ENABLED=True,
            TARGET_CHANNEL_ID=-100111,DISCUSSION_CHAT_ID=-100222,CAMPAIGN_INBOX_PATH=str(tmp_path/'inbox.sqlite3'),
            CAMPAIGN_BATCH_SIZE=2,CAMPAIGN_RETRY_SECONDS=1,CAMPAIGN_SETTLEMENT_GRACE_SECONDS=0,**options)
        self.container=NS(settings=self.cfg,mongo_client=NS(database=db),user_service=UserService(NS(database=db)))
        self.service=CommentCampaignService(self.container,clock=lambda:self.clock[0])
        self.counter=10000
        async def send(**kwargs):
            self.counter+=1;return NS(message_id=self.counter)
        async def chat(chat_id):
            if chat_id in (-100111,'@SenseiDurova'):
                return NS(id=-100111,type='channel',linked_chat_id=-100222)
            return NS(id=-100222,type='supergroup',linked_chat_id=-100111)
        self.bot=NS(send_message=AsyncMock(side_effect=send),get_chat=AsyncMock(side_effect=chat),
            get_me=AsyncMock(return_value=NS(id=999)),
            get_chat_member=AsyncMock(return_value=NS(status='administrator',can_post_messages=True)))
    async def open(self): await self.service.initialize(self.bot);return self
    async def close(self): await self.service.stop()
    async def profile(self,uid,banned=False):
        await self.db.users.insert_one(dict(id=uid,coins=0,xp=10,is_banned=banned))
    def root(self,post=1,root=100):
        return Update.model_validate(dict(update_id=root,message=dict(message_id=root,date=self.clock[0],
            chat=dict(id=-100222,type='supergroup'),is_automatic_forward=True,
            forward_origin=dict(type='channel',date=self.clock[0],chat=dict(id=-100111,type='channel'),message_id=post))))
    def comment(self,mid,uid=7,parent=100,thread=None,bot=False,date=None,service=False,sender=False):
        msg=dict(message_id=mid,date=date or self.clock[0]+timedelta(seconds=10),
            chat=dict(id=-100222,type='supergroup'),**{'from':dict(id=uid,is_bot=bot,first_name=f'User<{uid}>')},
            reply_to_message=dict(message_id=parent,date=self.clock[0],chat=dict(id=-100222,type='supergroup')))
        if service: msg['new_chat_title']='Service'
        else: msg['text']='hello'
        if thread: msg['message_thread_id']=thread
        if sender: msg['sender_chat']=dict(id=-100222,type='supergroup')
        return Update.model_validate(dict(update_id=mid,message=msg))
    async def begin(self,post=1,root=100):
        await self.service.ingest(self.root(post,root));await self.service.tick()
        return await self.db.comment_campaigns.find_one({'_id':f'-100111:{post}'})
    async def finish(self,post=1):
        self.clock[0]+=timedelta(hours=4,seconds=1)
        for _ in range(100):
            await self.service.tick()
            row=await self.db.comment_campaigns.find_one({'_id':f'-100111:{post}'})
            if row and row['status']=='completed': return row
        raise AssertionError('Campaign did not complete')
    async def wallet(self,uid): return (await self.db.users.find_one({'id':uid}))['coins']


class CampaignCases:
    async def test_new_post_starts_in_matching_discussion(self,campaign_env):
        env=campaign_env
        camp=await env.begin()
        assert camp['start_message_id'] and camp['status']=='active'
        assert env.bot.send_message.call_args.kwargs['text']==START_TEXT
        assert env.bot.send_message.call_args.kwargs['reply_parameters'].message_id==100
        assert (await env.db.comment_campaigns.count_documents({}))==1
        await env.service.ingest(env.root());assert (await env.db.comment_campaigns.count_documents({}))==1

    async def test_multiple_comments_and_one_winner_total(self,campaign_env):
        env=campaign_env
        await env.profile(7);await env.profile(8);await env.begin()
        for mid,uid in [(101,7),(102,8),(103,7)]: await env.service.ingest(env.comment(mid,uid))
        with patch('src.services.comment_campaign_service.secrets.randbelow',return_value=0):
            camp=await env.finish()
        assert camp['winner']['message_id']==103 and camp['eligible_count']==3
        assert await env.wallet(7)==2100 and await env.wallet(8)==100
        assert await env.db.transactions.count_documents({'tx_type':'comment_campaign_reward'})==3
        assert await env.db.campaign_rewards.count_documents({'kind':'winner_total'})==1
        assert 'User&lt;7&gt;' in env.bot.send_message.call_args.kwargs['text']
        assert (await env.db.users.find_one({'id':7}))['xp']==10

    async def test_unique_user_and_additive_bonus(self,campaign_env):
        env=campaign_env;env.cfg.reward_per_unique_user=True;env.cfg.winner_reward_mode='bonus'
        await env.profile(7);await env.profile(8);await env.begin()
        for mid,uid in [(101,7),(102,8),(103,7)]: await env.service.ingest(env.comment(mid,uid))
        with patch('src.services.comment_campaign_service.secrets.randbelow',return_value=0): camp=await env.finish()
        assert camp['eligible_count']==2 and camp['winner']['user_id']==8
        assert await env.wallet(7)==100 and await env.wallet(8)==2100

    async def test_bots_services_wrong_post_and_deadline_excluded(self,campaign_env):
        env=campaign_env;await env.profile(7);await env.begin()
        for event in [env.comment(101,999,bot=True),env.comment(102,8,bot=True),env.comment(103,7,service=True),
                      env.comment(104,7,parent=9999),env.comment(105,7,sender=True),
                      env.comment(106,7,date=env.clock[0]+timedelta(hours=4))]:
            await env.service.ingest(event)
        assert await env.db.campaign_comments.count_documents({})==0
        camp=await env.finish();assert camp['eligible_count']==0 and await env.wallet(7)==0
        assert 'Подходящих комментариев нет' in env.bot.send_message.call_args.kwargs['text']

    async def test_nested_replies_and_repeated_update(self,campaign_env):
        env=campaign_env;await env.profile(7);await env.begin()
        for event in [env.comment(101),env.comment(102,parent=101),env.comment(102,parent=101)]: await env.service.ingest(event)
        camp=await env.finish();assert camp['eligible_count']==2
        assert await env.wallet(7)==2100

    async def test_restart_and_multiple_posts(self,campaign_env):
        env=campaign_env;await env.profile(7);await env.profile(8)
        await env.begin(1,100);await env.begin(2,200)
        await env.service.ingest(env.comment(101,7,parent=100));await env.service.ingest(env.comment(201,8,parent=200))
        await env.service.stop()
        env.service=CommentCampaignService(env.container,clock=lambda:env.clock[0]);await env.service.initialize(env.bot)
        await env.finish(1)
        for _ in range(20): await env.service.tick()
        assert await env.wallet(7)==2000 and await env.wallet(8)==2000
        assert await env.db.comment_campaigns.count_documents({'status':'completed'})==2
        for _ in range(5): await env.service.tick()
        assert await env.wallet(7)==2000

    async def test_start_error_failed_and_retry(self,campaign_env):
        env=campaign_env;original=env.bot.send_message.side_effect
        env.bot.send_message.side_effect=RuntimeError('Telegram unavailable')
        camp=await env.begin();assert camp['status']=='failed' and camp['start_message_id'] is None
        env.bot.send_message.side_effect=original;env.clock[0]+=timedelta(seconds=2)
        await env.service.tick()
        assert (await env.db.comment_campaigns.find_one({'_id':camp['_id']}))['start_message_id']

    async def test_final_send_failure_does_not_repay(self,campaign_env):
        env=campaign_env;await env.profile(7);await env.begin();await env.service.ingest(env.comment(101))
        env.clock[0]+=timedelta(hours=4,seconds=1)
        for _ in range(20):
            camp=await env.db.comment_campaigns.find_one({'_id':'-100111:1'})
            if camp['phase']=='final': break
            await env.service.tick()
        assert await env.wallet(7)==2000
        original=env.bot.send_message.side_effect;env.bot.send_message.side_effect=RuntimeError('API')
        await env.service.tick();assert await env.wallet(7)==2000
        env.bot.send_message.side_effect=original;env.clock[0]+=timedelta(seconds=2)
        await env.service.tick();assert await env.wallet(7)==2000
        assert (await env.db.comment_campaigns.find_one({'_id':'-100111:1'}))['status']=='completed'

    async def test_no_discussion_no_campaign(self,campaign_env):
        env=campaign_env
        post=Update.model_validate(dict(update_id=1,channel_post=dict(message_id=1,date=env.clock[0],chat=dict(id=-100111,type='channel'),text='post')))
        await env.service.ingest(post);env.clock[0]+=timedelta(seconds=61);await env.service.tick()
        assert await env.db.comment_campaigns.count_documents({})==0
        assert (await env.db.campaign_posts.find_one({'_id':'-100111:1'}))['state']=='no_discussion_observed'

    async def test_fenced_worker_and_persisted_winner(self,campaign_env):
        from src.services.comment_campaign_service import LeaseLost
        env=campaign_env;await env.profile(7);await env.begin();await env.service.ingest(env.comment(101))
        env.clock[0]+=timedelta(hours=4,seconds=1)
        owner=await env.service.claim_work()
        assert await env.service.claim_work() is None
        env.clock[0]+=timedelta(seconds=env.cfg.campaign_lease_seconds+1)
        new=await env.service.claim_work();assert new['lease_owner']!=owner['lease_owner']
        try: await env.service.process(owner)
        except LeaseLost: pass
        else: raise AssertionError('Stale worker must be fenced')
        await env.service.process(new)
        await env.service.update_owned(new,{'lease_until':env.clock[0],'due_at':env.clock[0]})
        await env.finish();assert await env.wallet(7)==2000

    async def test_database_error_rolls_back_payout_and_preserves_winner(self,campaign_env):
        env=campaign_env;await env.profile(7);await env.begin();await env.service.ingest(env.comment(101))
        env.clock[0]+=timedelta(hours=4,seconds=1)
        for _ in range(20):
            camp=await env.db.comment_campaigns.find_one({'_id':'-100111:1'})
            if camp['phase']=='payout': break
            await env.service.tick()
        winner=camp['winner']
        with patch.object(env.service.journal,'insert_one',side_effect=RuntimeError('DB write failed')):
            await env.service.tick()
        assert await env.wallet(7)==0
        assert await env.db.campaign_rewards.count_documents({})==0
        assert (await env.db.comment_campaigns.find_one({'_id':camp['_id']}))['winner']==winner
        env.clock[0]+=timedelta(seconds=2)
        await env.finish();assert await env.wallet(7)==2000

    async def test_pending_registration_paid_later_once(self,campaign_env):
        env=campaign_env;await env.begin()
        with patch.object(env.container.user_service,'get_or_create',side_effect=RuntimeError('registration unavailable')):
            await env.service.ingest(env.comment(101,77))
        await env.finish()
        assert await env.db.users.find_one({'id':77}) is None
        assert await env.db.campaign_rewards.count_documents({'status':'pending_registration'})==1
        await env.profile(77);env.clock[0]+=timedelta(seconds=2)
        await env.service.tick();await env.service.tick()
        assert await env.wallet(77)==2000
        assert await env.db.transactions.count_documents({'user_id':77})==1

    async def test_durable_ingress_replayed_after_restart_and_db_failure(self,campaign_env):
        env=campaign_env;await env.profile(7)
        await env.service.capture(env.root());await env.service.capture(env.comment(101))
        with patch.object(env.service,'ingest',side_effect=RuntimeError('Mongo offline')):
            try: await env.service.tick()
            except RuntimeError: pass
            else: raise AssertionError('Failure must leave queue unacknowledged')
        assert await env.service.inbox.pending()
        await env.service.stop()
        env.service=CommentCampaignService(env.container,clock=lambda:env.clock[0]);await env.service.initialize(env.bot)
        for _ in range(3): await env.service.tick()
        assert not await env.service.inbox.pending()
        await env.finish();assert await env.wallet(7)==2000

    async def test_no_launch_for_manual_forward_and_wrong_channel(self,campaign_env):
        env=campaign_env
        raw=env.root().model_dump(mode='json')
        raw['message']['is_automatic_forward']=False
        await env.service.ingest(Update.model_validate(raw))
        raw['message']['is_automatic_forward']=True
        raw['message']['forward_origin']['chat']['id']=-100333
        await env.service.ingest(Update.model_validate(raw))
        assert await env.db.comment_campaigns.count_documents({})==0

    async def test_configuration_and_winner_snapshot_do_not_change_on_retry(self,campaign_env):
        env=campaign_env;await env.profile(7);await env.begin();await env.service.ingest(env.comment(101))
        env.cfg.winner_reward=9999;env.cfg.base_reward=333;env.cfg.winner_reward_mode='bonus'
        camp=await env.finish()
        assert camp['rules']['winner']==2000
        assert await env.wallet(7)==2000

    async def test_known_bot_deletion_is_excluded_before_draw(self,campaign_env):
        env=campaign_env;await env.profile(7);await env.begin()
        await env.service.capture(env.comment(101))
        await env.service.note_deleted(-100222,101)
        await env.service.tick()
        camp=await env.finish()
        assert camp['eligible_count']==0 and await env.wallet(7)==0

    async def test_album_roots_share_one_campaign(self,campaign_env):
        env=campaign_env;await env.profile(7)
        for post,root in [(1,100),(2,101)]:
            event=env.root(post,root).model_dump(mode='json');event['message']['media_group_id']='album1'
            await env.service.ingest(Update.model_validate(event))
        await env.service.tick()
        assert await env.db.comment_campaigns.count_documents({})==1
        await env.service.ingest(env.comment(102,parent=101))
        await env.finish();assert await env.wallet(7)==2000

    async def test_two_workers_do_not_settle_campaign_twice(self,campaign_env):
        env=campaign_env;await env.profile(7);await env.begin();await env.service.ingest(env.comment(101))
        other=CommentCampaignService(env.container,clock=lambda:env.clock[0]);await other.initialize(env.bot)
        env.clock[0]+=timedelta(hours=4,seconds=1)
        try:
            for _ in range(20): await asyncio.gather(env.service.tick(),other.tick())
            assert await env.wallet(7)==2000
            assert await env.db.transactions.count_documents({'tx_type':'comment_campaign_reward'})==1
        finally: await other.stop()

    async def test_retry_cannot_shorten_deadline_after_partial_start_metadata(self,campaign_env):
        env=campaign_env;await env.profile(7);await env.begin();await env.service.ingest(env.comment(101))
        await env.db.comment_campaigns.update_one({'_id':'-100111:1'},
            {'$set':{'status':'failed','due_at':env.clock[0]}})
        await env.service.tick()
        row=await env.db.comment_campaigns.find_one({'_id':'-100111:1'})
        assert row['phase']=='wait' and not row['sealed'] and await env.wallet(7)==0
        await env.finish();assert await env.wallet(7)==2000

    async def test_missing_route_cache_uses_persisted_announcement_id(self,campaign_env):
        env=campaign_env;await env.profile(7);camp=await env.begin()
        await env.db.campaign_message_routes.delete_many({})
        await env.service.ingest(env.comment(101,parent=camp['start_message_id']))
        await env.finish();assert await env.wallet(7)==2000

    async def test_partial_payout_resume_preserves_winner_and_money(self,campaign_env):
        env=campaign_env;await env.profile(7)
        env.cfg.campaign_batch_size=1;env.cfg.winner_reward_mode='bonus'
        await env.begin();await env.service.ingest(env.comment(101));await env.service.ingest(env.comment(102))
        env.clock[0]+=timedelta(hours=4,seconds=1)
        for _ in range(30):
            await env.service.tick()
            camp=await env.db.comment_campaigns.find_one({'_id':'-100111:1'})
            if camp['payout_cursor']==101: break
        assert camp['payout_cursor']==101
        winner=camp['winner'];assert await env.wallet(7) in (100,2100)
        await env.service.stop()
        env.service=CommentCampaignService(env.container,clock=lambda:env.clock[0]);await env.service.initialize(env.bot)
        completed=await env.finish()
        assert completed['winner']==winner and await env.wallet(7)==2200
        assert await env.db.transactions.count_documents({'tx_type':'comment_campaign_reward'})==3

    async def test_known_deletion_before_comment_ingestion_is_tombstoned(self,campaign_env):
        env=campaign_env;await env.profile(7);await env.begin()
        await env.service.note_deleted(-100222,101)
        assert await env.service.inbox.pending()
        await env.service.tick();assert not await env.service.inbox.pending()
        await env.service.ingest(env.comment(101))
        camp=await env.finish();assert camp['eligible_count']==0 and await env.wallet(7)==0

    async def test_late_album_alias_restores_existing_campaign(self,campaign_env):
        env=campaign_env;await env.profile(7)
        original=env.clock[0]
        root=env.root().model_dump(mode='json');root['message']['media_group_id']='late-album'
        await env.service.ingest(Update.model_validate(root));await env.service.tick()
        env.clock[0]+=timedelta(hours=4,seconds=1)
        alias=env.root(2,101).model_dump(mode='json')
        alias['message']['media_group_id']='late-album'
        alias['message']['forward_origin']['date']=int(original.timestamp())
        await env.service.ingest(Update.model_validate(alias))
        await env.service.ingest(env.comment(102,parent=101,date=original+timedelta(minutes=1)))
        camp=await env.finish()
        assert camp['eligible_count']==1 and await env.wallet(7)==2000
        assert await env.db.comment_campaigns.count_documents({})==1

    async def test_distinct_inbox_disables_second_worker(self,campaign_env,tmp_path):
        env=campaign_env
        import pytest
        from src.services.comment_campaign_service import InboxMismatch
        other=CommentCampaignService(env.container,clock=lambda:env.clock[0])
        env.cfg.campaign_inbox_path=str(tmp_path/'different.sqlite3')
        try:
            with pytest.raises(InboxMismatch):
                await other.start(env.bot)
            assert not other.ready and other.task is None
            assert env.service.ready
        finally:
            await other.stop()

    async def test_capture_cannot_commit_between_empty_check_and_seal(self,campaign_env):
        env=campaign_env;await env.begin()
        env.clock[0]+=timedelta(hours=4,seconds=1)
        reached=asyncio.Event();release=asyncio.Event()
        original=env.service.transaction
        async def paused(callback):
            reached.set();await release.wait()
            return await original(callback)
        with patch.object(env.service,'transaction',side_effect=paused):
            closing=asyncio.create_task(env.service.tick())
            await asyncio.wait_for(reached.wait(),5)
            entering=asyncio.create_task(env.service.capture(env.comment(101,date=env.clock[0]-timedelta(hours=1))))
            try:
                await asyncio.sleep(.05)
                assert not entering.done(), 'Admission must wait for settlement barrier'
            finally:
                release.set()
                await asyncio.wait_for(closing,5)
                await asyncio.wait_for(entering,5)
        assert (await env.db.comment_campaigns.find_one({'_id':'-100111:1'}))['sealed']
        # Updates admitted after the cutoff do not retroactively change a draw.
        assert await env.service.inbox.pending()
