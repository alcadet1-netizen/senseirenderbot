"""
🧠 Сервис викторины.
"""

import asyncio
import logging
import textwrap
from typing import Optional, Dict, List
from datetime import datetime, timezone

from src.core.config import settings
from src.core.constants import (
    DAILY_BASE_COINS,
    DAILY_BASE_XP,
    DAILY_STREAK_BONUSES,
)
from src.core.exceptions import BankInsufficientFundsError
from src.core.visuals import Visuals
from src.infra.mongo.client import MongoClient

logger = logging.getLogger(__name__)


class QuizService:
    """Сервис для управления викториной."""

    QUIZ_REWARD = 100.0
    QUESTION_INTERVAL = 20  # Интервал между вопросами
    ANSWER_TIMEOUT = 300    # Таймаут на ответ

    def __init__(self, mongo_client: MongoClient):
        self.mongo_client = mongo_client
        self.db = mongo_client.database
        # Collections
        self.quiz_states = self.db.quiz_states  # Stores quiz state per chat
        self.questions = self.db.quiz_questions  # Stores quiz questions
        self.users = self.db.users
        self.transactions = self.db.transactions
        self.bank = self.db.bank  # Will store {_id: "main", balance: X}
        self.tickets = self.db.tickets  # For ticket tracking
        # Locks for concurrency control - we'll use asyncio.Lock per chat for simplicity
        self._chat_locks = {}
        self._lock = asyncio.Lock()  # Lock for managing the _chat_locks dict

    async def _get_chat_lock(self, chat_id: int) -> asyncio.Lock:
        """Get or create a lock for a specific chat."""
        async with self._lock:
            if chat_id not in self._chat_locks:
                self._chat_locks[chat_id] = asyncio.Lock()
            return self._chat_locks[chat_id]

    async def run_quiz_loop(self, chat_id: int, bot):
        """Цикл викторины."""
        chat_lock = await self._get_chat_lock(chat_id)

        async with chat_lock:
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
                logger.error(f"Quiz error: {e}")
                try:
                    await bot.send_message(chat_id, "⚠️ Ошибка викторины.")
                except:
                    pass  # Bot might not be available
                await self.stop_quiz(chat_id)

    async def _send_question(self, bot, chat_id: int, data: Dict):
        """Отправить вопрос в чат с повторными попытками."""
        # Get current state to get round number
        state = await self._get_quiz_state(chat_id)
        round_num = state.get("round", 0) if state else 0

        # Формируем красивый блок вопроса
        w = Visuals.FRAME_W_MENU
        lines = [
            Visuals.frame_top_left(w),
            Visuals.frame_line_left(f"❓ Вопрос #{round_num}", w),
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
                if image_path:
                    # In a real implementation, we'd check if the file exists
                    # For now, we'll just try to send it
                    await bot.send_photo(chat_id, photo=image_path, caption=text_block, parse_mode="HTML")
                else:
                    await bot.send_message(chat_id, text_block, parse_mode="HTML")
                return
            except Exception as e:
                if attempt == 2:
                    logger.error(f"Failed to send question after 3 attempts: {e}")
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
        # Find the next ID
        last_question = await self.questions.find_one(sort=[("_id", -1)])
        next_id = (last_question.get("_id", 0) + 1) if last_question else 1

        question_doc = {
            "_id": next_id,
            "question_text": question,
            "answer": answer.lower().strip(),
            "image_path": image_path,
            "created_at": datetime.now(timezone.utc),
        }

        await self.questions.insert_one(question_doc)
        return next_id

    async def start_quiz(self, chat_id: int) -> bool:
        """Запустить викторину."""
        chat_lock = await self._get_chat_lock(chat_id)

        async with chat_lock:
            if await self.is_quiz_running(chat_id):
                return False

            initial_state = {
                "status": "running",
                "round": 0,
                "current_question_id": None,
                "used_questions": [],
                "stats": {
                    "total_questions": 0,
                    "total_coins": 0,
                    "total_tickets": 0,
                    "winners": {}
                },
                "updated_at": datetime.now(timezone.utc)
            }

            await self.quiz_states.update_one(
                {"chat_id": chat_id},
                {"$set": initial_state},
                upsert=True
            )
            return True

    async def stop_quiz(self, chat_id: int):
        """Остановить викторину и удалить использованные вопросы."""
        state = await self._get_quiz_state(chat_id)
        if state and state.get("used_questions"):
            await self._delete_used_questions(state["used_questions"])

        await self.quiz_states.delete_one({"chat_id": chat_id})

    async def _delete_used_questions(self, question_ids: List[int]):
        """Удалить использованные вопросы из БД."""
        if not question_ids:
            return

        await self.questions.delete_many({"_id": {"$in": question_ids}})

    async def is_quiz_running(self, chat_id: int) -> bool:
        """Проверить статус."""
        state = await self.quiz_states.find_one({"chat_id": chat_id})
        return state is not None

    async def get_next_question(self, chat_id: int) -> Optional[Dict]:
        """Получить следующий вопрос."""
        state = await self._get_quiz_state(chat_id)
        if not state:
            return None

        used = state.get("used_questions", [])

        # Find a random question not in used list
        match_condition = {}
        if used:
            match_condition["_id"] = {"$nin": used}

        # Count matching questions
        count = await self.questions.count_documents(match_condition)
        if count == 0:
            return None

        # Get a random question
        # We'll use aggregation with $sample for random selection
        pipeline = []
        if match_condition:
            pipeline.append({"$match": match_condition})
        pipeline.append({"$sample": {"size": 1}})

        cursor = self.questions.aggregate(pipeline)
        question_doc = await cursor.to_list(length=1)

        if not question_doc:
            return None

        question = question_doc[0]

        # Обновляем состояние
        used.append(question["_id"])
        state.update({
            "current_question_id": question["_id"],
            "answer": question["answer"],
            "status": "waiting_answer",
            "round": state["round"] + 1,
            "used_questions": used,
            "updated_at": datetime.now(timezone.utc)
        })

        await self.quiz_states.update_one(
            {"chat_id": chat_id},
            {"$set": state}
        )

        return {
            "id": question["_id"],
            "text": question["question_text"],
            "image_path": question.get("image_path")
        }

    async def check_answer(self, chat_id: int, user_id: int, user_name: str, text: str) -> Optional[Dict]:
        """Проверить ответ."""
        chat_lock = await self._get_chat_lock(chat_id)

        async with chat_lock:
            state = await self.quiz_states.find_one({"chat_id": chat_id})
            if not state:
                return None

            # Check if quiz is waiting for answer
            if state.get("status") != "waiting_answer":
                return None

            correct_answer = state.get("answer", "").lower().strip()
            user_answer = text.lower().strip()

            # Check if answer is correct
            if user_answer != correct_answer:
                return None

            # Answer is correct, process reward
            # Get user
            user = await self.users.find_one({"id": user_id})
            if not user:
                return None

            # Try to withdraw from bank
            bank_doc = await self.bank.find_one({"_id": "main"})
            if not bank_doc:
                # Initialize bank if not exists
                bank_doc = {"_id": "main", "balance": 0.0}
                await self.bank.insert_one(bank_doc)

            bank_balance = bank_doc.get("balance", 0.0)
            reward_amount = self.QUIZ_REWARD

            # Check if bank has sufficient funds
            if bank_balance < reward_amount:
                # Insufficient funds in bank - still count as correct answer but don't transfer
                pass
            else:
                # Sufficient funds, process the transfer
                new_bank_balance = bank_balance - reward_amount
                new_user_balance = user.get("coins", 0.0) + reward_amount

                # Update bank balance
                await self.bank.update_one(
                    {"_id": "main"},
                    {"$set": {"balance": new_bank_balance}}
                )

                # Update user balance
                await self.users.update_one(
                    {"id": user_id},
                    {"$inc": {"coins": reward_amount}}
                )

                # Record transaction
                transaction_doc = {
                    "user_id": user_id,
                    "amount": reward_amount,
                    "type": "quiz_win",
                    "timestamp": datetime.now(timezone.utc)
                }
                await self.transactions.insert_one(transaction_doc)

                # Award ticket (1 ticket per 1000 coins won, based on exchange rate)
                from src.core.constants import EXCHANGE_COINS_TO_TICKET
                tickets_earned = int(reward_amount // EXCHANGE_COINS_TO_TICKET)
                if tickets_earned > 0:
                    ticket_doc = {
                        "user_id": user_id,
                        "amount": tickets_earned,
                        "source": "quiz",
                        "timestamp": datetime.now(timezone.utc)
                    }
                    await self.tickets.insert_one(ticket_doc)

            # Update quiz state - mark as answered and update stats
            used_questions = state.get("used_questions", [])
            current_question_id = state.get("current_question_id")
            if current_question_id and current_question_id not in used_questions:
                used_questions.append(current_question_id)

            # Update stats
            stats = state.get("stats", {
                "total_questions": 0,
                "total_coins": 0,
                "total_tickets": 0,
                "winners": {}
            })
            stats["total_questions"] = stats.get("total_questions", 0) + 1
            stats["total_coins"] = stats.get("total_coins", 0) + reward_amount

            # Update winners
            winners = stats.get("winners", {})
            winner_key = str(user_id)
            if winner_key not in winners:
                winners[winner_key] = {"name": user_name, "wins": 0, "coins": 0.0}
            winners[winner_key]["wins"] = winners[winner_key].get("wins", 0) + 1
            winners[winner_key]["coins"] = winners[winner_key].get("coins", 0.0) + reward_amount
            stats["winners"] = winners

            # Update quiz state
            await self.quiz_states.update_one(
                {"chat_id": chat_id},
                {"$set": {
                    "status": "answered",
                    "used_questions": used_questions,
                    "stats": stats,
                    "updated_at": datetime.now(timezone.utc)
                }}
            )

            # Return result
            return {
                "user_id": user_id,
                "reward": reward_amount,
                "balance": user.get("coins", 0.0) + (reward_amount if bank_doc.get("balance", 0.0) >= reward_amount else 0.0)
            }

    async def generate_summary(self, chat_id: int) -> str:
        """Генерировать итоги викторины."""
        state = await self.quiz_states.find_one({"chat_id": chat_id})
        if not state:
            return "Викторина не найдена."

        stats = state.get("stats", {
            "total_questions": 0,
            "total_coins": 0,
            "total_tickets": 0,
            "winners": {}
        })

        total_questions = stats.get("total_questions", 0)
        total_coins = stats.get("total_coins", 0)
        total_tickets = stats.get("total_tickets", 0)
        winners = stats.get("winners", {})

        summary_parts = [
            f"Итоги викторины",
            f"Вопросов: {total_questions}",
            f"Монет: {total_coins}",
            f"Билетов: {total_tickets}",
        ]

        if not winners:
            summary_parts.append("Никто не выиграл.")
        else:
            summary_parts.append("Топ победителей")

            # Sort winners by wins descending, then by coins descending
            sorted_winners = sorted(
                winners.items(),
                key=lambda x: (x[1].get("wins", 0), x[1].get("coins", 0)),
                reverse=True
            )

            for i, (user_id, user_data) in enumerate(sorted_winners[:3]):  # Top 3
                name = user_data.get("name", "Неизвестный")
                wins = user_data.get("wins", 0)
                summary_parts.append(f"{i+1}. {name} ({wins})")

        return "\n".join(summary_parts)