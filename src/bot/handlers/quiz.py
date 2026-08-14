# src/bot/handlers/quiz.py
import os
import asyncio
import html
from pathlib import Path
from aiogram import Router, Bot, F
from aiogram.types import Message
from aiogram.filters import Command, BaseFilter
from aiogram.fsm.context import FSMContext

from src.bot.states.quiz_states import AddQuestionStates
from src.core.container import Container
from src.core.visuals import Visuals

router = Router()

# Директория для хранения изображений
IMAGES_DIR = Path("data/quiz_images")
IMAGES_DIR.mkdir(parents=True, exist_ok=True)


def get_quiz_service(container: Container) -> "QuizService":
    return container.quiz_service


class QuizActiveFilter(BaseFilter):
    """Фильтр для проверки активной викторины."""
    async def __call__(self, message: Message, container: Container) -> bool:
        service = get_quiz_service(container)
        return await service.is_quiz_running(message.chat.id)


# ============ ДОБАВЛЕНИЕ ВОПРОСА (в ЛС) ============

@router.message(Command("addquestion", "addquest"), F.chat.type == "private")
async def cmd_add_question(message: Message, state: FSMContext):
    """Начало добавления вопроса."""
    # Проверка прав (опционально - добавить проверку админа)
    await message.answer(
        "📝 <b>Добавление вопроса для викторины</b>\n\n"
        "Отправьте текст вопроса:",
        parse_mode="HTML"
    )
    await state.set_state(AddQuestionStates.waiting_question)


@router.message(AddQuestionStates.waiting_question, F.text)
async def process_question_text(message: Message, state: FSMContext):
    """Получение текста вопроса."""
    await state.update_data(question_text=message.text)
    await message.answer(
        "🖼 Отправьте изображение для вопроса.\n\n"
        "Или отправьте /skip чтобы пропустить."
    )
    await state.set_state(AddQuestionStates.waiting_image)


@router.message(AddQuestionStates.waiting_image, Command("skip"))
async def skip_image(message: Message, state: FSMContext):
    """Пропуск изображения."""
    await state.update_data(image_path=None)
    await message.answer(
        "✅ Теперь отправьте правильный ответ:\n"
        "<i>(Можно указать несколько вариантов через символ | )</i>",
        parse_mode="HTML"
    )
    await state.set_state(AddQuestionStates.waiting_answer)


@router.message(AddQuestionStates.waiting_image, F.photo)
async def process_image(message: Message, state: FSMContext, bot: Bot):
    """Получение изображения."""
    photo = message.photo[-1]  # Лучшее качество
    
    # Скачиваем файл
    file = await bot.get_file(photo.file_id)
    file_path = IMAGES_DIR / f"{photo.file_unique_id}.jpg"
    await bot.download_file(file.file_path, file_path)
    
    await state.update_data(image_path=str(file_path))
    await message.answer(
        "✅ Изображение сохранено!\n\n"
        "Теперь отправьте правильный ответ:\n"
        "<i>(Можно указать несколько вариантов через символ | )</i>",
        parse_mode="HTML"
    )
    await state.set_state(AddQuestionStates.waiting_answer)


@router.message(AddQuestionStates.waiting_answer, F.text)
async def process_answer(
    message: Message,
    state: FSMContext,
    container: Container
):
    """Получение ответа и сохранение вопроса."""
    data = await state.get_data()
    
    service = get_quiz_service(container)
    question_id = await service.add_question(
        question=data["question_text"],
        answer=message.text.strip(),
        image_path=data.get("image_path")
    )
    
    await message.answer(
        f"✅ <b>Вопрос добавлен!</b>\n\n"
        f"🆔 ID: {question_id}\n"
        f"❓ Вопрос: {data['question_text'][:50]}...\n"
        f"✔️ Ответ: {message.text}\n"
        f"🖼 Фото: {'Да' if data.get('image_path') else 'Нет'}",
        parse_mode="HTML"
    )
    await state.clear()


# ============ ЗАПУСК ВИКТОРИНЫ (в чате) ============

@router.message(Command("senseiviktorina"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_start_quiz(
    message: Message,
    bot: Bot,
    container: Container
):
    """Запуск викторины в чате."""
    chat_id = message.chat.id
    service = get_quiz_service(container)
    
    started = await service.start_quiz(chat_id)
    if not started:
        await message.answer("⚠️ Викторина уже запущена в этом чате!")
        return
    
    w = Visuals.FRAME_W_MENU
    lines = [
        Visuals.frame_top_left(w),
        Visuals.frame_line_left("🧠 ВИКТОРИНА ЗАПУЩЕНА!", w),
        Visuals.frame_separator_left(w),
        Visuals.frame_line_left("1️⃣ Вопрос через 20 сек...", w, "left"),
        Visuals.frame_line_left("✍️ Пишите ответы в чат", w, "left"),
        Visuals.frame_separator_left(w),
        Visuals.frame_line_left("🛑 /stopquiz", w, "center"),
        Visuals.frame_bottom_left(w)
    ]
    text = "<pre>\n" + "\n".join(lines) + "\n</pre>"
    
    await message.answer(text, parse_mode="HTML")
    
    # Запускаем цикл викторины в фоне
    asyncio.create_task(service.run_quiz_loop(chat_id, bot))


@router.message(Command("stopquiz"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_stop_quiz(
    message: Message,
    container: Container
):
    """Остановка викторины."""
    chat_id = message.chat.id
    service = get_quiz_service(container)
    
    if not await service.is_quiz_running(chat_id):
        await message.answer("ℹ️ Викторина не запущена.")
        return
    
    await service.stop_quiz(chat_id)
    await message.answer("🛑 Викторина остановлена!")


# ============ ПРОВЕРКА ОТВЕТОВ ============

@router.message(F.chat.type.in_({"group", "supergroup"}), F.text, ~F.text.startswith("/"), QuizActiveFilter())
async def check_quiz_answer(
    message: Message,
    bot: Bot,
    container: Container
):
    """Проверка ответов на викторину."""
    chat_id = message.chat.id
    user_id = message.from_user.id

    service = get_quiz_service(container)
    
    user_name = html.escape(message.from_user.full_name)
    result = await service.check_answer(chat_id, user_id, user_name, message.text)
    
    if result:
        w = Visuals.FRAME_W_MENU
        lines = [
            Visuals.frame_top_left(w),
            Visuals.frame_line_left("🎉 ПРАВИЛЬНО!", w),
            Visuals.frame_separator_left(w),
            Visuals.frame_line_left(f"👤 {user_name}", w, align="left"),
            Visuals.frame_line_left(f"💰 +{result['reward']:.0f} монет", w, align="left"),
            Visuals.frame_line_left(f"🎟 +1 билет", w, align="left"),
            Visuals.frame_separator_left(w),
            Visuals.frame_line_left("🔜 След. вопрос...", w, align="left"),
            Visuals.frame_bottom_left(w)
        ]
        text = "<pre>\n" + "\n".join(lines) + "\n</pre>"
        await message.reply(text, parse_mode="HTML")
