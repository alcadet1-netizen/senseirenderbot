"""
❓ Модель вопроса для викторины.
"""

from typing import Optional

from sqlalchemy import BigInteger, Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.infra.database.models.base import Base, TimestampMixin


class QuizQuestion(Base, TimestampMixin):
    """Модель вопроса викторины."""

    __tablename__ = "quiz_questions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(String(255), nullable=False)  # Правильный ответ
    image_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)  # Путь к файлу или file_id
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Метаданные (например, сложность, автор) можно добавить позже

    def __repr__(self) -> str:
        return f"<QuizQuestion(id={self.id}, text={self.question_text[:20]}...)>"
