"""
🎨 Генерация изображений через Hugging Face Inference API
- Использует модель black-forest-labs/FLUX.1-schnell
- Провайдер: nebius
"""

import re
import io
import html
import logging 
import asyncio
import os
from typing import Optional

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, BufferedInputFile
from aiogram.enums import ChatAction
from huggingface_hub import InferenceClient

from src.core.container import Container
from src.core.providers import AIProviderFactory

router = Router(name="draw")

# ═══════════════════════════════════════════════════════════
#                        НАСТРОЙКИ
# ═══════════════════════════════════════════════════════════

DRAW_PATTERN = re.compile(
    r"(?is)\bсенсей[,\s]+(?:рисуй|нарисуй)\s+(.+?)\s*$"
)

# API Token
# User provided this token in previous turns. 
# Ideally this should be in os.environ["HF_TOKEN"] but for stability we use the known working key if env is missing.
HF_TOKEN = os.environ.get("HF_TOKEN", "")
MODEL_ID = "black-forest-labs/FLUX.1-schnell"
PROVIDER = "nebius"

# Инициализация клиента
client = InferenceClient(
    provider=PROVIDER,
    api_key=HF_TOKEN,
)

# ═══════════════════════════════════════════════════════════
#                     ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ═══════════════════════════════════════════════════════════

def extract_prompt_from_command(text: str) -> str:
    """Извлекает промпт из команды /draw или /draw@BotName."""
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        return ""
    return parts[1].strip()

def contains_cyrillic(text: str) -> bool:
    """Проверяет наличие кириллицы в тексте."""
    return bool(re.search(r'[а-яА-ЯёЁ]', text))

# ═══════════════════════════════════════════════════════════
#                     ОСНОВНАЯ ЛОГИКА
# ═══════════════════════════════════════════════════════════

async def process_draw_request(message: Message, prompt: str, container: Container) -> None:
    """Генерация и отправка изображения."""
    prompt = (prompt or "").strip()
    
    if not prompt:
        await message.answer(
            "🎨 Что мне нарисовать?\n"
            "Пример: <code>/draw Сенсей точит Катану</code>",
            parse_mode="HTML"
        )
        return
    
    # Перевод промпта если есть кириллица
    final_prompt = prompt
    if contains_cyrillic(prompt):
        try:
            ai_factory = AIProviderFactory(container.settings)
            translated = await ai_factory.generate_text(
                system="You are a professional translator. Translate the following text to English. Return ONLY the translated text, no explanations.",
                user=prompt
            )
            if translated and not translated.startswith("❌"):
                final_prompt = translated.strip()
                logging.info(f"Translated prompt: '{prompt}' -> '{final_prompt}'")
        except Exception as e:
            logging.error(f"Translation failed: {e}")
            # Fallback to original prompt

    # Подготовка caption (с экранированием HTML)
    safe_caption = html.escape(prompt)
    if len(safe_caption) > 900:
        safe_caption = safe_caption[:900] + "…"
    
    wait_message = None
    try:
        # Уведомление о начале процесса
        wait_message = await message.answer(f"🎨Создаю шедевр через свои нейроны...")

        # Показываем "загружает фото"
        await message.bot.send_chat_action(
            chat_id=message.chat.id,
            action=ChatAction.UPLOAD_PHOTO
        )
        
        # Генерируем изображение (в отдельном потоке, так как это синхронный вызов)
        def generate():
            return client.text_to_image(
                final_prompt,
                model=MODEL_ID,
            )

        image = await asyncio.to_thread(generate)
        
        # Конвертируем PIL Image в байты
        output = io.BytesIO()
        image.save(output, format="PNG")
        img_bytes = output.getvalue()
        
        # Удаляем сообщение об ожидании
        try:
            if wait_message:
                await wait_message.delete()
        except Exception:
            pass

        # Отправляем
        file = BufferedInputFile(img_bytes, filename="image.png")
        caption = f"🎨 <b>{safe_caption}</b>"
        if final_prompt != prompt:
             caption += f"\n<tg-spoiler>Prompt: {html.escape(final_prompt)}</tg-spoiler>"

        await message.answer_photo(
            photo=file,
            caption=caption,
            parse_mode="HTML",
        )
        
    except Exception as e:
        logging.exception("Failed to generate/send image")
        
        # Удаляем сообщение об ожидании при ошибке
        try:
            if wait_message:
                await wait_message.delete()
        except Exception:
            pass

        await message.answer(
            f"😔 Не получилось нарисовать.\nОшибка: {str(e)}"
        )

@router.message(Command("draw"))
async def command_draw(message: Message, container: Container) -> None:
    """Обработчик команды /draw <промпт>"""
    if not message.text:
        return
    prompt = extract_prompt_from_command(message.text)
    await process_draw_request(message, prompt, container)

@router.message(F.text.regexp(DRAW_PATTERN))
async def trigger_draw(message: Message, container: Container) -> None:
    """Обработчик: 'сенсей рисуй ...' / 'сенсей, нарисуй ...'"""
    if not message.text:
        return
    match = DRAW_PATTERN.search(message.text)
    if not match:
        return
    prompt = match.group(1).strip()
    await process_draw_request(message, prompt, container)
