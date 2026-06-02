# Pydantic-схемы проектов
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None


class ProjectMemberAdd(BaseModel):
    user_id: uuid.UUID
    is_admin: bool = False
    role: str = "member"  # owner, member, viewer


class ProjectMemberOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    user_name: Optional[str] = None
    is_admin: bool
    role: str = "member"
    joined_at: datetime

    class Config:
        from_attributes = True


class ProjectOut(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str] = None
    creator_id: uuid.UUID
    is_deleted: bool = False
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProjectDetailOut(ProjectOut):
    members: list[ProjectMemberOut] = []
