from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.core.database import get_db
from app.core.security import get_current_user, require_hr
from app.models.user import User
from app.models.course import TestQuestion, TestAttempt, CourseModule
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

    # Проверяем — уже отвечал?
    existing = await db.execute(
        select(TestAttempt).where(
            TestAttempt.test_id == test_id,
            TestAttempt.user_id == current_user.id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Already answered")

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
    await db.flush()

    # Обновляем last_score в enrollment
    try:
        from app.models.course import Enrollment, CourseModule
        mod_res = await db.execute(
            select(CourseModule).where(CourseModule.id == question.module_id)
        )
        mod = mod_res.scalar_one_or_none()
        if mod:
            enr_res = await db.execute(
                select(Enrollment).where(
                    Enrollment.user_id == current_user.id,
                    Enrollment.course_id == mod.course_id
                )
            )
            enr = enr_res.scalar_one_or_none()
            if enr:
                # Считаем средний балл по всем вопросам курса
                from sqlalchemy import func
                total_q = await db.execute(
                    select(func.count(TestAttempt.id))
                    .join(TestQuestion, TestAttempt.test_id == TestQuestion.id)
                    .join(CourseModule, TestQuestion.module_id == CourseModule.id)
                    .where(TestAttempt.user_id == current_user.id, CourseModule.course_id == mod.course_id)
                )
                correct_q = await db.execute(
                    select(func.count(TestAttempt.id))
                    .join(TestQuestion, TestAttempt.test_id == TestQuestion.id)
                    .join(CourseModule, TestQuestion.module_id == CourseModule.id)
                    .where(TestAttempt.user_id == current_user.id, CourseModule.course_id == mod.course_id, TestAttempt.is_correct == True)
                )
                t = total_q.scalar() or 0
                c = correct_q.scalar() or 0
                if t > 0:
                    enr.last_score = round((c / t) * 100, 1)
    except Exception:
        pass

    await db.commit()

    return TestAttemptOut(
        test_id=test_id,
        answer=body.answer,
        is_correct=is_correct,
        score=score,
        correct_answer=question.correct_answer,
        explanation="Ответ верный!" if is_correct else f"Правильный ответ: «{question.correct_answer}»",
    )


@router.delete("/tests/reset/{user_id}/{course_id}")
async def reset_attempts(
    user_id: int,
    course_id: int,
    what: str = "all",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_hr),
):
    """HR сбрасывает попытки сотрудника по курсу. what: test | case | all"""
    from app.models.course import CaseAnswer
    if what in ("test", "all"):
        await db.execute(
            delete(TestAttempt).where(
                TestAttempt.user_id == user_id,
                TestAttempt.test_id.in_(
                    select(TestQuestion.id)
                    .join(CourseModule, TestQuestion.module_id == CourseModule.id)
                    .where(CourseModule.course_id == course_id)
                )
            )
        )
    if what in ("case", "all"):
        await db.execute(
            delete(CaseAnswer).where(
                CaseAnswer.user_id == user_id,
                CaseAnswer.module_id.in_(
                    select(CourseModule.id).where(CourseModule.course_id == course_id)
                )
            )
        )
    # Сбрасываем прогресс enrollment
    from app.models.course import Enrollment
    enr_res = await db.execute(
        select(Enrollment).where(
            Enrollment.user_id == user_id,
            Enrollment.course_id == course_id
        )
    )
    enr = enr_res.scalar_one_or_none()
    if enr:
        enr.progress_pct = 0.0
        enr.status = "active"
    await db.commit()
    return {"status": "reset", "what": what}
