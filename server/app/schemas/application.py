import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class ApplicationCreate(BaseModel):
    client_name: str = Field(..., min_length=1, max_length=255)
    client_email: Optional[str] = None
    client_phone: Optional[str] = None
    client_company: Optional[str] = None
    description: Optional[str] = None
    source: str = "manual"
    project_name: Optional[str] = Field(None, max_length=500)


class ApplicationWebhookCreate(BaseModel):
    """Payload from the website contact form (server-to-server)."""
    name: str = Field(..., min_length=1, max_length=255)
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    message: Optional[str] = None
    service: Optional[str] = None
    project_name: Optional[str] = Field(None, max_length=500)
    source_reference: Optional[str] = Field(None, max_length=120)
    source_verification_token: Optional[str] = Field(None, max_length=4096)


class ApplicationUpdate(BaseModel):
    client_name: Optional[str] = Field(None, max_length=255)
    client_email: Optional[str] = None
    client_phone: Optional[str] = None
    client_company: Optional[str] = None
    description: Optional[str] = None
    tz_content: Optional[str] = None
    departments: Optional[str] = None
    project_name: Optional[str] = Field(None, max_length=500)
    sphere_deadlines_json: Optional[str] = None


class ApplicationStatusChange(BaseModel):
    status: str
    comment: Optional[str] = None


class ApplicationMemberAdd(BaseModel):
    user_id: uuid.UUID


class ApplicationMemberOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    user_name: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ApplicationHistoryOut(BaseModel):
    id: uuid.UUID
    user_id: Optional[uuid.UUID] = None
    user_name: Optional[str] = None
    old_status: Optional[str] = None
    new_status: str
    comment: Optional[str] = None
    created_at: datetime

    @field_validator("old_status", "new_status", mode="before")
    @classmethod
    def enum_to_str(cls, v):
        if v is None:
            return v
        return v.value if hasattr(v, "value") else str(v)

    class Config:
        from_attributes = True


class ApplicationTaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    department: Optional[str] = None
    assignee_id: Optional[uuid.UUID] = None
    assignee_ids: Optional[list[uuid.UUID]] = None
    parent_id: Optional[uuid.UUID] = None
    deadline: Optional[str] = None  # дд.мм.гггг чч.мм или ISO-дата


class ApplicationTaskUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = None
    department: Optional[str] = None
    assignee_id: Optional[uuid.UUID] = None
    assignee_ids: Optional[list[uuid.UUID]] = None
    parent_id: Optional[uuid.UUID] = None
    deadline: Optional[str] = None
    is_completed: Optional[bool] = None


class ApplicationTaskOut(BaseModel):
    id: uuid.UUID
    application_id: uuid.UUID
    parent_id: Optional[uuid.UUID] = None
    assignee_id: Optional[uuid.UUID] = None
    assignee_name: Optional[str] = None
    assignee_ids: list[uuid.UUID] = []
    assignee_names: list[str] = []
    title: str
    description: Optional[str] = None
    department: Optional[str] = None
    deadline: Optional[datetime] = None
    is_completed: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


class ApplicationOut(BaseModel):
    id: uuid.UUID
    source: str
    external_reference: Optional[str] = None
    status: str
    client_name: str
    client_email: Optional[str] = None
    client_phone: Optional[str] = None
    client_company: Optional[str] = None
    description: Optional[str] = None
    tz_content: Optional[str] = None
    departments: Optional[str] = None
    consultant_id: Optional[uuid.UUID] = None
    consultant_name: Optional[str] = None
    approved_by_id: Optional[uuid.UUID] = None
    approved_by_name: Optional[str] = None
    review_comment: Optional[str] = None
    project_name: Optional[str] = None
    project_id: Optional[uuid.UUID] = None
    sphere_deadlines_json: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    members: list[ApplicationMemberOut] = []
    history: list[ApplicationHistoryOut] = []
    tasks: list[ApplicationTaskOut] = []

    @field_validator("source", "status", mode="before")
    @classmethod
    def enum_to_str(cls, v):
        if v is None:
            return v
        return v.value if hasattr(v, "value") else str(v)

    class Config:
        from_attributes = True
