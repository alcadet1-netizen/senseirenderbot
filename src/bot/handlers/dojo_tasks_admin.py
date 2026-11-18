"""Admin commands for /dojo channel and app-link tasks."""
import html
from urllib.parse import urlsplit

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from src.bot.filters import AdminFilter
from src.core.container import Container
from src.services.dojo_daily_service import DojoDailyService
from src.services.hedgehog_service import GameError
from src.services.dojo_task_service import (
    DEFAULT_ENERGY,
    DEFAULT_REWARD,
    MAX_ENERGY,
    MAX_REWARD,
    channel_link_username,
    normalize_link_url,
    normalize_username,
)

router = Router(name='dojo_tasks_admin')
router.message.filter(AdminFilter())

USAGE_ADD = (
    'Использование: <code>/task_add @channel [coin] [energy%]</code>\n'
    'Или ссылка: <code>/task_link URL [coin] [energy%] [название]</code>\n'
    f'По умолчанию: {DEFAULT_REWARD} Coin и +{DEFAULT_ENERGY}% энергии.'
)
USAGE_LINK = (
    'Использование: <code>/task_link URL [coin] [energy%] [название]</code>\n'
    'URL — HTTPS-ссылка на приложение, бота или реферальную страницу.\n'
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


def looks_like_link(value: str) -> bool:
    raw = (value or '').strip().lower()
    return raw.startswith(('https://', 'http://', 't.me/', 'telegram.me/',
                           'www.'))


def parse_link_args(text: str) -> tuple[str, int, int, str]:
    """Parse /task_link URL [coin] [energy] [title with spaces]."""
    parts = (text or '').split()
    if len(parts) < 2:
        raise ValueError('url')
    url = normalize_link_url(parts[1])
    if not url:
        raise ValueError('url')
    reward = DEFAULT_REWARD
    energy = DEFAULT_ENERGY
    index = 2
    try:
        if index < len(parts) and parts[index].lstrip('-').isdigit():
            reward = int(parts[index])
            index += 1
            if index < len(parts) and parts[index].lstrip('-').isdigit():
                energy = int(parts[index])
                index += 1
    except ValueError as exc:
        raise ValueError('numbers') from exc
    if not 0 <= reward <= MAX_REWARD or not 0 <= energy <= MAX_ENERGY:
        raise ValueError('numbers')
    title = ' '.join(parts[index:]).strip()[:120]
    if not title:
        title = (urlsplit(url).hostname or 'Приложение').lower()
    return url, reward, energy, title


async def _add_link_task(message: Message, container: Container) -> None:
    try:
        url, reward, energy, title = parse_link_args(message.text or '')
    except ValueError as exc:
        if str(exc) == 'numbers':
            await message.answer(
                f'Награда: 0…{format_number(MAX_REWARD)} Coin. '
                f'Энергия: 0…{format_number(MAX_ENERGY)}%.', parse_mode='HTML')
        else:
            await message.answer(USAGE_LINK, parse_mode='HTML')
        return
    task = await container.dojo_task_service.add_link(
        url=url,
        title=title,
        reward_coins=reward,
        energy_bonus=energy,
        created_by=message.from_user.id,
    )
    host = task.get('host') or urlsplit(task.get('url', '')).hostname or ''
    await message.answer(
        '✅ <b>Задание-ссылка добавлено</b>\n\n'
        f'Приложение: <b>{html.escape(task["title"])}</b> · '
        f'<a href="{html.escape(task["url"], quote=True)}">'
        f'{html.escape(str(host))}</a>\n'
        f'Награда: <b>{format_number(task["reward_coins"])} SenseiCoin</b>\n'
        f'Энергия: <b>+{task["energy_bonus"]}%</b>\n'
        'Кнопка игрока: <b>Запустить</b>',
        parse_mode='HTML',
        disable_web_page_preview=True,
    )


@router.message(Command('task_link', 'задание_ссылка', 'app_link'))
async def cmd_task_link(message: Message, container: Container) -> None:
    await _add_link_task(message, container)


@router.message(Command('task_add', 'задание_добавить'))
async def cmd_task_add(message: Message, container: Container) -> None:
    parts = (message.text or '').split()
    if len(parts) > 1 and looks_like_link(parts[1]) and not channel_link_username(parts[1]):
        await _add_link_task(message, container)
        return
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
    lines = ['📋 <b>Задания /dojo</b>', '']
    for task in tasks:
        mark = '🟢' if task['active'] else '⚪️'
        kind = task.get('kind') or 'channel'
        if kind == 'link':
            label = (f'🔗 <b>{html.escape(task["title"])}</b> · '
                     f'{html.escape(str(task.get("host") or ""))}')
        else:
            label = f'📣 <b>@{task["username"]}</b>'
        lines.append(
            f'{mark} {label} · '
            f'{format_number(task["reward_coins"])} Coin · '
            f'+{task["energy_bonus"]}% энергии'
        )
    lines.append('')
    lines.append('Канал: <code>/task_add @channel [coin] [energy%]</code>')
    lines.append('Ссылка: <code>/task_link URL [coin] [energy%] [название]</code>')
    lines.append('Убрать: <code>/task_remove @channel</code> или <code>/task_remove URL</code>')
    await message.answer('\n'.join(lines), parse_mode='HTML', disable_web_page_preview=True)


@router.message(Command('task_remove', 'задание_убрать'))
async def cmd_task_remove(message: Message, container: Container) -> None:
    parts = (message.text or '').split()
    value = parts[1] if len(parts) > 1 else ''
    if not value:
        await message.answer(
            'Использование: <code>/task_remove @channel</code> или '
            '<code>/task_remove URL</code>', parse_mode='HTML')
        return
    if not await container.dojo_task_service.remove_task(value):
        await message.answer(f'Задание {value} не найдено.')
        return
    await message.answer(f'⚪️ Задание {value} отключено.')


@router.message(Command('addchance'))
async def cmd_addchance(message: Message, container: Container) -> None:
    """Admin-only: durable and idempotent chest credit by registered username."""
    parts = (message.text or '').split()
    if (len(parts) != 3 or not parts[1].startswith('@') or
            not parts[2].isascii() or not parts[2].isdigit() or len(parts[2]) > 5):
        await message.answer('Использование: /addchance @username количество (1–10000).', parse_mode=None)
        return
    try:
        receipt = await DojoDailyService(container.mongo_client).grant_admin_chests(
            parts[1][1:], int(parts[2]), message.from_user.id,
            f'{message.chat.id}:{message.message_id}')
    except GameError as exc:
        await message.answer(str(exc), parse_mode=None)
        return
    except Exception:
        # Never acknowledge an uncertain write as a success. A retry of the
        # same Telegram update uses the same durable idempotency key.
        import logging
        logging.getLogger(__name__).exception('Dojo chest grant failed')
        await message.answer('Не удалось подтвердить выдачу. Проверь журнал перед повтором.', parse_mode=None)
        return
    await message.answer(
        f'✅ Выдано {receipt["amount"]} сундуков игроку @{receipt["username"]}. '
        'Они появятся в разделе CHANCE.', parse_mode=None)
