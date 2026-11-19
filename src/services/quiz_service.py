"""
🧠 Сервис викторины.
"""

import asyncio
import copy
import math
from decimal import Decimal
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
from src.services.bank_ledger import BankLedger, _matched, _valid
from src.services.referral_economy import transaction

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
        self.bank = self.db.bank  # legacy/useful bank collection
        self.ledger = BankLedger(mongo_client)
        self.tickets = self.db.tickets  # For ticket tracking
        # Locks for concurrency control - we'll use asyncio.Lock per chat for simplicity
        self._chat_locks = {}
        self._loop_locks = {}
        self._lock = asyncio.Lock()  # Lock for managing the _chat_locks dict

    async def _get_chat_lock(self, chat_id: int) -> asyncio.Lock:
        """Get or create a lock for a specific chat."""
        async with self._lock:
            if chat_id not in self._chat_locks:
                self._chat_locks[chat_id] = asyncio.Lock()
            return self._chat_locks[chat_id]

    async def run_quiz_loop(self, chat_id: int, bot):
        """Цикл викторины."""
        # The long-running question loop must not hold the answer lock while
        # waiting for players; otherwise check_answer can never run.
        async with self._lock:
            loop_lock = self._loop_locks.setdefault(chat_id, asyncio.Lock())
        if loop_lock.locked():
            return
        async with loop_lock:
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

    async def _get_quiz_state(self, chat_id: int) -> Optional[Dict]:
        """Получить состояние викторины для чата."""
        return await self.quiz_states.find_one({"chat_id": chat_id})

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
        """Settle one correct answer, bank payout, stats and journal together."""
        from src.core.constants import EXCHANGE_COINS_TO_TICKET

        chat_lock = await self._get_chat_lock(chat_id)
        async with chat_lock:
            async def settle(tx):
                state = await self.quiz_states.find_one({'chat_id': chat_id}, session=tx)
                if not state or state.get('status') != 'waiting_answer':
                    return None
                if text.lower().strip() != state.get('answer', '').lower().strip():
                    return None
                user = await self.users.find_one({'id': user_id}, session=tx)
                if not user:
                    return None
                accounts = []
                for bank_id, field in (('single', 'coins'), ('main', 'balance')):
                    doc = await self.bank.find_one({'_id': bank_id}, session=tx)
                    if not _valid(doc, bank_id, field):
                        continue
                    balance = float(doc.get(field, 0) or 0)
                    if not math.isfinite(balance) or balance < 0:
                        raise ValueError('Invalid quiz bank balance')
                    accounts.append((bank_id, field, Decimal(str(balance))))
                if not accounts:
                    raise RuntimeError('Quiz bank account is missing')
                reward = Decimal(str(self.QUIZ_REWARD))
                paid = sum((item[2] for item in accounts), Decimal(0)) >= reward
                amount = float(reward) if paid else 0.0
                if paid:
                    remaining = reward
                    for bank_id, field, balance in accounts:
                        take = min(remaining, balance)
                        if take <= 0:
                            continue
                        debit = await self.bank.update_one({'_id': bank_id, field: {'$gte': float(take)}},
                            {'$inc': {field: -float(take)}}, session=tx)
                        if not _matched(debit):
                            raise RuntimeError('Quiz bank debit missed')
                        remaining -= take
                    if remaining:
                        raise RuntimeError('Quiz bank withdrawal incomplete')
                    credit = await self.users.update_one({'id': user_id}, {'$inc': {'coins': amount}}, session=tx)
                    if not _matched(credit):
                        raise RuntimeError('Quiz winner missing')
                    await self.transactions.insert_one({'user_id': user_id, 'amount': amount,
                        'type': 'quiz_win', 'timestamp': datetime.now(timezone.utc)}, session=tx)
                tickets_earned = int(amount // EXCHANGE_COINS_TO_TICKET)
                if tickets_earned:
                    await self.tickets.insert_one({'user_id': user_id, 'amount': tickets_earned,
                        'source': 'quiz', 'timestamp': datetime.now(timezone.utc)}, session=tx)
                used = copy.deepcopy(state.get('used_questions', []))
                question_id = state.get('current_question_id')
                if question_id and question_id not in used:
                    used.append(question_id)
                stats = copy.deepcopy(state.get('stats') or {})
                stats['total_questions'] = stats.get('total_questions', 0) + 1
                stats['total_coins'] = stats.get('total_coins', 0) + amount
                stats['total_tickets'] = stats.get('total_tickets', 0) + tickets_earned
                winners = stats.get('winners', {})
                winner = winners.setdefault(str(user_id), {'name': user_name, 'wins': 0, 'coins': 0.0})
                winner['wins'] = winner.get('wins', 0) + 1
                winner['coins'] = winner.get('coins', 0.0) + amount
                stats['winners'] = winners
                changed = await self.quiz_states.update_one(
                    {'chat_id': chat_id, 'status': 'waiting_answer', 'current_question_id': question_id,
                     'round': state.get('round')},
                    {'$set': {'status': 'answered', 'used_questions': used, 'stats': stats,
                              'updated_at': datetime.now(timezone.utc)}}, session=tx)
                if not _matched(changed):
                    raise RuntimeError('Quiz question changed')
                return {'user_id': user_id, 'reward': amount, 'tickets': tickets_earned,
                        'balance': user.get('coins', 0.0) + amount}
            return await transaction(self.mongo_client, settle)

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