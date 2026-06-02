# Общие зависимости (dependencies) для FastAPI
import uuid
from fastapi import Depends, HTTPException, status, Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.project import Project, ProjectMember, ProjectRole
from app.models.iteration import Iteration
from app.models.user import User, UserRole
from app.middleware.auth import get_current_user


async def get_project_member(
    project_id: uuid.UUID = Path(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectMember:
    """Проверка что пользователь является участником проекта.
    Администраторы сайта имеют доступ ко всем проектам."""
    if user.role == UserRole.ADMIN:
        # Проверяем что проект существует
        result = await db.execute(select(Project).where(Project.id == project_id, Project.is_deleted == False))
        project = result.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=404, detail="Проект не найден")
        # Возвращаем виртуального участника для админа
        return ProjectMember(
            project_id=project_id, user_id=user.id,
            is_admin=True, role=ProjectRole.OWNER,
        )

    result = await db.execute(
        select(ProjectMember)
        .join(Project)
        .where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user.id,
            Project.is_deleted == False,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=403, detail="Вы не являетесь участником этого проекта")
    return member


async def require_project_admin(
    member: ProjectMember = Depends(get_project_member),
) -> ProjectMember:
    """Требует роль owner/admin в проекте"""
    if member.role not in (ProjectRole.OWNER,) and not member.is_admin:
        raise HTTPException(status_code=403, detail="Требуются права администратора проекта")
    return member


async def get_project_member_by_iteration(
    iteration_id: uuid.UUID = Path(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectMember:
    """Проверка участия в проекте по iteration_id (для чата, документов и т.д.)"""
    result = await db.execute(
        select(Iteration).where(Iteration.id == iteration_id)
    )
    iteration = result.scalar_one_or_none()
    if not iteration:
        raise HTTPException(status_code=404, detail="Итерация не найдена")

    if user.role == UserRole.ADMIN:
        return ProjectMember(
            project_id=iteration.project_id, user_id=user.id,
            is_admin=True, role=ProjectRole.OWNER,
        )

    result = await db.execute(
        select(ProjectMember)
        .join(Project)
        .where(
            ProjectMember.project_id == iteration.project_id,
            ProjectMember.user_id == user.id,
            Project.is_deleted == False,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=403, detail="Вы не являетесь участником этого проекта")
    return member
