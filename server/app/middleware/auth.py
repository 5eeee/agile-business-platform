# Middleware аутентификации JWT
import uuid
from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.database import get_db
from app.models.user import User, UserRole, UserStatus, ADMIN_ROLES

security = HTTPBearer(auto_error=False)


def create_access_token(user_id: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": user_id, "exp": expire, "type": "access"}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {"sub": user_id, "exp": expire, "type": "refresh"}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Токен истёк")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Невалидный токен")


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    token = None

    # Приоритет cookie (HttpOnly), fallback на Authorization header.
    token = request.cookies.get("access_token")
    if not token and credentials and getattr(credentials, "credentials", None):
        token = credentials.credentials

    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Не авторизован")

    payload = decode_token(token)
    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Невалидный тип токена")
    
    # Проверка blacklist (Redis)
    try:
        from app.services.redis import is_token_blacklisted
        if await is_token_blacklisted(token):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Токен отозван")
    except ImportError:
        pass
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Невалидный токен")
    
    result = await db.execute(
        select(User).where(User.id == uuid.UUID(user_id))
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Пользователь не найден")
    
    if user.status == UserStatus.FIRED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=user.fire_message or "Вы уволены",
            headers={"X-Fired": "true"}
        )
    
    if user.status not in (UserStatus.ACTIVE,):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Аккаунт не активен")

    if not getattr(user, "email_confirmed", False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Email не подтверждён")
    
    return user


FULL_ACCESS_ROLES = ADMIN_ROLES
APPLICATIONS_ROLES = {UserRole.ADMIN, UserRole.OWNER, UserRole.DEPUTY_OWNER, UserRole.CONSULTANT}


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role not in FULL_ACCESS_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Требуются права администратора")
    return user


def require_applications_access(user: User = Depends(get_current_user)) -> User:
    if user.role not in APPLICATIONS_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к модулю заявок")
    return user


def require_non_consultant(user: User = Depends(get_current_user)) -> User:
    if user.role == UserRole.CONSULTANT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Консультантам недоступен этот раздел")
    return user
