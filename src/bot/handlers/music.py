""" 
🎧 Обработчик поиска музыки. 
Полностью автономный модуль - просто скопируй и используй. 

Зависимости (pip install): 
- aiogram>=3.0 
- yt-dlp 
- aiohttp 

Системные зависимости: 
- ffmpeg (apt install ffmpeg / brew install ffmpeg) 
""" 

import os 
import re 
import glob 
import shutil 
import logging 
import asyncio 
import tempfile 
from typing import Dict, Optional, List 
from pathlib import Path 

from aiogram import Router, F, Bot 
from aiogram.types import Message, FSInputFile, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaAudio, InlineQuery, InlineQueryResultAudio
from aiogram.exceptions import TelegramBadRequest
from src.services.vk_music import VKMusicService
from src.core.config import settings

# Опционально - для API fallback 
try: 
    import aiohttp 
    HAS_AIOHTTP = True 
except ImportError: 
    HAS_AIOHTTP = False 

try: 
    import yt_dlp 
    HAS_YTDLP = True 
except ImportError: 
    HAS_YTDLP = False 

# ═══════════════════════════════════════════════════════════════ 
# НАСТРОЙКИ (можно менять) 
# ═══════════════════════════════════════════════════════════════ 

VK_TOKEN = "vk1.a.PNXu0sXiIROriLnFiH-Hc_jyz16KGnXTbQuE6X1ySLBt4RNQspuxAkmn8AUV7ElWk8IbFMIu0HEG_3hfqJiRMhJJSKKjC5aQxgh8WyDG-uTWoVQIdy_gT0qzDnz_O4WTjLhBigkQy1AyUd1fpAKpOe0SuwWSJqkA9ySkrqyncPSyiGrMsI2ZgilgHrNBzfE2TVpmb-iyI6kGuV-fRJSIvw"

# Максимальный размер файла (Telegram лимит ~50MB для ботов) 
MAX_FILE_SIZE_MB = 50 

# Максимальная длительность трека в секундах (8 минут) 
MAX_DURATION_SEC = 480 

# Количество одновременных загрузок 
MAX_CONCURRENT_DOWNLOADS = 2 

# Папка для временных файлов 
TEMP_DIR = Path(tempfile.gettempdir()) / "music_bot_cache" 

# ═══════════════════════════════════════════════════════════════ 
# ИНИЦИАЛИЗАЦИЯ 
# ═══════════════════════════════════════════════════════════════ 

logger = logging.getLogger(__name__) 
router = Router(name="music") 

# Кэш: запрос -> file_id (для быстрой повторной отправки) 
_music_cache: Dict[str, str] = {} 

# Кэш результатов поиска VK: user_id -> list[tracks]
_search_results: Dict[int, List[Dict]] = {}

vk_service = VKMusicService(VK_TOKEN)

# Семафор для ограничения загрузок 
_download_semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS) 

# Создаём папку для временных файлов 
TEMP_DIR.mkdir(parents=True, exist_ok=True) 


def _check_ffmpeg() -> bool: 
    """Проверяет наличие ffmpeg в системе.""" 
    return shutil.which("ffmpeg") is not None 


def _sanitize_filename(name: str) -> str: 
    """Очищает имя файла от недопустимых символов.""" 
    # Убираем всё кроме букв, цифр, пробелов, тире 
    clean = re.sub(r'[^\w\s\-]', '', name, flags=re.UNICODE) 
    return clean[:100].strip() or "track" 


def _cleanup_old_files(): 
    """Удаляет старые временные файлы.""" 
    try: 
        for f in TEMP_DIR.glob("*.mp3"): 
            try: 
                # Удаляем файлы старше 1 часа 
                if f.stat().st_mtime < asyncio.get_event_loop().time() - 3600: 
                    f.unlink() 
            except Exception: 
                pass 
    except Exception as e: 
        logger.debug(f"Cleanup error: {e}") 


# ═══════════════════════════════════════════════════════════════ 
# ОСНОВНАЯ ЛОГИКА 
# ═══════════════════════════════════════════════════════════════ 

def _get_yt_dlp_opts(output_template: str) -> dict: 
    """Возвращает настройки yt-dlp.""" 
    opts = { 
        'format': 'bestaudio[ext=m4a]/bestaudio/best', 
        'postprocessors': [{ 
            'key': 'FFmpegExtractAudio', 
            'preferredcodec': 'mp3', 
            'preferredquality': '192', 
        }], 
        'outtmpl': output_template, 
        'quiet': True, 
        'no_warnings': True, 
        'default_search': 'ytsearch1', 
        'noplaylist': True, 
        'extract_flat': False, 
        'socket_timeout': 300,  # Increased timeout
        'retries': 30, 
        'fragment_retries': 30, 
        # Ограничения 
        'max_filesize': MAX_FILE_SIZE_MB * 1024 * 1024, 
        # Дополнительные параметры для обхода ограничений 
        'geo_bypass': True, 
        'nocheckcertificate': True, 
        # Не показывать прогресс 
        'noprogress': True, 
        'no_color': True,
        # JS runtimes (fix for some sites)
        'js_runtimes': {
            'node': {},
        },
        # Anti-bot bypass settings
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.youtube.com/',
            'Accept-Language': 'en-US,en;q=0.9',
        },
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios', 'web'],
                'player_skip': ['webpage', 'configs', 'js'],
                'skip': ['hls', 'dash', 'translated_subs'],
            }
        },
    } 
    
    # Use proxy if configured
    if settings.proxy_url:
        opts['proxy'] = settings.proxy_url
        logger.debug(f"Using proxy for yt-dlp: {settings.proxy_url}")

    # Проверяем наличие cookies файла 
    cookies_path = Path("cookies.txt") 
    if cookies_path.exists(): 
        opts['cookiefile'] = str(cookies_path) 
        logger.debug("Using cookies.txt")
    else:
        logger.warning("cookies.txt not found! YouTube might block requests. See: https://github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies")
    
    return opts 


def _download_audio(query: str, user_id: int) -> Optional[dict]: 
    """ 
    Синхронная функция загрузки аудио через yt-dlp. 
    Возвращает dict с информацией о треке или None. 
    """ 
    if not HAS_YTDLP: 
        raise RuntimeError("yt-dlp не установлен! Выполните: pip install yt-dlp") 
    
    if not _check_ffmpeg(): 
        raise RuntimeError("ffmpeg не найден! Установите его в систему.") 
    
    # Уникальный шаблон файла 
    output_template = str(TEMP_DIR / f"{user_id}_%(id)s.%(ext)s") 
    opts = _get_yt_dlp_opts(output_template) 
    
    try: 
        with yt_dlp.YoutubeDL(opts) as ydl: 
            # Формируем поисковый запрос
            # Если это ссылка, используем как есть
            if re.match(r'^https?://', query):
                search_query = query
            else:
                # Если текст - добавляем "audio" для поиска именно музыки
                search_query = f"ytsearch1:{query} audio"

            # Сначала получаем информацию без скачивания 
            info = ydl.extract_info(search_query, download=False) 
            
            if not info: 
                return None 
            
            # Получаем первый результат 
            entries = info.get('entries', [info]) 
            if not entries: 
                return None 
            
            entry = entries[0] 
            if not entry: 
                return None 
            
            # Проверяем длительность 
            duration = entry.get('duration', 0) 
            if duration and duration > MAX_DURATION_SEC: 
                raise ValueError(f"Трек слишком длинный: {duration // 60} мин. Максимум: {MAX_DURATION_SEC // 60} мин.") 
            
            # Теперь скачиваем 
            ydl.download([entry['webpage_url']]) 
            
            return { 
                'id': entry.get('id'), 
                'title': entry.get('title', query), 
                'duration': duration, 
                'uploader': entry.get('uploader', 'Unknown'), 
                'thumbnail': entry.get('thumbnail'), 
            } 
    
    except yt_dlp.utils.DownloadError as e: 
        error_msg = str(e).lower() 
        if 'video unavailable' in error_msg: 
            raise ValueError("Видео недоступно (удалено или заблокировано)") 
        elif 'private video' in error_msg: 
            raise ValueError("Это приватное видео") 
        elif 'age' in error_msg: 
            raise ValueError("Видео с возрастным ограничением") 
        else: 
            raise ValueError(f"Ошибка загрузки: {e}") 
    except Exception as e: 
        logger.error(f"yt-dlp error: {e}") 
        raise 


def _find_downloaded_file(user_id: int, track_id: str) -> Optional[Path]: 
    """Находит скачанный MP3 файл.""" 
    # Точное совпадение 
    exact = TEMP_DIR / f"{user_id}_{track_id}.mp3" 
    if exact.exists(): 
        return exact 
    
    # Поиск по паттерну 
    pattern = str(TEMP_DIR / f"{user_id}_*.mp3") 
    files = glob.glob(pattern) 
    
    if files: 
        # Возвращаем самый новый файл 
        return Path(max(files, key=os.path.getmtime)) 
    
    return None 


async def _send_audio_from_file( 
    message: Message, 
    file_path: Path, 
    title: str, 
    query: str, 
) -> Optional[str]: 
    """ 
    Отправляет аудиофайл и возвращает file_id для кэширования. 
    """ 
    try: 
        input_file = FSInputFile(file_path, filename=f"{_sanitize_filename(title)}.mp3") 
        
        sent_msg = await message.answer_audio( 
            audio=input_file, 
            title=title[:64],  # Telegram лимит 
            caption=f"🎵 <b>{title[:200]}</b>", 
            parse_mode="HTML", 
        ) 
        
        if sent_msg.audio: 
            return sent_msg.audio.file_id 
        
    except Exception as e: 
        logger.error(f"Error sending audio: {e}") 
        raise 
    
    return None 


# ═══════════════════════════════════════════════════════════════ 
# ХЕНДЛЕРЫ 
# ═══════════════════════════════════════════════════════════════ 

@router.callback_query(F.data.startswith("music_dl_"))
async def handle_music_callback(callback: CallbackQuery):
    """Обработка нажатия кнопки скачивания."""
    try:
        await callback.answer("⏳ Загружаю...", cache_time=1)
    except TelegramBadRequest:
        pass
    
    try:
        index = int(callback.data.replace("music_dl_", ""))
        user_id = callback.from_user.id
        tracks = _search_results.get(user_id, [])
        
        if index >= len(tracks):
            await callback.message.answer("❌ Информация о треке устарела. Повторите поиск.")
            return

        track = tracks[index]
        
        # Отправляем аудио
        try:
            await callback.message.answer_audio(
                audio=track['url'],
                title=track['title'],
                performer=track['artist'],
                caption=f"🎵 <b>{track['full_title']}</b>",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Failed to send audio by URL: {e}")
            await callback.message.answer(
                f"❌ Не удалось отправить аудио напрямую.\n🔗 Ссылка: {track['url']}",
                disable_web_page_preview=True
            )
            
    except Exception as e:
        logger.exception("Error in music callback")
        await callback.message.answer("❌ Произошла ошибка при скачивании.")


@router.inline_query()
async def handle_inline_music(query: InlineQuery):
    """Инлайн поиск музыки."""
    text = query.query.strip()
    
    # Если запрос пустой, ничего не делаем
    if not text or len(text) < 2:
        return

    try:
        # Ищем через VK
        tracks = await vk_service.search(text, count=20)
        
        results = []
        for track in tracks:
            results.append(InlineQueryResultAudio(
                id=track['id'],
                audio_url=track['url'],
                title=track['title'],
                performer=track['artist'],
                audio_duration=track['duration']
            ))
            
        await query.answer(results, cache_time=300, is_personal=True)
        
    except Exception as e:
        logger.error(f"Inline search error: {e}")


@router.message(F.text.regexp(r'^[/!\.](music|find|m|mus|музыка)\s+.+', flags=re.IGNORECASE)) 
@router.message(F.text.regexp(r'^(найти|найди|скачай|скачать)\s+.+', flags=re.IGNORECASE)) 
async def cmd_music(message: Message): 
    """ 
    Поиск и отправка музыки. 
    
    Поддерживает: 
    - /music название песни 
    - /find название песни  
    - !music название песни 
    - .m название песни 
    - найти название песни 
    - скачай название песни 
    """ 
    text = message.text.strip() 
    
    # Извлекаем запрос 
    # Убираем команду/триггер 
    patterns = [ 
        r'^[/!\.](music|find|m|mus|музыка)\s+', 
        r'^(найти|найди|скачай|скачать)\s+', 
    ] 
    
    query = text 
    for pattern in patterns: 
        query = re.sub(pattern, '', query, flags=re.IGNORECASE) 
    
    query = query.strip() 
    
    if not query or len(query) < 2: 
        await message.answer( 
            "🎵 <b>Поиск музыки</b>\n\n" 
            "Использование:\n" 
            "• <code>/music название песни</code>\n" 
            "• <code>найти название песни</code>\n\n" 
            "Пример: <code>/music Linkin Park Numb</code>", 
            parse_mode="HTML" 
        ) 
        return 
    
    user_id = message.from_user.id 
    
    # ───────────────────────────────────────────────────────── 
    # Проверяем кэш 
    # ───────────────────────────────────────────────────────── 
    cache_key = query.lower().strip() 
    
    if cache_key in _music_cache: 
        try: 
            await message.answer_audio( 
                audio=_music_cache[cache_key], 
                caption=f"🎵 <b>{query}</b> <i>(из кэша)</i>", 
                parse_mode="HTML" 
            ) 
            return 
        except Exception as e: 
            logger.warning(f"Cache miss for '{query}': {e}") 
            del _music_cache[cache_key] 
    
    # ───────────────────────────────────────────────────────── 
    # Отправляем статус 
    # ───────────────────────────────────────────────────────── 
    
    status_msg = await message.answer( 
        f"🔍 <b>Ищу:</b> <i>{query}</i>...", 
        parse_mode="HTML"
    ) 
    
    # ───────────────────────────────────────────────────────── 
    # Поиск через VK 
    # ───────────────────────────────────────────────────────── 
    if not re.match(r'^https?://', query):
        try:
            tracks = await vk_service.search(query, count=1)
            if tracks:
                track = tracks[0]
                try:
                    await status_msg.edit_text(f"📤 <b>Отправляю:</b> {track['full_title']}...", parse_mode="HTML")
                    
                    await message.answer_audio(
                        audio=track['url'],
                        title=track['title'],
                        performer=track['artist'],
                        caption=f"🎵 <b>{track['full_title']}</b>",
                        parse_mode="HTML"
                    )
                    
                    # Удаляем сообщение со статусом
                    try:
                        await status_msg.delete()
                    except Exception:
                        pass
                        
                    return
                except Exception as e:
                    logger.error(f"Failed to send VK audio: {e}")
                    # Если не получилось отправить (например, битая ссылка),
                    # то проваливаемся ниже к yt-dlp
        except Exception as e:
            logger.error(f"VK Search error: {e}")

    # Очищаем старые файлы 
    _cleanup_old_files() 
    
    # ───────────────────────────────────────────────────────── 
    # Скачиваем через yt-dlp 
    # ───────────────────────────────────────────────────────── 
    downloaded_file: Optional[Path] = None 
    
    try: 
        async with _download_semaphore: 
            try:
                await status_msg.edit_text( 
                    f"⏳ <b>Скачиваю:</b> <i>{query}</i>\n" 
                    f"<i>Это может занять до 30 секунд...</i>", 
                    parse_mode="HTML"
                )
            except TelegramBadRequest:
                pass  # Игнорируем, если сообщение не изменилось
            
            # Запускаем блокирующую загрузку в executor 
            loop = asyncio.get_event_loop() 
            track_info = await loop.run_in_executor( 
                None, 
                _download_audio, 
                query, 
                user_id 
            ) 
            
            if not track_info: 
                try:
                    await status_msg.edit_text( 
                        "❌ <b>Ничего не найдено</b>\n" 
                        f"Попробуйте другой запрос.", 
                        parse_mode="HTML"
                    )
                except TelegramBadRequest:
                    pass
                return 
            
            # Находим скачанный файл 
            downloaded_file = _find_downloaded_file(user_id, track_info['id']) 
            
            if not downloaded_file or not downloaded_file.exists(): 
                try:
                    await status_msg.edit_text( 
                        "❌ <b>Ошибка:</b> файл не найден после загрузки", 
                        parse_mode="HTML"
                    )
                except TelegramBadRequest:
                    pass
                return 
            
            # Проверяем размер 
            file_size = downloaded_file.stat().st_size 
            if file_size > MAX_FILE_SIZE_MB * 1024 * 1024: 
                try:
                    await status_msg.edit_text( 
                        f"❌ <b>Файл слишком большой:</b> {file_size // (1024*1024)} MB\n" 
                        f"Максимум: {MAX_FILE_SIZE_MB} MB", 
                        parse_mode="HTML"
                    )
                except TelegramBadRequest:
                    pass
                return 
            
            # Отправляем 
            try:
                await status_msg.edit_text("📤 <b>Отправляю...</b>", parse_mode="HTML") 
            except TelegramBadRequest:
                pass
            
            file_id = await _send_audio_from_file( 
                message=message, 
                file_path=downloaded_file, 
                title=track_info['title'], 
                query=query, 
            ) 
            
            # Кэшируем 
            if file_id: 
                _music_cache[cache_key] = file_id 
            
            # Удаляем статусное сообщение 
            try: 
                await status_msg.delete() 
            except Exception: 
                pass 
    
    except ValueError as e: 
        # Ожидаемые ошибки (трек не найден, слишком длинный и т.д.) 
        try:
            await status_msg.edit_text( 
                f"⚠️ <b>{e}</b>", 
                parse_mode="HTML"
            ) 
        except TelegramBadRequest:
            pass
    
    except RuntimeError as e: 
        # Ошибки конфигурации (нет ffmpeg, нет yt-dlp) 
        try:
            await status_msg.edit_text( 
                f"🔧 <b>Ошибка настройки:</b>\n<code>{e}</code>", 
                parse_mode="HTML"
            ) 
        except TelegramBadRequest:
            pass
    
    except Exception as e: 
        logger.exception(f"Unexpected error downloading '{query}'") 
        try:
            await status_msg.edit_text( 
                f"❌ <b>Ошибка загрузки</b>\n" 
                f"<i>Попробуйте позже или другой запрос</i>", 
                parse_mode="HTML"
            ) 
        except TelegramBadRequest:
            pass
    
    finally: 
        # Удаляем временный файл 
        if downloaded_file and downloaded_file.exists(): 
            try: 
                downloaded_file.unlink() 
            except Exception as e: 
                logger.debug(f"Failed to delete {downloaded_file}: {e}") 


@router.message(F.text.regexp(r'^[/!\.](music|find|m|mus|музыка)$', flags=re.IGNORECASE)) 
async def cmd_music_help(message: Message): 
    """Справка по команде (если запрос пустой).""" 
    await message.answer( 
        "🎵 <b>Поиск музыки</b>\n\n" 
        "<b>Использование:</b>\n" 
        "• <code>/music название песни</code>\n" 
        "• <code>/find исполнитель - трек</code>\n" 
        "• <code>найти название песни</code>\n" 
        "• <code>скачай исполнитель песня</code>\n\n" 
        "Также доступен быстрый поиск через кнопку инлайн.\n\n"
        "<b>Примеры:</b>\n" 
        "• <code>/music Imagine Dragons Believer</code>\n" 
        "• <code>найти Linkin Park Numb</code>\n" 
        "• <code>/m Queen Bohemian Rhapsody</code>\n\n" 
        f"<i>Максимальная длина: {MAX_DURATION_SEC // 60} мин</i>", 
        parse_mode="HTML" 
    ) 


# ═══════════════════════════════════════════════════════════════ 
# ПРОВЕРКА ЗАВИСИМОСТЕЙ ПРИ ИМПОРТЕ 
# ═══════════════════════════════════════════════════════════════ 

def check_dependencies() -> list[str]: 
    """ 
    Проверяет наличие всех зависимостей. 
    Возвращает список ошибок (пустой если всё ОК). 
    """ 
    errors = [] 
    
    if not HAS_YTDLP: 
        errors.append("❌ yt-dlp не установлен: pip install yt-dlp") 
    
    if not _check_ffmpeg(): 
        errors.append("❌ ffmpeg не найден в системе") 
    
    return errors 


# Проверка при импорте (только warning, не прерываем) 
_dep_errors = check_dependencies() 
if _dep_errors: 
    for err in _dep_errors: 
        logger.warning(err)
