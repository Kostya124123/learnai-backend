from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.security import get_current_user, require_hr
from app.models.user import User
from app.models.course import Course, CourseModule, TestQuestion, Enrollment, CaseAnswer
from app.models.document import Document
from app.schemas.course import (
    CourseOut, CourseModuleOut, TestQuestionOut,
    GenerateCourseIn, EnrollmentOut, ProgressUpdate, DocumentOut
)
from app.services.llm_stub import generate_course_content
from app.services.document_service import save_upload, extract_text, chunk_text

router = APIRouter(tags=["courses"])


# Documents

@router.post("/documents/upload", response_model=DocumentOut)
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_hr),
):
    content = await file.read()
    file_path = await save_upload(content, file.filename)

    text = extract_text(file_path)
    chunks = chunk_text(text)

    doc = Document(
        filename=file.filename,
        file_path=file_path,
        uploaded_by=current_user.id,
        chunk_count=len(chunks),
        status="indexed" if text else "error",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc


@router.get("/documents", response_model=list[DocumentOut])
async def list_documents(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_hr),
):
    result = await db.execute(select(Document).order_by(Document.uploaded_at.desc()))
    return result.scalars().all()


@router.post("/reload_docs")
async def reload_docs(current_user: User = Depends(require_hr)):
    return {"status": "ok", "message": "База знаний обновлена"}


# Course generation

@router.post("/courses/generate", response_model=CourseOut)
async def generate_course(
    body: GenerateCourseIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_hr),
):
    doc_text = None
    if body.document_id:
        result = await db.execute(select(Document).where(Document.id == body.document_id))
        doc = result.scalar_one_or_none()
        if doc:
            try:
                doc_text = extract_text(doc.file_path)
            except Exception:
                doc_text = None

    # Generate content — await async LLM call
    content = await generate_course_content(body.title, doc_text)

    course = Course(
        title=body.title,
        description=f"Курс сгенерирован AI на основе: {body.title}",
        document_id=body.document_id,
        created_by=current_user.id,
        status="published",
    )
    db.add(course)
    await db.flush()

    for mod_data in content["modules"]:
        module = CourseModule(
            course_id=course.id,
            module_type=mod_data["module_type"],
            order_index=mod_data["order_index"],
            title=mod_data["title"],
            content=mod_data["content"],
        )
        db.add(module)
        await db.flush()

        if mod_data["module_type"] == "test" and "questions" in mod_data:
            for q in mod_data["questions"]:
                question = TestQuestion(
                    module_id=module.id,
                    question=q["question"],
                    options=q["options"],
                    correct_answer=q["correct_answer"],
                    points=q.get("points", 10),
                )
                db.add(question)

    await db.commit()
    await db.refresh(course)

    count_result = await db.execute(
        select(func.count()).where(CourseModule.course_id == course.id)
    )
    module_count = count_result.scalar()

    return CourseOut(
        id=course.id,
        title=course.title,
        description=course.description,
        status=course.status,
        generated_at=course.generated_at,
        module_count=module_count,
        document_id=course.document_id,
    )


# Course list & detail

@router.get("/courses", response_model=list[CourseOut])
async def list_courses(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_hr),
):
    result = await db.execute(
        select(Course).where(Course.status == "published").order_by(Course.generated_at.desc())
    )
    courses = result.scalars().all()
    out = []
    for c in courses:
        cnt = await db.execute(select(func.count()).where(CourseModule.course_id == c.id))
        out.append(CourseOut(
            id=c.id, title=c.title, description=c.description,
            status=c.status, generated_at=c.generated_at,
            module_count=cnt.scalar(), document_id=c.document_id,
        ))
    return out


@router.get("/courses/{course_id}/modules", response_model=list[CourseModuleOut])
async def get_modules(
    course_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(CourseModule)
        .where(CourseModule.course_id == course_id)
        .order_by(CourseModule.order_index)
    )
    return result.scalars().all()


@router.get("/modules/{module_id}")
async def get_module(
    module_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(CourseModule).where(CourseModule.id == module_id))
    mod = result.scalar_one_or_none()
    if not mod:
        raise HTTPException(404, "Module not found")
    return {"id": mod.id, "course_id": mod.course_id, "module_type": mod.module_type, "title": mod.title}


@router.get("/modules/{module_id}/tests", response_model=list[TestQuestionOut])
async def get_tests(
    module_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(TestQuestion).where(TestQuestion.module_id == module_id)
    )
    return result.scalars().all()


# Enrollments

@router.get("/enrollments/me", response_model=list[EnrollmentOut])
async def my_enrollments(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Enrollment, Course.title)
        .join(Course, Enrollment.course_id == Course.id)
        .where(Enrollment.user_id == current_user.id)
        .order_by(Enrollment.enrolled_at.desc())
    )
    rows = result.all()
    return [
        EnrollmentOut(
            id=e.id, course_id=e.course_id, course_title=title,
            enrolled_at=e.enrolled_at, status=e.status,
            progress_pct=e.progress_pct, last_score=e.last_score,
        )
        for e, title in rows
    ]


@router.get("/enrollments/all")
async def all_enrollments(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_hr),
):
    result = await db.execute(select(Enrollment))
    enrollments = result.scalars().all()
    return [{"id": e.id, "course_id": e.course_id, "user_id": e.user_id, "status": e.status} for e in enrollments]


@router.post("/enrollments/{course_id}")
async def enroll(
    course_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Enrollment).where(
            Enrollment.user_id == current_user.id,
            Enrollment.course_id == course_id
        )
    )
    if result.scalar_one_or_none():
        return {"status": "already enrolled"}

    enrollment = Enrollment(user_id=current_user.id, course_id=course_id)
    db.add(enrollment)
    await db.commit()
    return {"status": "enrolled"}


@router.patch("/enrollments/{enrollment_id}/progress")
async def update_progress(
    enrollment_id: int,
    body: ProgressUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Enrollment).where(
            Enrollment.id == enrollment_id,
            Enrollment.user_id == current_user.id,
        )
    )
    enrollment = result.scalar_one_or_none()
    if not enrollment:
        raise HTTPException(404, "Enrollment not found")

    enrollment.progress_pct = min(body.progress_pct, 100.0)
    if enrollment.progress_pct >= 100:
        enrollment.status = "completed"
    await db.commit()
    return {"status": "updated"}


@router.delete("/documents/{doc_id}")
async def delete_document(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_hr),
):
    from sqlalchemy import text
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(404, "Document not found")
    # Каскадное удаление через сырой SQL в правильном порядке
    await db.execute(text("""
        DELETE FROM test_attempts WHERE test_id IN (
            SELECT t.id FROM tests t
            JOIN course_modules cm ON t.module_id = cm.id
            JOIN courses c ON cm.course_id = c.id
            WHERE c.document_id = :doc_id)
    """), {"doc_id": doc_id})
    await db.execute(text("""
        DELETE FROM case_answers WHERE module_id IN (
            SELECT cm.id FROM course_modules cm
            JOIN courses c ON cm.course_id = c.id
            WHERE c.document_id = :doc_id)
    """), {"doc_id": doc_id})
    await db.execute(text("""
        DELETE FROM tests
        WHERE module_id IN (
            SELECT cm.id FROM course_modules cm
            JOIN courses c ON cm.course_id = c.id
            WHERE c.document_id = :doc_id
        )
    """), {"doc_id": doc_id})
    await db.execute(text("""
        DELETE FROM enrollments
        WHERE course_id IN (SELECT id FROM courses WHERE document_id = :doc_id)
    """), {"doc_id": doc_id})
    await db.execute(text("""
        DELETE FROM course_modules
        WHERE course_id IN (SELECT id FROM courses WHERE document_id = :doc_id)
    """), {"doc_id": doc_id})
    await db.execute(text("DELETE FROM courses WHERE document_id = :doc_id"), {"doc_id": doc_id})
    await db.execute(text("DELETE FROM documents WHERE id = :doc_id"), {"doc_id": doc_id})
    await db.commit()
    return {"status": "deleted"}


@router.delete("/courses/{course_id}")
async def delete_course(
    course_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_hr),
):
    from sqlalchemy import text
    await db.execute(text("DELETE FROM test_attempts WHERE test_id IN (SELECT id FROM tests WHERE module_id IN (SELECT id FROM course_modules WHERE course_id = :cid))"), {"cid": course_id})
    await db.execute(text("DELETE FROM case_answers WHERE module_id IN (SELECT id FROM course_modules WHERE course_id = :cid)"), {"cid": course_id})
    await db.execute(text("DELETE FROM tests WHERE module_id IN (SELECT id FROM course_modules WHERE course_id = :cid)"), {"cid": course_id})
    await db.execute(text("DELETE FROM enrollments WHERE course_id = :cid"), {"cid": course_id})
    await db.execute(text("DELETE FROM course_modules WHERE course_id = :cid"), {"cid": course_id})
    await db.execute(text("DELETE FROM courses WHERE id = :cid"), {"cid": course_id})
    await db.commit()
    return {"status": "deleted"}


@router.get("/users")
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_hr),
):
    result = await db.execute(
        select(User).order_by(User.full_name)
    )
    users = result.scalars().all()
    return [{"id": u.id, "full_name": u.full_name, "email": u.email, "role": u.role} for u in users]


@router.post("/enrollments/{course_id}/{user_id}")
async def enroll_user(
    course_id: int,
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_hr),
):
    result = await db.execute(
        select(Enrollment).where(
            Enrollment.user_id == user_id,
            Enrollment.course_id == course_id
        )
    )
    if result.scalar_one_or_none():
        return {"status": "already enrolled"}
    enrollment = Enrollment(user_id=user_id, course_id=course_id)
    db.add(enrollment)
    await db.commit()
    return {"status": "enrolled"}


# ── Case Answers ───────────────────────────────────────────────

@router.post("/case-answers")
async def submit_case_answer(
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models.course import CaseAnswer
    answer = CaseAnswer(
        user_id=current_user.id,
        module_id=body["module_id"],
        answer=body["answer"],
    )
    db.add(answer)
    await db.commit()
    await db.refresh(answer)
    return {"status": "submitted", "id": answer.id}


@router.get("/case-answers")
async def list_case_answers(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_hr),
):
    from app.models.course import CaseAnswer
    from app.models.user import User as UserModel
    result = await db.execute(
        select(CaseAnswer).order_by(CaseAnswer.created_at.desc())
    )
    answers = result.scalars().all()
    out = []
    for a in answers:
        user_res = await db.execute(select(UserModel).where(UserModel.id == a.user_id))
        user = user_res.scalar_one_or_none()
        mod_res = await db.execute(select(CourseModule).where(CourseModule.id == a.module_id))
        mod = mod_res.scalar_one_or_none()
        out.append({
            "id": a.id,
            "user_name": user.full_name if user else "—",
            "module_title": mod.title if mod else "—",
            "answer": a.answer,
            "score": a.score,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        })
    return out


@router.patch("/case-answers/{answer_id}/score")
async def score_case_answer(
    answer_id: int,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_hr),
):
    from app.models.course import CaseAnswer
    result = await db.execute(select(CaseAnswer).where(CaseAnswer.id == answer_id))
    answer = result.scalar_one_or_none()
    if not answer:
        raise HTTPException(404, "Answer not found")
    answer.score = body.get("score")
    await db.commit()
    return {"status": "scored"}
