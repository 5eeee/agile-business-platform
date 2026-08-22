import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_db
from app.middleware.auth import require_call_access
from app.models.conference import Conference, ConferenceSSOUse
from app.models.user import ADMIN_ROLES, User, UserStatus
from app.schemas.conference import CallSSOTokenIn, ConferenceCreate, ConferenceOut, ConferenceStatusUpdate


router = APIRouter(tags=["Конференции"])


def _can_manage(user: User) -> bool:
    return user.role in ADMIN_ROLES


def _ensure_can_join(conference: Conference, user: User, now: datetime) -> None:
    if conference.status == "ended" or (conference.ends_at and now > conference.ends_at):
        raise HTTPException(status_code=403, detail="Конференция завершена")
    if _can_manage(user):
        return
    invited = set(conference.invited_user_ids or [])
    if invited and str(user.id) not in invited:
        raise HTTPException(status_code=403, detail="Вы не приглашены в эту конференцию")
    if conference.status != "live" and now < conference.starts_at - timedelta(minutes=5):
        raise HTTPException(status_code=403, detail="Подключение откроется за 5 минут до начала")


def _to_out(conference: Conference, viewer: User) -> ConferenceOut:
    creator = conference.created_by
    creator_name = None
    if creator:
        creator_name = " ".join(part for part in (creator.last_name, creator.name) if part)
    return ConferenceOut(
        id=conference.id,
        title=conference.title,
        room_code=conference.room_code,
        starts_at=conference.starts_at,
        ends_at=conference.ends_at,
        status=conference.status,
        invited_user_ids=conference.invited_user_ids or [],
        created_by_id=conference.created_by_id,
        created_by_name=creator_name,
        created_at=conference.created_at,
        can_manage=_can_manage(viewer),
    )


@router.get("/conferences", response_model=list[ConferenceOut])
async def list_conferences(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_call_access),
) -> list[ConferenceOut]:
    query = select(Conference).options(selectinload(Conference.created_by)).where(
        Conference.status != "ended",
    )
    result = await db.execute(query.order_by(Conference.starts_at.asc()))
    conferences = list(result.scalars().all())
    if not _can_manage(current_user):
        user_id = str(current_user.id)
        conferences = [
            item for item in conferences
            if not item.invited_user_ids or user_id in item.invited_user_ids
        ]
    return [_to_out(item, current_user) for item in conferences]


@router.post("/conferences", response_model=ConferenceOut, status_code=201)
async def create_scheduled_conference(
    data: ConferenceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_call_access),
) -> ConferenceOut:
    if not _can_manage(current_user):
        raise HTTPException(status_code=403, detail="Создавать конференции могут только владелец и руководители")
    invited = [str(item) for item in dict.fromkeys(data.invited_user_ids)]
    if invited:
        users_result = await db.execute(select(User.id).where(User.id.in_(data.invited_user_ids)))
        existing = {str(row[0]) for row in users_result.all()}
        if existing != set(invited):
            raise HTTPException(status_code=400, detail="Один или несколько приглашённых сотрудников не найдены")
    conference = Conference(
        title=data.title,
        room_code=f"AGILE_{secrets.token_hex(5).upper()}",
        starts_at=data.starts_at,
        ends_at=data.ends_at,
        invited_user_ids=invited,
        created_by_id=current_user.id,
    )
    db.add(conference)
    await db.commit()
    result = await db.execute(
        select(Conference).options(selectinload(Conference.created_by)).where(Conference.id == conference.id)
    )
    return _to_out(result.scalar_one(), current_user)


@router.patch("/conferences/{conference_id}/status", response_model=ConferenceOut)
async def update_conference_status(
    conference_id: uuid.UUID,
    data: ConferenceStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_call_access),
) -> ConferenceOut:
    if not _can_manage(current_user):
        raise HTTPException(status_code=403, detail="Изменять конференции могут только владелец и руководители")
    result = await db.execute(
        select(Conference).options(selectinload(Conference.created_by)).where(Conference.id == conference_id)
    )
    conference = result.scalar_one_or_none()
    if not conference:
        raise HTTPException(status_code=404, detail="Конференция не найдена")
    conference.status = data.status
    conference.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(conference)
    return _to_out(conference, current_user)


@router.get("/conference/sso")
async def create_call_sso_token(
    conference_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_call_access),
) -> dict[str, str]:
    conference = await db.get(Conference, conference_id)
    if not conference:
        raise HTTPException(status_code=404, detail="Конференция не найдена")
    now = datetime.now(timezone.utc)
    _ensure_can_join(conference, current_user, now)
    full_name = " ".join(
        part for part in (current_user.last_name, current_user.name, current_user.patronymic) if part
    )
    expires_at = now + timedelta(seconds=60)
    jti = secrets.token_urlsafe(24)
    token = jwt.encode(
        {
            "sub": str(current_user.id),
            "jti": jti,
            "email": current_user.email,
            "full_name": full_name or current_user.name,
            "role": current_user.role.value,
            "conference_id": str(conference.id),
            "room_code": conference.room_code,
            "type": "call_sso",
            "aud": "agile-call",
            "exp": expires_at,
        },
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return {"token": token, "expires_at": expires_at.isoformat()}


@router.post("/conference/sso/verify")
async def verify_call_sso_token(data: CallSSOTokenIn, db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    try:
        payload = jwt.decode(
            data.token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            audience="agile-call",
            options={"require": ["exp", "sub", "jti", "conference_id", "room_code"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="Токен Agile Call истёк") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Невалидный токен Agile Call") from exc
    if payload.get("type") != "call_sso" or not payload.get("sub"):
        raise HTTPException(status_code=401, detail="Невалидный тип токена Agile Call")
    try:
        user_id = uuid.UUID(str(payload["sub"]))
        conference_id = uuid.UUID(str(payload["conference_id"]))
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Невалидный пользователь Agile Call") from exc
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or user.status != UserStatus.ACTIVE or not user.email_confirmed:
        raise HTTPException(status_code=401, detail="Учётная запись сотрудника недоступна")
    conference = await db.get(Conference, conference_id)
    if not conference or conference.room_code != payload.get("room_code"):
        raise HTTPException(status_code=401, detail="Конференция Agile Call недоступна")
    _ensure_can_join(conference, user, datetime.now(timezone.utc))

    consume_statement = (
        pg_insert(ConferenceSSOUse)
        .values(
            jti=str(payload["jti"]),
            conference_id=conference.id,
            user_id=user.id,
            expires_at=datetime.fromtimestamp(float(payload["exp"]), tz=timezone.utc),
            used_at=datetime.now(timezone.utc),
        )
        .on_conflict_do_nothing(index_elements=[ConferenceSSOUse.jti])
        .returning(ConferenceSSOUse.jti)
    )
    consume_result = await db.execute(consume_statement)
    if consume_result.scalar_one_or_none() is None:
        await db.rollback()
        raise HTTPException(status_code=401, detail="Токен Agile Call уже использован")
    await db.commit()
    full_name = " ".join(part for part in (user.last_name, user.name, user.patronymic) if part)
    return {
        "ok": True,
        "conference_id": str(conference.id),
        "room_code": conference.room_code,
        "conference_title": conference.title,
        "user": {
            "platform_id": str(user.id),
            "email": user.email,
            "full_name": full_name or user.name,
            "role": user.role.value,
            "department_id": user.department_id,
        },
    }
