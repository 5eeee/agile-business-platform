# API аутентификации
import uuid
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response
import bcrypt

from app.database import get_db
from app.models.user import User, UserStatus, UserRole
from app.schemas.user import (
    UserRegister, UserLogin, TokenResponse,
    PasswordChange, PasswordReset, PasswordResetConfirm, UserOut, UserAdminOut
)
from app.middleware.auth import (
    create_access_token, create_refresh_token, decode_token, get_current_user
)
from app.config import settings
import jwt as pyjwt
from app.rate_limit import limiter

import pyotp
import qrcode
import io
import base64

router = APIRouter(prefix="/auth", tags=["Аутентификация"])

# Dummy hash for timing attack mitigation
_DUMMY_HASH = bcrypt.hashpw(b"dummy", bcrypt.gensalt()).decode()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str | None) -> bool:
    """Безопасная проверка: битый/пустой хеш из БД не даёт 500, только «неверный пароль»."""
    if not hashed or not isinstance(hashed, str):
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError, AttributeError):
        return False


@router.post("/register", status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.RATE_LIMIT_LOGIN)
async def register(
    request: Request,
    data: UserRegister,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Регистрация. В проде по умолчанию — модерация; при DEBUG или REGISTRATION_AUTO_APPROVE — сразу ACTIVE."""
    if len(data.name) > 100:
        raise HTTPException(status_code=400, detail="Имя слишком длинное (макс. 100 символов)")
    if len(data.password) < 6:
        raise HTTPException(status_code=400, detail="Пароль должен быть минимум 6 символов")

    immediate = settings.DEBUG or settings.REGISTRATION_AUTO_APPROVE
    status_new = UserStatus.ACTIVE if immediate else UserStatus.PENDING

    result = await db.execute(select(User).where(func.lower(User.email) == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Пользователь с таким email уже существует")

    user = User(
        name=data.name.strip(),
        email=data.email,
        password_hash=hash_password(data.password),
        status=status_new,
        role=UserRole.USER,
        email_confirmed=bool(immediate),
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Пользователь с таким email уже существует")
    await db.refresh(user)

    try:
        from app.tasks.auth_notifications import notify_new_registration_task

        # Best-effort: если брокер недоступен, не валим запрос регистрации.
        notify_new_registration_task.delay(user.name, user.email)
    except Exception:
        try:
            # Fallback на синхронную отправку (асинхронные сервисы вызываем через await).
            from app.services.telegram import notify_new_registration

            await notify_new_registration(user.name, user.email)
        except Exception:
            pass

    if immediate:
        msg = "Регистрация успешна. Можно войти."
    else:
        msg = "Регистрация отправлена на модерацию. Вход будет доступен после одобрения администратором."

    return {
        "message": msg,
        "user_id": str(user.id),
        "immediate_login": immediate,
    }


@router.post("/login", response_model=TokenResponse)
@limiter.limit(settings.RATE_LIMIT_LOGIN)
async def login(
    request: Request,
    data: UserLogin,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Вход в систему по email/паролю. JWT-токены (access + refresh)"""
    result = await db.execute(select(User).where(func.lower(User.email) == data.email))
    user = result.scalar_one_or_none()
    
    if not user:
        # Timing attack mitigation: always run bcrypt even if user not found
        verify_password("dummy", _DUMMY_HASH)
        raise HTTPException(status_code=401, detail="Неверный email или пароль")
    
    if not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Неверный email или пароль")
    
    # Проверка статуса увольнения
    if user.status == UserStatus.FIRED:
        return {
            "token_type": "fired",
            "fire_message": user.fire_message or "ВЫ УВОЛЕНЫ",
        }
    
    if user.status == UserStatus.PENDING:
        raise HTTPException(status_code=403, detail="Ваш аккаунт на модерации")
    
    if user.status == UserStatus.REJECTED:
        raise HTTPException(status_code=403, detail="Ваша заявка была отклонена")
    
    if user.status == UserStatus.BLOCKED:
        raise HTTPException(status_code=403, detail="Ваш аккаунт заблокирован")

    if not getattr(user, "email_confirmed", False):
        raise HTTPException(status_code=403, detail="Email не подтверждён")
    
    # 2FA: если включена, не выдаём токены, а возвращаем временный токен
    if getattr(user, "totp_enabled", False) and user.totp_secret:
        temp_token = pyjwt.encode(
            {"sub": str(user.id), "type": "2fa_pending", "exp": datetime.utcnow() + timedelta(minutes=5)},
            settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM,
        )
        return {"token_type": "2fa_required", "temp_token": temp_token}

    # Обновление онлайн-статуса
    user.is_online = True
    user.last_seen = datetime.utcnow()
    await db.commit()

    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))

    # HttpOnly cookies защищают токены от XSS.
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/",
    )

    return TokenResponse()


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Обновление access-токена через refresh-токен"""
    refresh_token_cookie = request.cookies.get("refresh_token")
    if not refresh_token_cookie:
        raise HTTPException(status_code=401, detail="Refresh-токен отсутствует")

    payload = decode_token(refresh_token_cookie)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Невалидный refresh-токен")
    
    # Check if refresh token is blacklisted
    from app.services.redis import is_token_blacklisted, blacklist_token
    if await is_token_blacklisted(refresh_token_cookie):
        raise HTTPException(status_code=401, detail="Refresh-токен отозван")
    
    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if (
        not user
        or user.status != UserStatus.ACTIVE
        or not getattr(user, "email_confirmed", False)
    ):
        raise HTTPException(status_code=401, detail="Пользователь не найден или неактивен")
    
    # Blacklist old refresh token
    try:
        await blacklist_token(refresh_token_cookie, ttl=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400)
    except Exception:
        pass

    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/",
    )

    return TokenResponse()


@router.get("/me")
async def get_me(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Получение текущего профиля"""
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(User).options(selectinload(User.sphere_roles)).where(User.id == user.id)
    )
    user = result.scalar_one()
    return UserAdminOut.model_validate(user) if user.role == UserRole.ADMIN else UserOut.model_validate(user)


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Выход из системы — токен добавляется в blacklist Redis"""
    user.is_online = False
    user.last_seen = datetime.utcnow()
    await db.commit()
    
    try:
        from app.services.redis import blacklist_token
        access_token_cookie = request.cookies.get("access_token")
        refresh_token_cookie = request.cookies.get("refresh_token")

        if access_token_cookie:
            await blacklist_token(access_token_cookie, ttl=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)
        if refresh_token_cookie:
            await blacklist_token(refresh_token_cookie, ttl=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400)
    except Exception:
        pass

    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")

    return {"message": "Выход выполнен"}


@router.put("/password")
async def change_password(data: PasswordChange, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Смена пароля"""
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Неверный текущий пароль")
    if len(data.new_password) < 6:
        raise HTTPException(status_code=400, detail="Пароль должен быть минимум 6 символов")
    
    user.password_hash = hash_password(data.new_password)
    await db.commit()
    return {"message": "Пароль изменён"}


@router.post("/forgot-password")
@limiter.limit(settings.RATE_LIMIT_LOGIN)
async def forgot_password(
    request: Request,
    data: PasswordReset,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Запрос сброса пароля — отправка email со ссылкой"""
    result = await db.execute(select(User).where(func.lower(User.email) == data.email))
    user = result.scalar_one_or_none()
    # Всегда возвращаем успех (не раскрываем, существует ли email)
    if user:
        token = pyjwt.encode(
            {"sub": str(user.id), "type": "reset", "exp": datetime.utcnow() + timedelta(hours=1)},
            settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM,
        )
        try:
            from app.tasks.auth_notifications import send_password_reset_email_task

            # Best-effort: не раскрываем существование email и не валим запрос, если очередь недоступна.
            send_password_reset_email_task.delay(user.email, user.name, token)
        except Exception:
            try:
                from app.services.email import send_password_reset_email

                await send_password_reset_email(user.email, user.name, token)
            except Exception:
                pass
    return {"message": "Если email зарегистрирован, вы получите письмо со ссылкой для сброса"}


@router.post("/reset-password")
@limiter.limit(settings.RATE_LIMIT_LOGIN)
async def reset_password(
    request: Request,
    data: PasswordResetConfirm,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Сброс пароля по токену из email"""
    try:
        payload = pyjwt.decode(data.token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except Exception:
        raise HTTPException(status_code=400, detail="Невалидный или истёкший токен")
    if payload.get("type") != "reset":
        raise HTTPException(status_code=400, detail="Невалидный токен")

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=400, detail="Пользователь не найден")

    if len(data.new_password) < 6:
        raise HTTPException(status_code=400, detail="Пароль должен быть минимум 6 символов")

    user.password_hash = hash_password(data.new_password)
    await db.commit()
    return {"message": "Пароль успешно сброшен"}


@router.get("/confirm-email")
async def confirm_email(token: str, db: AsyncSession = Depends(get_db)):
    """Подтверждение email по токену"""
    try:
        payload = pyjwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except Exception:
        raise HTTPException(status_code=400, detail="Невалидный или истёкший токен")
    if payload.get("type") != "confirm":
        raise HTTPException(status_code=400, detail="Невалидный токен")

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=400, detail="Пользователь не найден")

    user.email_confirmed = True
    await db.commit()
    return {"message": "Email подтверждён"}


# ─── 2FA TOTP ───────────────────────────────────────────────

@router.post("/2fa/setup")
async def setup_totp(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Генерация TOTP-секрета и QR-кода для настройки 2FA"""
    secret = pyotp.random_base32()
    user.totp_secret = secret
    await db.commit()

    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=user.email, issuer_name="Agile.Workspace")

    # Генерация QR-кода в base64
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode()

    return {"secret": secret, "qr_code": f"data:image/png;base64,{qr_b64}"}


@router.post("/2fa/enable")
async def enable_totp(
    code: str = "",
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Включение 2FA после проверки одноразового кода"""
    if not user.totp_secret:
        raise HTTPException(status_code=400, detail="Сначала выполните /2fa/setup")

    totp = pyotp.TOTP(user.totp_secret)
    if not totp.verify(code, valid_window=1):
        raise HTTPException(status_code=400, detail="Неверный код")

    user.totp_enabled = True
    await db.commit()
    return {"message": "2FA включена"}


@router.post("/2fa/disable")
async def disable_totp(
    code: str = "",
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Отключение 2FA после проверки кода"""
    if not user.totp_enabled or not user.totp_secret:
        raise HTTPException(status_code=400, detail="2FA не включена")

    totp = pyotp.TOTP(user.totp_secret)
    if not totp.verify(code, valid_window=1):
        raise HTTPException(status_code=400, detail="Неверный код")

    user.totp_enabled = False
    user.totp_secret = None
    await db.commit()
    return {"message": "2FA отключена"}


@router.post("/2fa/verify")
@limiter.limit(settings.RATE_LIMIT_LOGIN)
async def verify_totp_login(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Проверка TOTP-кода при входе (второй шаг)"""
    body = await request.json()
    temp_token = body.get("temp_token", "")
    code = body.get("code", "")

    try:
        payload = pyjwt.decode(temp_token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except Exception:
        raise HTTPException(status_code=401, detail="Невалидный или истёкший токен")

    if payload.get("type") != "2fa_pending":
        raise HTTPException(status_code=401, detail="Невалидный токен")

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user or not user.totp_secret:
        raise HTTPException(status_code=401, detail="Пользователь не найден")

    totp = pyotp.TOTP(user.totp_secret)
    if not totp.verify(code, valid_window=1):
        raise HTTPException(status_code=401, detail="Неверный код 2FA")

    # Успешная верификация → выдаём полноценные токены
    user.is_online = True
    user.last_seen = datetime.utcnow()
    await db.commit()

    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))

    response.set_cookie(
        key="access_token", value=access_token,
        httponly=True, secure=not settings.DEBUG, samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60, path="/",
    )
    response.set_cookie(
        key="refresh_token", value=refresh_token,
        httponly=True, secure=not settings.DEBUG, samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400, path="/",
    )

    return TokenResponse()
