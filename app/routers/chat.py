from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.course import ChatHistory
from app.models.document import Document
from app.schemas.course import ChatIn, ChatOut, ChatMessageOut
from app.services.llm_stub import answer_question

router = APIRouter(tags=["chat"])

@router.post("/ask", response_model=ChatOut)
async def ask(
    body: ChatIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Получаем контекст из загруженных документов (RAG)
    context = ""
    try:
        docs_result = await db.execute(
            select(Document).where(Document.status == "indexed").limit(3)
        )
        docs = docs_result.scalars().all()
        if docs:
            import os
            chunks = []
            for d in docs:
                try:
                    if os.path.exists(d.file_path):
                        with open(d.file_path, "r", encoding="utf-8") as f:
                            text = f.read()[:3000]  # Лимит на документ
                        chunks.append(f"--- Документ: {d.filename} ---\n{text}")
                except Exception:
                    pass
            if chunks:
                context = "\n\n".join(chunks)
    except Exception:
        pass

    # Вызываем LLM с await
    result = await answer_question(body.question, context)

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


@router.delete("/chat/history")
async def clear_chat_history(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy import delete as sql_delete
    await db.execute(
        sql_delete(ChatHistory).where(ChatHistory.user_id == current_user.id)
    )
    await db.commit()
    return {"status": "cleared"}
