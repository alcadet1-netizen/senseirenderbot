"""
🧠 Сервис викторины.
"""

import json
import asyncio
import os
import logging
import textwrap
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from aiogram import Bot
from aiogram.types import FSInputFile

from src.domain.repositories.quiz_repository import QuizRepository
from src.domain.repositories.user_repository import UserRepository
from src.domain.repositories.transaction_repository import TransactionRepository
from src.domain.repositories.bank_repository import BankRepository
from src.domain.repositories.ticket_repository import TicketRepository
from src.infra.database.models import TransactionType
from src.infra.database.uow import UnitOfWork
from src.infra.redis.locks import DistributedLock
from src.core.exceptions import BankInsufficientFundsError
from src.core.visuals import Visuals


class QuizService:
    """Сервис для управления викториной."""
    
    REDIS_PREFIX = "quiz"
    QUIZ_REWARD = 100.0
    QUESTION_INTERVAL = 20  # Интервал между вопросами
    ANSWER_TIMEOUT = 300    # Таймаут на ответ
    
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        redis: Redis
    ):
        self.session_factory = session_factory
        self.redis = redis

    async def run_quiz_loop(self, chat_id: int, bot: Bot):
        """Цикл викторины."""
        try:
            # Задержка перед первым вопросом
            await asyncio.sleep(20)
            
            while await self.is_quiz_running(chat_id):
                
                question_data = await self.get_next_question(chat_id)
                if not question_data:
                    summary = await self.generate_summary(chat_id)
                    await bot.send_message(chat_id, f"🏁 Спасибо всем за игру, вопросы кончились!\n\n{summary}", parse_mode="HTML")
                    await self.stop_quiz(chat_id)
                    break
                
                # Отправляем вопрос
                await self._send_question(bot, chat_id, question_data)
                
                # Ждём правильного ответа (блокируем цикл пока не ответят)
                await self._wait_for_answer(chat_id)
                
                # Проверяем, не остановлена ли викторина пока ждали
                if not await self.is_quiz_running(chat_id):
                    break

                # Пауза перед следующим вопросом
                await asyncio.sleep(20)
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"Quiz error: {e}")
            await bot.send_message(chat_id, "⚠️ Ошибка викторины.")
            await self.stop_quiz(chat_id)

    async def _send_question(self, bot: Bot, chat_id: int, data: Dict):
        """Отправить вопрос в чат с повторными попытками."""
        state = await self._get_quiz_state(chat_id)
        
        # Формируем красивый блок вопроса
        w = Visuals.FRAME_W_MENU
        lines = [
            Visuals.frame_top_left(w),
            Visuals.frame_line_left(f"❓ Вопрос #{state['round']}", w),
            Visuals.frame_separator_left(w),
        ]
        
        # Разбиваем текст вопроса на строки
        q_text = data['text']
        wrapped = textwrap.wrap(q_text, width=w-4)
        
        for line in wrapped:
            lines.append(Visuals.frame_line_left(line, w, align="left"))
            
        lines.append(Visuals.frame_bottom_left(w))
        text_block = "<pre>\n" + "\n".join(lines) + "\n</pre>"
        
        image_path = data.get('image_path')
        
        for attempt in range(3):
            try:
                if image_path and os.path.exists(image_path):
                    await bot.send_photo(chat_id, FSInputFile(image_path), caption=text_block, parse_mode="HTML")
                else:
                    await bot.send_message(chat_id, text_block, parse_mode="HTML")
                return
            except Exception as e:
                if attempt == 2:
                    raise e
                logger.warning(f"Ошибка отправки вопроса (попытка {attempt+1}/3): {e}")
                await asyncio.sleep(1)

    async def _wait_for_answer(self, chat_id: int):
        """Ожидание ответа или таймаута."""
        for _ in range(self.ANSWER_TIMEOUT):
            if not await self.is_quiz_running(chat_id):
                return

            state = await self._get_quiz_state(chat_id)
            if not state or state.get("status") == "answered":
                return
            
            await asyncio.sleep(1)

    async def add_question(self, question: str, answer: str, image_path: Optional[str] = None) -> int:
        """Добавить вопрос."""
        uow = UnitOfWork(self.session_factory)
        async with uow:
            repo = QuizRepository(uow.session)
            q = await repo.add_question(question, answer, image_path)
            await uow.commit()
            return q.id

    async def start_quiz(self, chat_id: int) -> bool:
        """Запустить викторину."""
        lock = DistributedLock(self.redis)
        async with lock.acquire(f"{self.REDIS_PREFIX}:start:{chat_id}"):
            if await self.is_quiz_running(chat_id):
                return False
            
            await self._set_quiz_state(chat_id, {
                "status": "running",
                "round": 0,
                "current_question_id": None,
                "used_questions": [],
                "stats": {
                    "total_questions": 0,
                    "total_coins": 0,
                    "total_tickets": 0,
                    "winners": {}
                }
            })
            return True

    async def stop_quiz(self, chat_id: int):
        """Остановить викторину и удалить использованные вопросы."""
        state = await self._get_quiz_state(chat_id)
        if state and state.get("used_questions"):
            await self._delete_used_questions(state["used_questions"])

        await self.redis.delete(f"{self.REDIS_PREFIX}:state:{chat_id}")

    async def _delete_used_questions(self, question_ids: List[int]):
        """Удалить использованные вопросы из БД."""
        if not question_ids:
            return
            
        uow = UnitOfWork(self.session_factory)
        async with uow:
            repo = QuizRepository(uow.session)
            await repo.delete_questions(question_ids)
            await uow.commit()

    async def is_quiz_running(self, chat_id: int) -> bool:
        """Проверить статус."""
        return await self.redis.exists(f"{self.REDIS_PREFIX}:state:{chat_id}")

    async def get_next_question(self, chat_id: int) -> Optional[Dict]:
        """Получить следующий вопрос."""
        state = await self._get_quiz_state(chat_id)
        if not state:
            return None
        
        used = state.get("used_questions", [])
        
        uow = UnitOfWork(self.session_factory)
        async with uow:
            repo = QuizRepository(uow.session)
            question = await repo.get_random_question(exclude_ids=used if used else None)
            
            if not question:
                return None
            
            # Обновляем состояние
            used.append(question.id)
            state.update({
                "current_question_id": question.id,
                "answer": question.answer.lower().strip(),
                "status": "waiting_answer",
                "round": state["round"] + 1,
                "used_questions": used
            })
            await self._set_quiz_state(chat_id, state)
            
            return {
                "id": question.id,
                "text": question.question_text,
                "image_path": question.image_path
            }

    async def check_answer(self, chat_id: int, user_id: int, user_name: str, text: str) -> Optional[Dict]:
        """Проверить ответ."""
        state = await self._get_quiz_state(chat_id)
        if not state or state.get("status") != "waiting_answer":
            return None
        
        correct_raw = state.get("answer", "")
        # Поддержка нескольких вариантов ответа через |
        correct_variants = [v.strip() for v in correct_raw.split("|")]
        
        user_answer = text.lower().strip()
        
        if user_answer not in correct_variants:
            return None
        
        # Блокируем чтобы только один победил
        lock = DistributedLock(self.redis)
        async with lock.acquire(f"{self.REDIS_PREFIX}:answer:{chat_id}"):
            state = await self._get_quiz_state(chat_id)
            if state.get("status") != "waiting_answer":
                return None
            
            state["status"] = "answered"
            
            # Обновляем статистику
            stats = state.get("stats", {
                "total_questions": 0, "total_coins": 0, "total_tickets": 0, "winners": {}
            })
            stats["total_questions"] += 1
            stats["total_coins"] += self.QUIZ_REWARD
            stats["total_tickets"] += 1
            
            winners = stats.get("winners", {})
            user_key = str(user_id)
            if user_key not in winners:
                winners[user_key] = {"name": user_name, "wins": 0, "coins": 0}
            
            winners[user_key]["wins"] += 1
            winners[user_key]["coins"] += int(self.QUIZ_REWARD)
            stats["winners"] = winners
            state["stats"] = stats

            await self._set_quiz_state(chat_id, state)
            
            reward_data = await self._grant_reward(user_id)
            
            # Сжигаем вопрос (удаляем из БД) после правильного ответа
            current_question_id = state.get("current_question_id")
            if current_question_id:
                await self._delete_used_questions([current_question_id])
            
            return {
                "user_id": user_id,
                "reward": self.QUIZ_REWARD,
                "correct_answer": correct_raw,
                "balance": reward_data["balance"]
            }

    async def generate_summary(self, chat_id: int) -> str:
        """Сгенерировать сводку по викторине."""
        state = await self._get_quiz_state(chat_id)
        if not state:
            return ""
        
        stats = state.get("stats", {
            "total_questions": 0, "total_coins": 0, "total_tickets": 0, "winners": {}
        })
        
        total_questions = stats["total_questions"]
        total_coins = stats["total_coins"]
        total_tickets = stats["total_tickets"]
        winners = stats["winners"]
        
        w = Visuals.FRAME_W_MENU
        lines = [
            Visuals.frame_top_left(w),
            Visuals.frame_line_left("📊 Итоги викторины", w),
            Visuals.frame_separator_left(w),
            Visuals.frame_line_left(f"Вопросов: {total_questions}", w, align="left"),
            Visuals.frame_line_left(f"Монет: {total_coins:.0f}", w, align="left"),
            Visuals.frame_line_left(f"Билетов: {total_tickets}", w, align="left"),
        ]
        
        if winners:
            lines.append(Visuals.frame_separator_left(w))
            lines.append(Visuals.frame_line_left("🏆 Топ победителей", w))
            lines.append(Visuals.frame_separator_left(w))
            # Сортируем по количеству побед
            sorted_winners = sorted(winners.values(), key=lambda x: x["wins"], reverse=True)
            for i, w_data in enumerate(sorted_winners[:10], 1):
                name = w_data['name']
                # Truncate name if needed
                max_name_len = w - 12 
                if len(name) > max_name_len:
                    name = name[:max_name_len-1] + "…"
                
                row = f"{i}. {name} ({w_data['wins']})"
                lines.append(Visuals.frame_line_left(row, w, align="left"))
        else:
            lines.append(Visuals.frame_separator_left(w))
            lines.append(Visuals.frame_line_left("Никто не выиграл 🤷‍♂️", w))
            
        lines.append(Visuals.frame_bottom_left(w))
        return "<pre>\n" + "\n".join(lines) + "\n</pre>"

    async def _grant_reward(self, user_id: int) -> dict:
        """Начислить награду."""
        uow = UnitOfWork(self.session_factory)
        async with uow:
            user_repo = UserRepository(uow.session)
            tx_repo = TransactionRepository(uow.session)
            bank_repo = BankRepository(uow.session)
            ticket_repo = TicketRepository(uow.session)
            
            user = await user_repo.get_for_update(user_id)
            if not user:
                return {"balance": 0}
            
            # 1. Выдача монет из банка
            try:
                await bank_repo.withdraw(self.QUIZ_REWARD)
                user.coins += self.QUIZ_REWARD
                
                await tx_repo.create(
                    user_id=user_id,
                    tx_type=TransactionType.QUIZ_WIN.value,
                    coins_change=self.QUIZ_REWARD,
                    description="Quiz Winner"
                )
            except BankInsufficientFundsError:
                # Если в банке нет денег, монеты не выдаем
                pass
            
            # 2. Выдача билета
            await ticket_repo.create(user.id)
            
            await uow.commit()
            return {"balance": user.coins}

    async def get_state(self, chat_id: int) -> Optional[Dict]:
        return await self._get_quiz_state(chat_id)

    async def _get_quiz_state(self, chat_id: int) -> Optional[Dict]:
        data = await self.redis.get(f"{self.REDIS_PREFIX}:state:{chat_id}")
        return json.loads(data) if data else None

    async def _set_quiz_state(self, chat_id: int, state: Dict):
        await self.redis.set(
            f"{self.REDIS_PREFIX}:state:{chat_id}",
            json.dumps(state),
            ex=86400
        )
