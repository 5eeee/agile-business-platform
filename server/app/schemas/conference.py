import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ConferenceCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    starts_at: datetime
    ends_at: datetime | None = None
    invited_user_ids: list[uuid.UUID] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_period(self):
        self.title = self.title.strip()
        if self.ends_at and self.ends_at <= self.starts_at:
            raise ValueError("Время завершения должно быть позже времени начала")
        return self


class ConferenceStatusUpdate(BaseModel):
    status: Literal["scheduled", "live", "ended"]


class ConferenceOut(BaseModel):
    id: uuid.UUID
    title: str
    room_code: str
    starts_at: datetime
    ends_at: datetime | None = None
    status: str
    invited_user_ids: list[str]
    created_by_id: uuid.UUID
    created_by_name: str | None = None
    created_at: datetime
    can_manage: bool = False


class CallSSOTokenIn(BaseModel):
    token: str = Field(..., min_length=20, max_length=4096)
