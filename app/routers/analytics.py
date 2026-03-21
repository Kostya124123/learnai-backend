from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.security import require_hr
from app.models.user import User
from app.models.course import Enrollment, TestAttempt, Course
from app.schemas.course import AnalyticsOut

router = APIRouter(tags=["analytics"])


@router.get("/analytics/dashboard", response_model=AnalyticsOut)
async def dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_hr),
):
    # Total enrolled (unique users)
    enrolled_result = await db.execute(
        select(func.count(Enrollment.id))
    )
    total_enrolled = enrolled_result.scalar() or 0

    # Average score
    score_result = await db.execute(
        select(func.avg(TestAttempt.score)).where(TestAttempt.score > 0)
    )
    avg_raw = score_result.scalar() or 0
    avg_score = round(float(avg_raw), 1)

    # Courses generated
    courses_result = await db.execute(
        select(func.count(Course.id)).where(Course.status == "published")
    )
    courses_generated = courses_result.scalar() or 0

    # Incomplete enrollments
    incomplete_result = await db.execute(
        select(func.count(Enrollment.id)).where(Enrollment.status == "active")
    )
    incomplete_count = incomplete_result.scalar() or 0

    # Weak topics (stub data for now)
    weak_topics = [
        {"topic": "Действия при нарушении протокола", "score": 58},
        {"topic": "Классификация зон риска", "score": 65},
        {"topic": "Использование СИЗ", "score": 82},
    ]

    # Recent activity (stub)
    recent_activity = [
        {"date": "2025-01-10", "completions": 3},
        {"date": "2025-01-11", "completions": 5},
        {"date": "2025-01-12", "completions": 2},
        {"date": "2025-01-13", "completions": 7},
        {"date": "2025-01-14", "completions": 4},
    ]

    return AnalyticsOut(
        total_enrolled=total_enrolled,
        avg_score=avg_score,
        courses_generated=courses_generated,
        incomplete_count=incomplete_count,
        weak_topics=weak_topics,
        recent_activity=recent_activity,
    )
