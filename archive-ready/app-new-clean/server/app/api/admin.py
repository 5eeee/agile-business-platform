# API администрирования
import uuid
import secrets
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.user import User, UserRole, UserStatus, UserSphereRole
from app.models.project import Project
from app.schemas.user import (
    UserAdminOut, AdminUserUpdate, UserSphereRoleCreate, UserFireRequest
)
from app.middleware.auth import require_admin
from app.api.auth import hash_password
from app.config import SPHERES, SPHERE_ROLE_TEMPLATES
from app.services.telegram import notify_admin, notify_user_approved, notify_user_rejected, notify_user_fired
from app.services.email import send_decision_email

router = APIRouter(prefix="/admin", tags=["Администрирование"])


@router.get("/users", response_model=list[UserAdminOut])
async def list_all_users(db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    """Список всех пользователей (для админки)"""
    result = await db.execute(
        select(User).where(User.status != UserStatus.BLOCKED)
        .options(selectinload(User.sphere_roles)).order_by(User.created_at.desc())
    )
    return [UserAdminOut.model_validate(u) for u in result.scalars().all()]


@router.get("/users/pending", response_model=list[UserAdminOut])
async def list_pending_users(db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    """Заявки на модерации"""
    result = await db.execute(
        select(User).where(User.status == UserStatus.PENDING)
        .options(selectinload(User.sphere_roles))
        .order_by(User.created_at.desc())
    )
    return [UserAdminOut.model_validate(u) for u in result.scalars().all()]


@router.post("/users/{user_id}/approve")
async def approve_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    """Одобрить пользователя"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    user.status = UserStatus.ACTIVE
    # При одобрении считаем email подтвержденным, чтобы пользователь мог войти.
    user.email_confirmed = True
    await db.commit()
    # Telegram
    if user.telegram_id:
        await notify_user_approved(user.telegram_id, user.name)
    # Email
    await send_decision_email(user.email, user.name, approved=True)
    return {"message": f"Пользователь {user.name} одобрен"}


@router.post("/users/{user_id}/reject")
async def reject_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    """Отклонить пользователя"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    user.status = UserStatus.REJECTED
    await db.commit()
    # Telegram
    if user.telegram_id:
        await notify_user_rejected(user.telegram_id, user.name)
    # Email
    await send_decision_email(user.email, user.name, approved=False)
    return {"message": f"Пользователь {user.name} отклонён"}


@router.put("/users/{user_id}")
async def update_user(user_id: uuid.UUID, data: AdminUserUpdate, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    """Редактирование пользователя (админ)"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if key == "role" and value:
            setattr(user, key, UserRole(value))
        elif key == "status" and value:
            setattr(user, key, UserStatus(value))
        elif key == "training_role":
            # None, "intern", "training_editor"
            if value and value not in ("intern", "training_editor"):
                raise HTTPException(400, "training_role должен быть intern, training_editor или null")
            setattr(user, key, value or None)
        else:
            setattr(user, key, value)
    
    await db.commit()
    return {"message": "Пользователь обновлён"}


@router.delete("/users/{user_id}")
async def delete_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    """Удалить пользователя"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    if user.role == UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Нельзя удалить администратора")
    
    user.status = UserStatus.BLOCKED
    await db.commit()
    return {"message": "Пользователь удалён"}


@router.post("/users/{user_id}/fire")
async def fire_user(user_id: uuid.UUID, data: UserFireRequest, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    """Уволить пользователя — при входе показывается всплывающее окно"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    if user.role == UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Нельзя уволить администратора")
    
    user.status = UserStatus.FIRED
    user.fire_message = data.fire_message or "Чемодан, вокзал, НАХУЙ"
    await db.commit()
    # Telegram
    if user.telegram_id:
        await notify_user_fired(user.telegram_id, user.name, user.fire_message)
    return {"message": f"Пользователь {user.name} уволен"}


@router.put("/fire-message/{user_id}")
async def update_fire_message(user_id: uuid.UUID, data: UserFireRequest, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    """Изменить текст сообщения при увольнении"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    user.fire_message = data.fire_message
    await db.commit()
    return {"message": "Сообщение при увольнении обновлено"}


@router.post("/reset-password/{user_id}")
async def reset_password(user_id: uuid.UUID, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    """Сброс пароля пользователя (устанавливает 'password123')"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    new_password = secrets.token_urlsafe(12)
    user.password_hash = hash_password(new_password)
    await db.commit()
    return {"message": "Пароль сброшен. Новый пароль отправлен пользователю."}


# --- Роли в сферах ---

@router.get("/spheres")
async def get_spheres():
    """Список всех сфер и шаблонов ролей"""
    return {"spheres": SPHERES, "role_templates": SPHERE_ROLE_TEMPLATES}


@router.post("/users/{user_id}/sphere-roles")
async def assign_sphere_role(user_id: uuid.UUID, data: UserSphereRoleCreate, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    """Назначить роль пользователю внутри сферы"""
    sphere = data.sphere if hasattr(data, 'sphere') else None
    role_title = data.role_title if hasattr(data, 'role_title') else None
    target_user_id = user_id  # user_id from path takes priority
    
    if sphere not in SPHERES:
        raise HTTPException(status_code=400, detail="Неизвестная сфера")
    
    # Удалить старую роль в этой сфере, если есть
    result = await db.execute(
        select(UserSphereRole).where(
            UserSphereRole.user_id == target_user_id,
            UserSphereRole.sphere == sphere
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        existing.role_title = role_title
    else:
        role = UserSphereRole(
            user_id=target_user_id,
            sphere=sphere,
            role_title=role_title,
        )
        db.add(role)
    
    await db.commit()
    return {"message": "Роль назначена"}


@router.delete("/sphere-roles/{role_id}")
async def remove_sphere_role(role_id: uuid.UUID, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    """Удалить роль из сферы"""
    result = await db.execute(select(UserSphereRole).where(UserSphereRole.id == role_id))
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="Роль не найдена")
    
    await db.delete(role)
    await db.commit()
    return {"message": "Роль удалена"}


@router.get("/stats")
async def admin_stats(db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    """Статистика для дашборда админки"""
    # Try Redis cache (30s TTL)
    try:
        from app.services.redis import get_redis
        import json
        r = await get_redis()
        cached = await r.get("admin:stats")
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    total_users = await db.execute(select(func.count(User.id)))
    active_users = await db.execute(select(func.count(User.id)).where(User.status == UserStatus.ACTIVE))
    pending_users = await db.execute(select(func.count(User.id)).where(User.status == UserStatus.PENDING))
    total_projects = await db.execute(select(func.count(Project.id)).where(Project.is_deleted == False))
    
    result = {
        "total_users": total_users.scalar(),
        "active_users": active_users.scalar(),
        "pending_users": pending_users.scalar(),
        "total_projects": total_projects.scalar(),
    }

    try:
        import json
        r = await get_redis()
        await r.setex("admin:stats", 30, json.dumps(result))
    except Exception:
        pass

    return result


# --- Системные напоминания (ТЗ 3.20.4) ---

from pydantic import BaseModel
from typing import Optional
from datetime import datetime as dt


class SystemReminderCreate(BaseModel):
    title: str
    message: str
    send_date: str  # ISO format


class SystemReminderUpdate(BaseModel):
    title: Optional[str] = None
    message: Optional[str] = None
    send_date: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("/reminders")
async def list_system_reminders(db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    """Список системных напоминаний"""
    from app.models.notification import SystemReminder
    result = await db.execute(select(SystemReminder).order_by(SystemReminder.send_date.desc()))
    return [
        {
            "id": str(r.id), "title": r.title, "message": r.message,
            "send_date": str(r.send_date), "is_active": r.is_active, "sent": r.sent,
            "created_at": str(r.created_at),
        }
        for r in result.scalars().all()
    ]


@router.post("/reminders", status_code=201)
async def create_system_reminder(
    data: SystemReminderCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Создать системное напоминание (дедлайн, праздник, перерыв)"""
    from app.models.notification import SystemReminder
    reminder = SystemReminder(
        title=data.title,
        message=data.message,
        send_date=dt.fromisoformat(data.send_date),
        created_by=admin.id,
    )
    db.add(reminder)
    await db.commit()
    await db.refresh(reminder)
    return {"id": str(reminder.id), "title": reminder.title}


@router.put("/reminders/{reminder_id}")
async def update_system_reminder(
    reminder_id: uuid.UUID,
    data: SystemReminderUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Обновить системное напоминание"""
    from app.models.notification import SystemReminder
    result = await db.execute(select(SystemReminder).where(SystemReminder.id == reminder_id))
    rem = result.scalar_one_or_none()
    if not rem:
        raise HTTPException(status_code=404, detail="Напоминание не найдено")
    if data.title is not None:
        rem.title = data.title
    if data.message is not None:
        rem.message = data.message
    if data.send_date is not None:
        rem.send_date = dt.fromisoformat(data.send_date)
    if data.is_active is not None:
        rem.is_active = data.is_active
    await db.commit()
    return {"message": "Обновлено"}


@router.delete("/reminders/{reminder_id}")
async def delete_system_reminder(
    reminder_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Удалить системное напоминание"""
    from app.models.notification import SystemReminder
    result = await db.execute(select(SystemReminder).where(SystemReminder.id == reminder_id))
    rem = result.scalar_one_or_none()
    if not rem:
        raise HTTPException(status_code=404, detail="Напоминание не найдено")
    await db.delete(rem)
    await db.commit()
    return {"message": "Удалено"}
