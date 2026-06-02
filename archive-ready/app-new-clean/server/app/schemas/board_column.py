import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class BoardColumnCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    sort_order: int = 0
    color: Optional[str] = None


class BoardColumnOut(BaseModel):
    id: uuid.UUID
    iteration_id: uuid.UUID
    title: str
    sort_order: int
    color: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
