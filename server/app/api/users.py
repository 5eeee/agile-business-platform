# API пользователей и профилей
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.user import User, UserRole, UserSphereRole
from app.schemas.user import UserOut, UserProfileUpdate
from app.middleware.auth import get_current_user
from app.services.s3 import upload_file_to_s3

router = APIRouter(prefix="/users", tags=["Пользователи"])


@router.get("", response_model=list[UserOut])
async def list_users(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Список всех активных пользователей"""
    result = await db.execute(
        select(User)
        .options(selectinload(User.sphere_roles))
        .where(User.status == "active")
        .order_by(User.name)
    )
    users = result.scalars().all()
    return [UserOut.model_validate(u) for u in users]


@router.get("/{user_id}")
async def get_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Получение профиля пользователя. Email скрыт от обычных пользователей"""
    result = await db.execute(
        select(User).options(selectinload(User.sphere_roles)).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    data = UserOut.model_validate(user).model_dump()
    # Email виден только администратору
    if current_user.role == UserRole.ADMIN:
        data["email"] = user.email
    return data


@router.put("/profile")
async def update_profile(data: UserProfileUpdate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Редактирование своего профиля"""
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(user, key, value)
    
    await db.commit()
    # Eager load sphere_roles for serialization
    result = await db.execute(
        select(User).options(selectinload(User.sphere_roles)).where(User.id == user.id)
    )
    user = result.scalar_one()
    return UserOut.model_validate(user)


@router.post("/me/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Загрузка аватара пользователя"""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Допустимы только изображения")
    if file.size and file.size > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Максимальный размер: 5 МБ")

    url = await upload_file_to_s3(file, f"avatars/{user.id}")
    user.avatar_url = url
    await db.commit()
    return {"avatar_url": url}
