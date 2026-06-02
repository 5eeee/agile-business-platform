# API ретроспектив
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.retrospective import Retrospective, RetrospectiveAnswer
from app.models.project import ProjectMember
from app.models.user import User
from app.schemas.event import RetrospectiveAnswerCreate, RetrospectiveOut
from app.middleware.auth import get_current_user
from app.dependencies import get_project_member_by_iteration

router = APIRouter(prefix="/retrospectives", tags=["Ретроспективы"])


@router.get("/{iteration_id}")
async def get_retrospective(
    iteration_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    _member: ProjectMember = Depends(get_project_member_by_iteration),
):
    """Получить ретроспективу итерации"""
    result = await db.execute(
        select(Retrospective)
        .options(selectinload(Retrospective.answers))
        .where(Retrospective.iteration_id == iteration_id)
    )
    retro = result.scalar_one_or_none()
    if not retro:
        raise HTTPException(status_code=404, detail="Ретроспектива не найдена")
    
    # Batch-fetch user names
    user_ids = {a.user_id for a in retro.answers}
    user_names = {}
    if user_ids:
        users_result = await db.execute(select(User.id, User.name).where(User.id.in_(user_ids)))
        user_names = {row.id: row.name for row in users_result.all()}
    
    answers = [
        {
            "id": str(a.id),
            "user_id": str(a.user_id),
            "user_name": user_names.get(a.user_id),
            "went_well": a.went_well,
            "to_improve": a.to_improve,
            "to_try": a.to_try,
            "created_at": str(a.created_at),
        }
        for a in retro.answers
    ]
    
    return RetrospectiveOut(
        id=retro.id, iteration_id=retro.iteration_id,
        answers=answers, created_at=retro.created_at,
    )


@router.post("/{iteration_id}/answer")
async def submit_answer(
    iteration_id: uuid.UUID, data: RetrospectiveAnswerCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    _member: ProjectMember = Depends(get_project_member_by_iteration),
):
    """Ответить на вопросы ретроспективы"""
    result = await db.execute(
        select(Retrospective).where(Retrospective.iteration_id == iteration_id)
    )
    retro = result.scalar_one_or_none()
    if not retro:
        raise HTTPException(status_code=404, detail="Ретроспектива не найдена")
    
    # Проверить, не отвечал ли уже
    existing = await db.execute(
        select(RetrospectiveAnswer).where(
            RetrospectiveAnswer.retrospective_id == retro.id,
            RetrospectiveAnswer.user_id == user.id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Вы уже ответили на ретроспективу")
    
    answer = RetrospectiveAnswer(
        retrospective_id=retro.id, user_id=user.id,
        went_well=data.went_well, to_improve=data.to_improve, to_try=data.to_try,
    )
    db.add(answer)
    await db.commit()
    return {"message": "Ответ сохранён"}


@router.put("/{iteration_id}/answer")
async def update_answer(
    iteration_id: uuid.UUID, data: RetrospectiveAnswerCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    _member: ProjectMember = Depends(get_project_member_by_iteration),
):
    """Обновить свой ответ на ретроспективу"""
    result = await db.execute(
        select(Retrospective).where(Retrospective.iteration_id == iteration_id)
    )
    retro = result.scalar_one_or_none()
    if not retro:
        raise HTTPException(status_code=404, detail="Ретроспектива не найдена")
    existing = await db.execute(
        select(RetrospectiveAnswer).where(
            RetrospectiveAnswer.retrospective_id == retro.id,
            RetrospectiveAnswer.user_id == user.id,
        )
    )
    answer = existing.scalar_one_or_none()
    if not answer:
        raise HTTPException(status_code=404, detail="Ответ не найден")
    answer.went_well = data.went_well
    answer.to_improve = data.to_improve
    answer.to_try = data.to_try
    await db.commit()
    return {"message": "Ответ обновлён"}
