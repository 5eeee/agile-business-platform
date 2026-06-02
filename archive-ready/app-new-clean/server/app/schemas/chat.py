# Pydantic-схемы чата
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ChatMessageCreate(BaseModel):
    content: str = Field(..., min_length=1)
    reply_to_id: Optional[uuid.UUID] = None


class ChatMessageUpdate(BaseModel):
    content: str = Field(..., min_length=1)


class ChatMessageOut(BaseModel):
    id: uuid.UUID
    iteration_id: uuid.UUID
    user_id: uuid.UUID
    user_name: Optional[str] = None
    user_avatar: Optional[str] = None
    content: str
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    file_mime: Optional[str] = None
    reply_to_id: Optional[uuid.UUID] = None
    reply_to_content: Optional[str] = None
    reply_to_user_name: Optional[str] = None
    is_edited: bool = False
    is_deleted: bool = False
    poll: Optional[dict] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PollCreate(BaseModel):
    question: str = Field(..., min_length=1)
    options: list[str] = Field(..., min_length=2, max_length=20)  # До 20 вариантов ответа
    is_multiple: bool = False


class PollVote(BaseModel):
    option_id: uuid.UUID
