# API уведомлений
import uuid
from fastapi import APIRouter, Depends
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.notification import Notification
from app.models.user import User
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/notifications", tags=["Уведомления"])


@router.get("")
async def list_notifications(limit: int = 50, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Получение последних уведомлений"""
    limit = min(max(limit, 1), 100)  # Cap: 1-100
    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
    )
    return [
        {
            "id": str(n.id), "title": n.title, "message": n.message or "",
            "type": n.type, "link": n.link, "is_read": n.is_read,
            "created_at": str(n.created_at),
        }
        for n in result.scalars().all()
    ]


@router.get("/unread-count")
async def unread_count(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(
        select(func.count(Notification.id)).where(Notification.user_id == user.id, Notification.is_read == False)
    )
    return {"count": result.scalar() or 0}


@router.put("/read-all")
async def read_all(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await db.execute(
        update(Notification).where(Notification.user_id == user.id, Notification.is_read == False).values(is_read=True)
    )
    await db.commit()
    return {"message": "Все уведомления прочитаны"}


@router.put("/{notification_id}/read")
async def read_one(notification_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(
        select(Notification).where(Notification.id == notification_id, Notification.user_id == user.id)
    )
    n = result.scalar_one_or_none()
    if n:
        n.is_read = True
        await db.commit()
    return {"message": "Прочитано"}
