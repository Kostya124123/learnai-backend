from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.course import TestQuestion, TestAttempt
from app.schemas.course import TestAttemptIn, TestAttemptOut

router = APIRouter(tags=["tests"])


@router.post("/tests/{test_id}/attempt", response_model=TestAttemptOut)
async def submit_answer(
    test_id: int,
    body: TestAttemptIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(TestQuestion).where(TestQuestion.id == test_id))
    question = result.scalar_one_or_none()
    if not question:
        raise HTTPException(404, "Question not found")

    is_correct = body.answer.strip().lower() == question.correct_answer.strip().lower()
    score = question.points if is_correct else 0

    attempt = TestAttempt(
        user_id=current_user.id,
        test_id=test_id,
        answer=body.answer,
        is_correct=is_correct,
        score=score,
    )
    db.add(attempt)
    await db.commit()

    return TestAttemptOut(
        test_id=test_id,
        answer=body.answer,
        is_correct=is_correct,
        score=score,
        correct_answer=question.correct_answer,
        explanation="Ответ верный!" if is_correct else f"Правильный ответ: «{question.correct_answer}»",
    )
