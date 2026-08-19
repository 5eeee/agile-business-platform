"""Авторизованная выдача зашифрованных объектов из приватного хранилища."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.iteration import Iteration
from app.models.project import ProjectMember
from app.models.task import Task
from app.models.user import ADMIN_ROLES, User
from app.services.s3 import download_file_from_s3


router = APIRouter(prefix="/secure-files", tags=["Защищённые файлы"])


@router.get("/{file_path:path}")
async def get_secure_file(
    file_path: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    parts = file_path.strip("/").split("/")
    if len(parts) < 3 or parts[0] not in {"tasks", "documents", "chat"}:
        raise HTTPException(status_code=404, detail="Файл не найден")
    if user.role not in ADMIN_ROLES:
        try:
            parent_id = uuid.UUID(parts[1])
        except ValueError as exc:
            raise HTTPException(status_code=404, detail="Файл не найден") from exc
        if parts[0] == "tasks":
            task = await db.get(Task, parent_id)
            iteration_id = task.iteration_id if task else None
        else:
            iteration_id = parent_id
        iteration = await db.get(Iteration, iteration_id) if iteration_id else None
        if not iteration:
            raise HTTPException(status_code=404, detail="Файл не найден")
        membership = await db.scalar(
            select(ProjectMember.id).where(
                ProjectMember.project_id == iteration.project_id,
                ProjectMember.user_id == user.id,
            )
        )
        if not membership:
            raise HTTPException(status_code=403, detail="Нет доступа к файлу")
    content, content_type = download_file_from_s3(file_path)
    return Response(
        content=content,
        media_type=content_type,
        headers={
            "Cache-Control": "private, no-store",
            "Content-Security-Policy": "default-src 'none'; sandbox",
            "X-Content-Type-Options": "nosniff",
        },
    )
