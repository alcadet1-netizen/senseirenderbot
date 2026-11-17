import ast
import re
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

import pytest
from aiogram.types import Message
from src.bot.admin_help import admin_help_pages


def test_pages_complete_and_telegram_safe():
    pages = admin_help_pages()
    assert len(pages) > 1
    assert all(len(p.encode('utf-16-le'))//2 < 4096 for p in pages)
    assert all('<pre>' not in p for p in pages)
    text='\n'.join(pages)
    documented=set(re.findall(r'/([\w]+)',text))
    # Every registered command/alias in these administrative modules is listed.
    root=Path(__file__).resolve().parents[2]/'src/bot/handlers'
    for name in ['admin_commands.py','dojo_tasks_admin.py','boss_admin.py','boss_commands.py','maintenance.py','chat_settings.py','zov.py','quiz.py','digest.py','sensei_check/admin.py']:
        tree=ast.parse((root/name).read_text())
        for node in ast.walk(tree):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='Command':
                for arg in node.args:
                    if isinstance(arg,ast.Constant) and isinstance(arg.value,str):
                        assert arg.value in documented, (name,arg.value)
    assert '+fire' in text and '/+fire' not in text
    assert '/boss_reset_pool' in text and '/senseifly on|off|status' in text
    assert '/senseihelp' in text and '/topticket' in text


@pytest.mark.asyncio
@pytest.mark.parametrize('command',['/adminhelp','/senseiadmin','/adminhelp@Senseigame_bot'])
@pytest.mark.parametrize('allowed',[True,False])
async def test_admin_help_router_access_and_delivery(command,allowed):
    from src.bot.handlers.admin_commands import router
    bot=AsyncMock()
    bot.me.return_value=NS(username='Senseigame_bot')
    msg=Message.model_validate(dict(message_id=1,date=1,chat=dict(id=7,type='private'),
        **{'from':dict(id=7,is_bot=False,first_name='<unsafe>')},text=command)).as_(bot)
    with patch('src.bot.filters.admin.settings',NS(admin_ids=[7] if allowed else [],admin_ids_str='')):
        await router.propagate_event('message',msg,bot=bot)
    if allowed:
        assert bot.await_count==len(admin_help_pages())
        assert [call.args[0].text for call in bot.call_args_list]==admin_help_pages()
        assert all(call.args[0].parse_mode is None for call in bot.call_args_list)
    else:
        bot.assert_not_awaited()


@pytest.mark.asyncio
async def test_senseihelp_gives_admin_the_full_catalogue():
    from src.bot.handlers.user_commands import cmd_help
    bot = AsyncMock()
    msg = Message.model_validate(dict(
        message_id=1, date=1, chat=dict(id=7, type='private'),
        **{'from': dict(id=7, is_bot=False, first_name='Admin')},
        text='/senseihelp')).as_(bot)
    with patch('src.bot.handlers.user_commands.settings',
               NS(admin_ids=[7], admin_ids_str='7')):
        await cmd_help(msg)
    pages = admin_help_pages()
    assert bot.await_count == len(pages)
    assert [call.args[0].text for call in bot.call_args_list] == pages
    assert all(call.args[0].parse_mode is None for call in bot.call_args_list)


@pytest.mark.asyncio
async def test_senseihelp_stays_private_for_non_admin_in_private_chat():
    from src.bot.handlers.user_commands import cmd_help
    bot = AsyncMock()
    msg = Message.model_validate(dict(
        message_id=1, date=1, chat=dict(id=7, type='private'),
        **{'from': dict(id=7, is_bot=False, first_name='User')},
        text='/senseihelp')).as_(bot)
    with patch('src.bot.handlers.user_commands.settings',
               NS(admin_ids=[], admin_ids_str='')):
        await cmd_help(msg)
    assert bot.await_count == 1
    assert 'только в групповых чатах' in bot.call_args.args[0].text
