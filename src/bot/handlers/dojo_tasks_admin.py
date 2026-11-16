"""Admin commands for /dojo subscription tasks."""
import html

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from src.bot.filters import AdminFilter
from src.core.container import Container
from src.services.dojo_task_service import (
    DEFAULT_ENERGY,
    DEFAULT_REWARD,
    MAX_ENERGY,
    MAX_REWARD,
    normalize_username,
)

router = Router(name='dojo_tasks_admin')
router.message.filter(AdminFilter())

USAGE_ADD = (
    'Использование: <code>/task_add @channel [coin] [energy%]</code>\n'
    f'По умолчанию: {DEFAULT_REWARD} Coin и +{DEFAULT_ENERGY}% энергии.'
)


def format_number(value: int) -> str:
    return f'{int(value):,}'.replace(',', ' ')


def parse_add_args(text: str) -> tuple[str, int, int]:
    parts = (text or '').split()
    if len(parts) < 2:
        raise ValueError('channel')
    username = normalize_username(parts[1])
    if not username:
        raise ValueError('channel')
    try:
        reward = int(parts[2]) if len(parts) >= 3 else DEFAULT_REWARD
        energy = int(parts[3]) if len(parts) >= 4 else DEFAULT_ENERGY
    except ValueError as exc:
        raise ValueError('numbers') from exc
    if not 0 <= reward <= MAX_REWARD or not 0 <= energy <= MAX_ENERGY:
        raise ValueError('numbers')
    return username, reward, energy


@router.message(Command('task_add', 'задание_добавить'))
async def cmd_task_add(message: Message, container: Container) -> None:
    try:
        username, reward, energy = parse_add_args(message.text or '')
    except ValueError as exc:
        if str(exc) == 'numbers':
            await message.answer(
                f'Награда: 0…{format_number(MAX_REWARD)} Coin. '
                f'Энергия: 0…{format_number(MAX_ENERGY)}%.', parse_mode='HTML')
        else:
            await message.answer(USAGE_ADD, parse_mode='HTML')
        return
    try:
        chat = await message.bot.get_chat(f'@{username}')
        member = await message.bot.get_chat_member(chat.id, message.bot.id)
    except Exception:
        await message.answer(
            'Не вижу этот канал. Добавь бота администратором канала и повтори.',
            parse_mode='HTML')
        return
    if chat.type not in ('channel', 'supergroup'):
        await message.answer('Задание можно привязать только к каналу или супергруппе.')
        return
    if member.status not in ('creator', 'administrator'):
        await message.answer(
            'Бот должен быть администратором канала, иначе подписку не проверить.',
            parse_mode='HTML')
        return
    task = await container.dojo_task_service.add_task(
        username=username,
        title=chat.title or username,
        channel_id=chat.id,
        reward_coins=reward,
        energy_bonus=energy,
        created_by=message.from_user.id,
    )
    await message.answer(
        '✅ <b>Задание добавлено</b>\n\n'
        f'Канал: <b>{html.escape(task["title"])}</b> · @{task["username"]}\n'
        f'Награда: <b>{format_number(task["reward_coins"])} SenseiCoin</b>\n'
        f'Энергия: <b>+{task["energy_bonus"]}%</b>\n\n'
        f'Открыть: {task["url"]}',
        parse_mode='HTML',
    )


@router.message(Command('task_list', 'задания'))
async def cmd_task_list(message: Message, container: Container) -> None:
    tasks = await container.dojo_task_service.all_tasks()
    if not tasks:
        await message.answer('Заданий пока нет.')
        return
    lines = ['📋 <b>Задания подписки</b>', '']
    for task in tasks:
        mark = '🟢' if task['active'] else '⚪️'
        lines.append(
            f'{mark} <b>@{task["username"]}</b> · '
            f'{format_number(task["reward_coins"])} Coin · '
            f'+{task["energy_bonus"]}% энергии'
        )
    lines.append('')
    lines.append('Добавить: <code>/task_add @channel</code>')
    lines.append('Убрать: <code>/task_remove @channel</code>')
    await message.answer('\n'.join(lines), parse_mode='HTML', disable_web_page_preview=True)


@router.message(Command('task_remove', 'задание_убрать'))
async def cmd_task_remove(message: Message, container: Container) -> None:
    parts = (message.text or '').split()
    username = normalize_username(parts[1]) if len(parts) > 1 else ''
    if not username:
        await message.answer(
            'Использование: <code>/task_remove @channel</code>', parse_mode='HTML')
        return
    if not await container.dojo_task_service.remove_task(username):
        await message.answer(f'Задание для @{username} не найдено.')
        return
    await message.answer(f'⚪️ Задание для @{username} отключено.')
