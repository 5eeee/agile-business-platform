# API проектов
import uuid
from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.project import Project, ProjectMember, ProjectRole
from app.models.iteration import Iteration, IterationStatus
from app.models.board_column import BoardColumn
from app.models.user import User, UserRole, ADMIN_ROLES
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectMemberAdd, ProjectOut, ProjectMemberOut
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/projects", tags=["Проекты"])


@router.get("", response_model=list[ProjectOut])
async def list_projects(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Список проектов, доступных пользователю"""
    if user.role in ADMIN_ROLES:
        result = await db.execute(
            select(Project).where(Project.is_deleted == False).order_by(Project.created_at.desc())
        )
    else:
        result = await db.execute(
            select(Project)
            .join(ProjectMember, ProjectMember.project_id == Project.id)
            .where(ProjectMember.user_id == user.id, Project.is_deleted == False)
            .order_by(Project.created_at.desc())
        )
    return [ProjectOut.model_validate(p) for p in result.scalars().all()]


@router.get("/archived/list", response_model=list[ProjectOut])
async def list_archived_projects(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Список архивированных проектов"""
    if user.role in ADMIN_ROLES:
        result = await db.execute(
            select(Project).where(Project.is_deleted == True).order_by(Project.updated_at.desc())
        )
    else:
        result = await db.execute(
            select(Project)
            .join(ProjectMember, ProjectMember.project_id == Project.id)
            .where(ProjectMember.user_id == user.id, Project.is_deleted == True)
            .order_by(Project.updated_at.desc())
        )
    return [ProjectOut.model_validate(p) for p in result.scalars().all()]


@router.get("/{project_id}")
async def get_project(project_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Детали проекта с участниками"""
    result = await db.execute(
        select(Project).options(selectinload(Project.members)).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")
    # Verify project membership
    if user.role not in ADMIN_ROLES:
        member_result = await db.execute(
            select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.user_id == user.id)
        )
        if not member_result.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Вы не являетесь участником этого проекта")

    member_user_ids = [m.user_id for m in project.members]
    user_map: dict[uuid.UUID, User] = {}
    if member_user_ids:
        users_result = await db.execute(select(User).where(User.id.in_(member_user_ids)))
        user_map = {u.id: u for u in users_result.scalars().all()}

    members = []
    for m in project.members:
        u = user_map.get(m.user_id)
        members.append(ProjectMemberOut(
            id=m.id,
            user_id=m.user_id,
            user_name=u.name if u else None,
            is_admin=m.is_admin,
            role=getattr(m, 'role', None) or 'member',
            joined_at=m.joined_at
        ))
    
    return {
        **ProjectOut.model_validate(project).model_dump(),
        "members": [m.model_dump() for m in members],
    }


@router.post("", response_model=ProjectOut, status_code=201)
async def create_project(data: ProjectCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Создание проекта"""
    project = Project(name=data.name, description=data.description, creator_id=user.id)
    db.add(project)
    await db.flush()
    
    # Создатель — владелец проекта
    member = ProjectMember(project_id=project.id, user_id=user.id, is_admin=True, role=ProjectRole.OWNER)
    db.add(member)

    # Стартовая доска: итерация + первая колонка
    today = date.today()
    default_iteration = Iteration(
        project_id=project.id,
        name="Итерация 1",
        start_date=today,
        end_date=today + timedelta(days=13),
        status=IterationStatus.ACTIVE,
        sort_order=0,
    )
    db.add(default_iteration)
    await db.flush()

    default_column = BoardColumn(
        iteration_id=default_iteration.id,
        title="Колонка 1",
        sort_order=0,
    )
    db.add(default_column)

    await db.commit()
    await db.refresh(project)
    from app.services.realtime import notify_project_watchers
    await notify_project_watchers(db, project.id)
    return ProjectOut.model_validate(project)


@router.put("/{project_id}", response_model=ProjectOut)
async def update_project(project_id: uuid.UUID, data: ProjectUpdate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Редактирование проекта"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")
    
    # Проверка прав: админ сайта или админ проекта
    if user.role not in ADMIN_ROLES:
        member_result = await db.execute(
            select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.user_id == user.id, ProjectMember.is_admin == True)
        )
        if not member_result.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Нет прав на редактирование проекта")
    
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(project, key, value)
    
    await db.commit()
    await db.refresh(project)
    from app.services.realtime import notify_project_watchers
    await notify_project_watchers(db, project_id)
    return ProjectOut.model_validate(project)


@router.post("/{project_id}/archive")
async def archive_project(project_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Архивировать проект (скрыть из основного списка, данные сохраняются). Только администратор."""
    if user.role not in ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Только администратор может архивировать проекты")

    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")
    if project.is_deleted:
        raise HTTPException(status_code=400, detail="Проект уже в архиве")

    project.is_deleted = True
    await db.commit()
    from app.services.realtime import notify_project_watchers
    await notify_project_watchers(db, project_id)
    return {"message": "Проект помещён в архив"}


@router.delete("/{project_id}")
async def delete_project(project_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Безвозвратное удаление проекта и связанных данных (итерации, задачи, участники и т.д.). Только администратор."""
    if user.role not in ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Только администратор может удалять проекты")

    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")

    await db.delete(project)
    await db.commit()
    from app.services.realtime import notify_project_watchers
    await notify_project_watchers(db, project_id)
    return {"message": "Проект удалён безвозвратно"}


@router.post("/{project_id}/restore")
async def restore_project(project_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Восстановление архивированного проекта"""
    if user.role not in ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Только администратор может восстанавливать проекты")

    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")
    if not project.is_deleted:
        raise HTTPException(status_code=400, detail="Проект не в архиве")

    project.is_deleted = False
    await db.commit()
    from app.services.realtime import notify_project_watchers
    await notify_project_watchers(db, project_id)
    return {"message": "Проект восстановлен"}


@router.post("/{project_id}/members")
async def add_member(project_id: uuid.UUID, data: ProjectMemberAdd, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Добавление участника в проект (только админ проекта)"""
    # Проверка прав
    if user.role not in ADMIN_ROLES:
        member_result = await db.execute(
            select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.user_id == user.id, ProjectMember.is_admin == True)
        )
        if not member_result.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Только администратор проекта может добавлять участников")
    
    # Проверка, не добавлен ли уже
    existing = await db.execute(
        select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.user_id == data.user_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Пользователь уже в проекте")
    
    member = ProjectMember(project_id=project_id, user_id=data.user_id, is_admin=data.is_admin, role=data.role)
    db.add(member)
    await db.commit()
    from app.services.realtime import notify_project_watchers
    await notify_project_watchers(db, project_id)
    return {"message": "Участник добавлен"}


@router.delete("/{project_id}/members/{user_id}")
async def remove_member(project_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Удаление участника из проекта"""
    if user.role not in ADMIN_ROLES:
        member_result = await db.execute(
            select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.user_id == user.id, ProjectMember.is_admin == True)
        )
        if not member_result.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Только администратор проекта может удалять участников")
    
    result = await db.execute(
        select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id)
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Участник не найден")
    
    await db.delete(member)
    await db.commit()
    from app.services.realtime import notify_project_watchers
    await notify_project_watchers(db, project_id)
    return {"message": "Участник удалён"}
