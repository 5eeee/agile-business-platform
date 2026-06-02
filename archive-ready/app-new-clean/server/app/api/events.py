# API событий
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.event import Event, EventParticipant, EventPhoto, EventChatMessage, EventReminder
from app.models.user import User
from app.schemas.event import EventCreate, EventUpdate, EventOut, EventParticipate, EventParticipantOut
from app.middleware.auth import get_current_user, require_admin

router = APIRouter(prefix="/events", tags=["События"])


@router.get("", response_model=list[EventOut])
async def list_events(limit: int = 50, offset: int = 0, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    limit = min(max(limit, 1), 100)
    offset = max(offset, 0)
    result = await db.execute(
        select(Event)
        .options(selectinload(Event.participants).selectinload(EventParticipant.user))
        .order_by(Event.event_date.desc()).limit(limit).offset(offset)
    )
    events = result.scalars().all()
    
    out = []
    for e in events:
        attending_count = sum(1 for p in e.participants if p.status == "attending")
        user_status = next((p.status for p in e.participants if p.user_id == user.id), None)
        participants = [
            EventParticipantOut(
                user_id=p.user_id, user_name=p.user.name if p.user else None, status=p.status
            )
            for p in e.participants
        ]
        
        out.append(EventOut(
            id=e.id, title=e.title, description=e.description, location=e.location,
            photo_url=e.photo_url, start_date=e.event_date, event_date=e.event_date,
            creator_id=e.creator_id, is_active=e.is_active,
            participant_count=attending_count,
            user_status=user_status, participants=participants,
            created_at=e.created_at,
        ))
    return out


@router.post("", response_model=EventOut, status_code=201)
async def create_event(data: EventCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    # Accept start_date as alias for event_date
    event_date = data.event_date or data.start_date
    if not event_date:
        raise HTTPException(status_code=400, detail="event_date or start_date is required")
    event = Event(
        title=data.title, description=data.description, location=data.location,
        event_date=event_date, creator_id=user.id,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return EventOut(
        id=event.id, title=event.title, description=event.description,
        location=event.location, photo_url=event.photo_url,
        start_date=event.event_date, event_date=event.event_date,
        creator_id=event.creator_id, is_active=event.is_active, created_at=event.created_at,
    )


@router.put("/{event_id}", response_model=EventOut)
async def update_event(event_id: uuid.UUID, data: EventUpdate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Событие не найдено")
    if event.creator_id != user.id and user.role.value != "admin":
        raise HTTPException(status_code=403, detail="Нет прав на редактирование")
    
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(event, key, value)
    await db.commit()
    await db.refresh(event)
    return EventOut(
        id=event.id, title=event.title, description=event.description,
        location=event.location, photo_url=event.photo_url,
        start_date=event.event_date, event_date=event.event_date,
        creator_id=event.creator_id, is_active=event.is_active, created_at=event.created_at,
    )


@router.delete("/{event_id}")
async def delete_event(event_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Событие не найдено")
    if event.creator_id != user.id and user.role.value != "admin":
        raise HTTPException(status_code=403, detail="Нет прав на удаление")
    await db.delete(event)
    await db.commit()
    return {"message": "Событие удалено"}


@router.post("/{event_id}/participate")
async def participate(event_id: uuid.UUID, data: EventParticipate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Участие в событии: 'Я приду' / 'Не смогу'"""
    if data.status not in ("attending", "not_attending"):
        raise HTTPException(status_code=400, detail="Статус: attending / not_attending")
    
    result = await db.execute(
        select(EventParticipant).where(EventParticipant.event_id == event_id, EventParticipant.user_id == user.id)
    )
    existing = result.scalar_one_or_none()
    if existing:
        existing.status = data.status
    else:
        p = EventParticipant(event_id=event_id, user_id=user.id, status=data.status)
        db.add(p)
    
    await db.commit()
    return {"message": "Статус участия обновлён"}


@router.get("/{event_id}/photos")
async def get_event_photos(event_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(EventPhoto).where(EventPhoto.event_id == event_id))
    return [{"id": str(p.id), "photo_url": p.photo_url, "created_at": str(p.created_at)} for p in result.scalars().all()]


@router.post("/{event_id}/photo", status_code=201)
async def upload_event_photo(
    event_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Загрузка фото события"""
    from app.services.s3 import upload_file_to_s3
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Допустимы только изображения")
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Событие не найдено")
    url = await upload_file_to_s3(file, f"events/{event_id}")
    photo = EventPhoto(event_id=event_id, photo_url=url, uploader_id=user.id)
    db.add(photo)
    await db.commit()
    await db.refresh(photo)
    return {"id": str(photo.id), "photo_url": photo.photo_url}


# --- Чат события ---

class EventChatMessageCreate(BaseModel):
    content: str


@router.get("/{event_id}/chat")
async def get_event_chat(
    event_id: uuid.UUID, limit: int = 50, offset: int = 0,
    db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user),
):
    """Сообщения чата события"""
    result = await db.execute(
        select(EventChatMessage)
        .options(selectinload(EventChatMessage.user))
        .where(EventChatMessage.event_id == event_id)
        .order_by(EventChatMessage.created_at.asc())
        .offset(offset).limit(limit)
    )
    messages = result.scalars().all()
    return [
        {
            "id": str(m.id), "event_id": str(m.event_id),
            "user_id": str(m.user_id),
            "user_name": m.user.name if m.user else None,
            "content": "[Удалено]" if m.is_deleted else m.content,
            "is_deleted": m.is_deleted,
            "created_at": str(m.created_at),
        }
        for m in messages
    ]


@router.post("/{event_id}/chat", status_code=201)
async def send_event_chat_message(
    event_id: uuid.UUID, data: EventChatMessageCreate,
    db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user),
):
    """Отправить сообщение в чат события"""
    msg = EventChatMessage(event_id=event_id, user_id=user.id, content=data.content)
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    return {
        "id": str(msg.id), "event_id": str(msg.event_id),
        "user_id": str(msg.user_id), "user_name": user.name,
        "content": msg.content, "created_at": str(msg.created_at),
    }


@router.delete("/{event_id}/chat/{message_id}")
async def delete_event_chat_message(
    event_id: uuid.UUID, message_id: uuid.UUID,
    db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user),
):
    """Удалить сообщение в чате события"""
    result = await db.execute(
        select(EventChatMessage).where(EventChatMessage.id == message_id, EventChatMessage.event_id == event_id)
    )
    msg = result.scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=404, detail="Сообщение не найдено")
    if msg.user_id != user.id and user.role.value != "admin":
        raise HTTPException(status_code=403, detail="Нет прав на удаление")
    msg.is_deleted = True
    msg.content = ""
    await db.commit()
    return {"message": "Сообщение удалено"}


# --- Напоминания о событии ---

@router.post("/{event_id}/reminders")
async def create_event_reminders(event_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Создать стандартные напоминания для события (1440, 360, 60, 45, 30, 15, 10, 5 мин до)"""
    from app.config import EVENT_REMINDER_INTERVALS
    existing = await db.execute(select(EventReminder).where(EventReminder.event_id == event_id))
    if existing.scalars().first():
        return {"message": "Напоминания уже созданы"}
    
    for minutes in EVENT_REMINDER_INTERVALS:
        r = EventReminder(event_id=event_id, minutes_before=minutes)
        db.add(r)
    await db.commit()
    return {"message": "Напоминания созданы"}


@router.get("/{event_id}/reminders")
async def get_event_reminders(event_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(
        select(EventReminder).where(EventReminder.event_id == event_id).order_by(EventReminder.minutes_before.desc())
    )
    return [{"id": str(r.id), "minutes_before": r.minutes_before, "sent": r.sent} for r in result.scalars().all()]
