# Pydantic-схемы итераций
import uuid
from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, Field


class IterationCreate(BaseModel):
    project_id: uuid.UUID
    name: str = Field(..., min_length=1, max_length=255)
    start_date: date
    end_date: date
    template_name: Optional[str] = None


class IterationUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[str] = None


class IterationOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    start_date: date
    end_date: date
    status: str
    sort_order: int = 0
    template_name: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class IterationTemplateOut(BaseModel):
    id: uuid.UUID
    name: str
    sphere: Optional[str] = None
    tasks: list[dict] = []

    class Config:
        from_attributes = True
