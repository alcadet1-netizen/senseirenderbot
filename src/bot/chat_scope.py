"""Pin gameplay to the verified public group; leave DMs and subscription reads alone."""
import logging

from aiogram import BaseMiddleware
from aiogram.types import Update

logger = logging.getLogger(__name__)
TARGET_USERNAME = 'airchatton'


async def resolve_game_chat(bot, settings):
    # Never trust arbitrary MAIN_CHAT_ID or an unverified username in an update.
    chat = await bot.get_chat('@' + TARGET_USERNAME)
    if chat.type not in ('group', 'supergroup') or chat.id >= 0:
        raise RuntimeError('@airchatton must resolve to a group or supergroup')
    if settings.main_chat_id and settings.main_chat_id != chat.id:
        raise RuntimeError('MAIN_CHAT_ID does not match @airchatton; fix configuration')
    settings.main_chat_id = chat.id
    if settings.comment_campaigns_enabled and settings.discussion_chat_id and settings.discussion_chat_id != chat.id:
        logger.warning('Comment campaigns disabled: discussion is not @airchatton')
        settings.comment_campaigns_enabled = False
    # Other features that use ALLOWED_CHATS (e.g. boss editor) must not target old groups.
    settings.allowed_chats_str = str(chat.id)
    bot.game_chat_id = chat.id
    logger.info('Gameplay pinned to @%s chat=%s', TARGET_USERNAME, chat.id)
    return chat.id


def allowed_chat(chat, game_chat_id):
    return bool(chat and (chat.type == 'private' or
                          (chat.type in ('group', 'supergroup') and chat.id == game_chat_id)))


class GameChatScopeMiddleware(BaseMiddleware):
    def __init__(self, container):
        self.container = container

    async def __call__(self, handler, event, data):
        if not isinstance(event, Update):
            return await handler(event, data)
        # Inline queries have no destination chat ID. Accepting them would let
        # games and checks be placed in arbitrary groups or channels.
        if event.inline_query or event.chosen_inline_result:
            return None
        callback = event.callback_query
        if callback:
            if not callback.message or not allowed_chat(callback.message.chat, self.container.settings.main_chat_id):
                return None
        for name in ('message', 'edited_message', 'channel_post', 'edited_channel_post',
                     'chat_member', 'chat_join_request', 'message_reaction', 'message_reaction_count'):
            item = getattr(event, name, None)
            if item and not allowed_chat(item.chat, self.container.settings.main_chat_id):
                return None
        # Future widget queries can contain a chat or an unidentifiable inline
        # message. Fail closed for those without a verifiable destination.
        fields = event.model_dump(mode='python', by_alias=True, exclude_none=True)
        for name in ('widget_query', 'shared_widget_query'):
            query = fields.get(name)
            if isinstance(query, dict):
                chat = query.get('chat') or {}
                if not (chat.get('type') == 'private' or
                        (chat.get('type') in ('group', 'supergroup') and
                         chat.get('id') == self.container.settings.main_chat_id)):
                    return None
        return await handler(event, data)
