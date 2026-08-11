from typing import List, Optional
from sqlalchemy import select, func, delete
from src.domain.repositories.base import BaseRepository
from src.infra.database.models.quiz import QuizQuestion


class QuizRepository(BaseRepository[QuizQuestion, int]):
    """Репозиторий для вопросов викторины."""
    
    def __init__(self, session):
        super().__init__(session, QuizQuestion)

    async def delete_questions(self, question_ids: List[int]):
        """Удалить список вопросов по ID."""
        if not question_ids:
            return
        stmt = delete(self.model).where(self.model.id.in_(question_ids))
        await self.session.execute(stmt)

    async def get_random_question(self, exclude_ids: List[int] = None) -> Optional[QuizQuestion]:
        """Получить случайный активный вопрос, исключая указанные ID."""
        stmt = select(self.model).where(self.model.is_active == True)
        
        if exclude_ids:
            stmt = stmt.where(self.model.id.not_in(exclude_ids))
            
        stmt = stmt.order_by(func.random()).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def add_question(self, question: str, answer: str, image_path: Optional[str] = None) -> QuizQuestion:
        """Добавить новый вопрос."""
        q = QuizQuestion(
            question_text=question,
            answer=answer,
            image_path=image_path,
            is_active=True
        )
        self.session.add(q)
        # Flush чтобы получить ID, но не коммитить (коммит в сервисе/UoW)
        await self.session.flush() 
        return q
