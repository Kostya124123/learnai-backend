from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.course import ChatHistory
from app.schemas.course import ChatIn, ChatOut, ChatMessageOut
from app.services.llm_stub import answer_question

router = APIRouter(tags=["chat"])


@router.post("/ask", response_model=ChatOut)
async def ask(
    body: ChatIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # TODO: replace with real RAG when model is ready
    result = answer_question(body.question)

    record = ChatHistory(
        user_id=current_user.id,
        question=body.question,
        answer=result["answer"],
        source=result["source"],
    )
    db.add(record)
    await db.commit()

    return ChatOut(answer=result["answer"], source=result["source"])


@router.get("/chat/history", response_model=list[ChatMessageOut])
async def chat_history(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ChatHistory)
        .where(ChatHistory.user_id == current_user.id)
        .order_by(ChatHistory.created_at.desc())
        .limit(50)
    )
    rows = result.scalars().all()
    messages = []
    for row in reversed(rows):
        messages.append(ChatMessageOut(
            id=row.id * 2 - 1,
            role="user",
            content=row.question,
            created_at=row.created_at,
        ))
        messages.append(ChatMessageOut(
            id=row.id * 2,
            role="assistant",
            content=row.answer,
            source=row.source,
            created_at=row.created_at,
        ))
    return messages
