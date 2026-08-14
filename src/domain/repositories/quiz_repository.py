from typing import List, Optional
from motor.motor_asyncio import AsyncIOMotorCollection
from bson import ObjectId


class QuizRepository:
    """Репозиторий для вопросов викторины."""

    def __init__(self, collection: AsyncIOMotorCollection):
        self.collection = collection

    async def delete_questions(self, question_ids: List[int]):
        """Удалить список вопросов по ID."""
        if not question_ids:
            return
        await self.collection.delete_many({"id": {"$in": question_ids}})

    async def get_random_question(self, exclude_ids: List[int] = None) -> Optional[dict]:
        """Получить случайный активный вопрос, исключая указанные ID."""
        match = {"is_active": True}
        if exclude_ids:
            match["id"] = {"$nin": exclude_ids}
        # Use aggregation with $sample for random
        pipeline = [
            {"$match": match},
            {"$sample": {"size": 1}}
        ]
        cursor = self.collection.aggregate(pipeline)
        result = await cursor.to_list(length=1)
        return result[0] if result else None

    async def add_question(self, question: str, answer: str, image_path: Optional[str] = None) -> dict:
        """Добавить новый вопрос."""
        # Determine next id
        last = await self.collection.find_one(sort=[("id", -1)])
        next_id = (last.get("id", 0) if last else 0) + 1
        quiz_question = {
            "id": next_id,
            "question_text": question,
            "answer": answer,
            "image_path": image_path,
            "is_active": True,
        }
        await self.collection.insert_one(quiz_question)
        return quiz_question