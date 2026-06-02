# API итераций
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.iteration import Iteration, IterationStatus, IterationTemplate, IterationTemplateTask
from app.models.board_column import BoardColumn
from app.models.task import Task
from app.models.project import ProjectMember
from app.models.retrospective import Retrospective
from app.models.user import User, UserRole
from app.schemas.iteration import IterationCreate, IterationUpdate, IterationOut
from app.schemas.board_column import BoardColumnCreate, BoardColumnOut
from app.middleware.auth import get_current_user
from app.dependencies import get_project_member, get_project_member_by_iteration

router = APIRouter(prefix="/iterations", tags=["Итерации"])


@router.get("/project/{project_id}", response_model=list[IterationOut])
async def list_iterations(
    project_id: uuid.UUID,
    include_archived: bool = False,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    _member: ProjectMember = Depends(get_project_member),
):
    """Список итераций проекта (архивные скрыты по умолчанию)"""
    query = select(Iteration).where(Iteration.project_id == project_id)
    if not include_archived:
        query = query.where(Iteration.status != IterationStatus.ARCHIVED)
    query = query.order_by(Iteration.sort_order, Iteration.start_date.desc())
    
    result = await db.execute(query)
    return [IterationOut.model_validate(i) for i in result.scalars().all()]


@router.get("/{iteration_id}/board-columns", response_model=list[BoardColumnOut])
async def list_board_columns(
    iteration_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    _member: ProjectMember = Depends(get_project_member_by_iteration),
):
    result = await db.execute(
        select(BoardColumn).where(BoardColumn.iteration_id == iteration_id).order_by(BoardColumn.sort_order, BoardColumn.created_at)
    )
    return [BoardColumnOut.model_validate(c) for c in result.scalars().all()]


@router.post("/{iteration_id}/board-columns", response_model=BoardColumnOut, status_code=201)
async def create_board_column(
    iteration_id: uuid.UUID,
    data: BoardColumnCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    _member: ProjectMember = Depends(get_project_member_by_iteration),
):
    col = BoardColumn(iteration_id=iteration_id, title=data.title.strip(), sort_order=data.sort_order)
    db.add(col)
    await db.commit()
    await db.refresh(col)
    return BoardColumnOut.model_validate(col)


@router.delete("/{iteration_id}/board-columns/{column_id}")
async def delete_board_column(
    iteration_id: uuid.UUID,
    column_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    _member: ProjectMember = Depends(get_project_member_by_iteration),
):
    result = await db.execute(
        select(BoardColumn).where(BoardColumn.id == column_id, BoardColumn.iteration_id == iteration_id)
    )
    col = result.scalar_one_or_none()
    if not col:
        raise HTTPException(status_code=404, detail="Колонка не найдена")
    roots = await db.execute(
        select(Task).where(Task.board_column_id == column_id, Task.parent_id.is_(None))
    )
    if roots.scalars().first():
        raise HTTPException(status_code=400, detail="В колонке есть задачи — удалите или перенесите их")
    await db.delete(col)
    await db.commit()
    return {"message": "Колонка удалена"}


@router.get("/{iteration_id}", response_model=IterationOut)
async def get_iteration(iteration_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Iteration).where(Iteration.id == iteration_id))
    iteration = result.scalar_one_or_none()
    if not iteration:
        raise HTTPException(status_code=404, detail="Итерация не найдена")
    # Verify project membership
    if user.role != UserRole.ADMIN:
        member_result = await db.execute(
            select(ProjectMember).where(ProjectMember.project_id == iteration.project_id, ProjectMember.user_id == user.id)
        )
        if not member_result.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Вы не являетесь участником этого проекта")
    return IterationOut.model_validate(iteration)


@router.post("", response_model=IterationOut, status_code=201)
async def create_iteration(data: IterationCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Создание итерации (с возможностью выбора шаблона)"""
    # Verify project membership
    if user.role != UserRole.ADMIN:
        member_result = await db.execute(
            select(ProjectMember).where(ProjectMember.project_id == data.project_id, ProjectMember.user_id == user.id)
        )
        if not member_result.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Вы не являетесь участником этого проекта")
    
    iteration = Iteration(
        project_id=data.project_id,
        name=data.name,
        start_date=data.start_date,
        end_date=data.end_date,
        template_name=data.template_name,
    )
    db.add(iteration)
    await db.flush()
    
    # Если указан шаблон — создать типовые задачи
    if data.template_name:
        tmpl_result = await db.execute(
            select(IterationTemplate)
            .options(selectinload(IterationTemplate.tasks))
            .where(IterationTemplate.name == data.template_name)
        )
        template = tmpl_result.scalar_one_or_none()
        if template:
            default_col = BoardColumn(iteration_id=iteration.id, title="Задачи", sort_order=0)
            db.add(default_col)
            await db.flush()
            for t in template.tasks:
                task = Task(
                    iteration_id=iteration.id,
                    title=t.title,
                    description=t.description,
                    priority=t.priority,
                    creator_id=user.id,
                    board_column_id=default_col.id,
                    is_completed=False,
                )
                db.add(task)
    
    await db.commit()
    await db.refresh(iteration)
    return IterationOut.model_validate(iteration)


@router.put("/{iteration_id}", response_model=IterationOut)
async def update_iteration(iteration_id: uuid.UUID, data: IterationUpdate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Iteration).where(Iteration.id == iteration_id))
    iteration = result.scalar_one_or_none()
    if not iteration:
        raise HTTPException(status_code=404, detail="Итерация не найдена")
    # Verify project membership
    if user.role != UserRole.ADMIN:
        member_result = await db.execute(
            select(ProjectMember).where(ProjectMember.project_id == iteration.project_id, ProjectMember.user_id == user.id)
        )
        if not member_result.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Вы не являетесь участником этого проекта")
    
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(iteration, key, value)
    
    await db.commit()
    await db.refresh(iteration)
    return IterationOut.model_validate(iteration)


@router.post("/{iteration_id}/complete")
async def complete_iteration(iteration_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Завершение итерации с автоматическим предложением ретроспективы"""
    result = await db.execute(select(Iteration).where(Iteration.id == iteration_id))
    iteration = result.scalar_one_or_none()
    if not iteration:
        raise HTTPException(status_code=404, detail="Итерация не найдена")
    # Verify project membership
    if user.role != UserRole.ADMIN:
        member_result = await db.execute(
            select(ProjectMember).where(ProjectMember.project_id == iteration.project_id, ProjectMember.user_id == user.id)
        )
        if not member_result.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Вы не являетесь участником этого проекта")
    
    if iteration.status != IterationStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Только активную итерацию можно завершить")
    
    iteration.status = IterationStatus.COMPLETED
    
    # Создаём ретроспективу только если ещё нет
    existing_retro = await db.execute(
        select(Retrospective).where(Retrospective.iteration_id == iteration.id)
    )
    if existing_retro.scalar_one_or_none():
        await db.commit()
        return {"message": "Итерация завершена (ретроспектива уже существует)"}
    
    retro = Retrospective(iteration_id=iteration.id)
    db.add(retro)
    
    await db.commit()
    return {"message": "Итерация завершена", "retrospective_id": str(retro.id)}


@router.post("/{iteration_id}/archive")
async def archive_iteration(iteration_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Архивация завершённой итерации"""
    result = await db.execute(select(Iteration).where(Iteration.id == iteration_id))
    iteration = result.scalar_one_or_none()
    if not iteration:
        raise HTTPException(status_code=404, detail="Итерация не найдена")
    # Verify project membership
    if user.role != UserRole.ADMIN:
        member_result = await db.execute(
            select(ProjectMember).where(ProjectMember.project_id == iteration.project_id, ProjectMember.user_id == user.id)
        )
        if not member_result.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Вы не являетесь участником этого проекта")
    
    if iteration.status != IterationStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Можно архивировать только завершённую итерацию")
    
    iteration.status = IterationStatus.ARCHIVED
    await db.commit()
    return {"message": "Итерация в архиве"}


@router.delete("/{iteration_id}")
async def delete_iteration(iteration_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Iteration).where(Iteration.id == iteration_id))
    iteration = result.scalar_one_or_none()
    if not iteration:
        raise HTTPException(status_code=404, detail="Итерация не найдена")
    if user.role != UserRole.ADMIN:
        member_result = await db.execute(
            select(ProjectMember).where(ProjectMember.project_id == iteration.project_id, ProjectMember.user_id == user.id)
        )
        if not member_result.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Вы не являетесь участником этого проекта")
    await db.delete(iteration)
    await db.commit()
    return {"message": "Итерация удалена"}


@router.patch("/project/{project_id}/reorder")
async def reorder_iterations(
    project_id: uuid.UUID,
    items: list[dict],
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    _member: ProjectMember = Depends(get_project_member),
):
    for item in items:
        iter_id = item.get("id")
        sort_order = item.get("sort_order", 0)
        if iter_id is not None:
            result = await db.execute(select(Iteration).where(Iteration.id == uuid.UUID(str(iter_id)), Iteration.project_id == project_id))
            iteration = result.scalar_one_or_none()
            if iteration:
                iteration.sort_order = sort_order
    await db.commit()
    return {"message": "ok"}


# --- Шаблоны итераций ---

@router.get("/templates/list")
async def list_templates(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(
        select(IterationTemplate).options(selectinload(IterationTemplate.tasks))
    )
    templates = result.scalars().all()
    return [
        {
            "id": str(t.id),
            "name": t.name,
            "sphere": t.sphere,
            "tasks": [{"title": task.title, "description": task.description, "priority": task.priority} for task in t.tasks],
        }
        for t in templates
    ]
