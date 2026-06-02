# Pydantic-схемы задач
import uuid
from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, Field


class TaskCreate(BaseModel):
    iteration_id: uuid.UUID
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    assignee_id: Optional[uuid.UUID] = None
    start_date: Optional[datetime] = None
    deadline: Optional[datetime] = None
    priority: str = "Средний"
    parent_id: Optional[uuid.UUID] = None
    board_column_id: Optional[uuid.UUID] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    assignee_id: Optional[uuid.UUID] = None
    start_date: Optional[datetime] = None
    deadline: Optional[datetime] = None
    board_column_id: Optional[uuid.UUID] = None
    is_completed: Optional[bool] = None


class TaskCommentCreate(BaseModel):
    content: str = Field(..., min_length=1)


class TaskOut(BaseModel):
    id: uuid.UUID
    iteration_id: uuid.UUID
    title: str
    description: Optional[str] = None
    status: str
    priority: str
    assignee_id: Optional[uuid.UUID] = None
    assignee_name: Optional[str] = None
    creator_id: uuid.UUID
    creator_name: Optional[str] = None
    start_date: Optional[datetime] = None
    deadline: Optional[datetime] = None
    parent_id: Optional[uuid.UUID] = None
    board_column_id: Optional[uuid.UUID] = None
    is_completed: bool = False
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TaskCommentOut(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    user_id: uuid.UUID
    user_name: Optional[str] = None
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class TaskHistoryOut(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    user_id: uuid.UUID
    user_name: Optional[str] = None
    field: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class TaskDetailOut(TaskOut):
    comments: list[TaskCommentOut] = []
    history: list[TaskHistoryOut] = []
    attachments: list[dict[str, str | int | None]] = []


class BacklogItemCreate(BaseModel):
    project_id: uuid.UUID
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None


class BacklogItemOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    title: str
    description: Optional[str] = None
    creator_id: uuid.UUID
    creator_name: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class BacklogToTask(BaseModel):
    iteration_id: uuid.UUID
    assignee_id: Optional[uuid.UUID] = None
    start_date: Optional[datetime] = None
    deadline: Optional[date] = None
    priority: str = "Средний"
    board_column_id: Optional[uuid.UUID] = None
