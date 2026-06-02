# Pydantic-схемы событий
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class EventCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    location: Optional[str] = None
    event_date: Optional[datetime] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class EventUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    location: Optional[str] = None
    event_date: Optional[datetime] = None


class EventParticipantOut(BaseModel):
    user_id: uuid.UUID
    user_name: Optional[str] = None
    status: str


class EventOut(BaseModel):
    id: uuid.UUID
    title: str
    description: Optional[str] = None
    location: Optional[str] = None
    photo_url: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    event_date: Optional[datetime] = None
    creator_id: uuid.UUID
    is_active: bool
    participant_count: int = 0
    user_status: Optional[str] = None
    participants: list[EventParticipantOut] = []
    created_at: datetime

    class Config:
        from_attributes = True


class EventParticipate(BaseModel):
    status: str  # attending / not_attending


class RetrospectiveAnswerCreate(BaseModel):
    went_well: Optional[str] = None
    to_improve: Optional[str] = None
    to_try: Optional[str] = None


class RetrospectiveOut(BaseModel):
    id: uuid.UUID
    iteration_id: uuid.UUID
    answers: list[dict] = []
    created_at: datetime

    class Config:
        from_attributes = True
