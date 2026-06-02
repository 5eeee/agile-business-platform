# Pydantic-схемы обучения
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# --- Course ---
class CourseCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None

class CourseUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    order: Optional[int] = None
    is_published: Optional[bool] = None

class CourseOut(BaseModel):
    id: uuid.UUID
    title: str
    description: Optional[str] = None
    order: int
    is_published: bool
    topic_count: int = 0
    created_at: datetime
    class Config:
        from_attributes = True


# --- Hashtag ---
class HashtagCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    color: Optional[str] = Field(None, max_length=7)

class HashtagOut(BaseModel):
    id: uuid.UUID
    name: str
    color: str
    class Config:
        from_attributes = True


# --- Topic ---
class TopicCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    section_title: Optional[str] = None
    difficulty: Optional[str] = None

class TopicUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    order: Optional[int] = None
    section_title: Optional[str] = None
    difficulty: Optional[str] = None

class ContentBlockOut(BaseModel):
    id: uuid.UUID
    title: Optional[str] = None
    body: Optional[str] = None
    content_type: str = "text"
    order: int
    class Config:
        from_attributes = True

class TaskBriefOut(BaseModel):
    id: uuid.UUID
    title: str
    class Config:
        from_attributes = True

class TopicOut(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    title: str
    description: Optional[str] = None
    order: int
    section_title: Optional[str] = None
    difficulty: Optional[str] = None
    has_task: bool = False
    is_unlocked: bool = True
    status: str = "locked"  # locked / in_progress / completed
    progress: str = "not_started"  # not_started / in_progress / completed
    hashtags: list[HashtagOut] = []
    created_at: datetime
    class Config:
        from_attributes = True

class TopicDetailOut(TopicOut):
    content_blocks: list[ContentBlockOut] = []
    task: Optional[TaskBriefOut] = None


# --- Content ---
class ContentCreate(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None
    content_type: Optional[str] = "text"
    order: Optional[int] = 0

class ContentUpdate(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None
    content_type: Optional[str] = None
    order: Optional[int] = None


# --- Task ---
class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str

class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None

class TaskOut(BaseModel):
    id: uuid.UUID
    topic_id: uuid.UUID
    title: str
    description: str
    created_at: datetime
    class Config:
        from_attributes = True


# --- Submission ---
class SubmissionCreate(BaseModel):
    content: Optional[str] = None

class SubmissionReview(BaseModel):
    status: str  # approved / rejected
    review_comment: Optional[str] = None

class SubmissionOut(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    user_id: uuid.UUID
    user_name: str = ""
    task_title: str = ""
    content: Optional[str] = None
    file_url: Optional[str] = None
    status: str
    review_comment: Optional[str] = None
    reviewer_id: Optional[uuid.UUID] = None
    created_at: datetime
    reviewed_at: Optional[datetime] = None
    class Config:
        from_attributes = True


# --- Course Assignment ---
class CourseAssign(BaseModel):
    user_ids: list[uuid.UUID]

class CourseAssignmentOut(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    user_id: uuid.UUID
    user_name: str = ""
    user_email: str = ""
    assigned_by_name: str = ""
    created_at: datetime
    class Config:
        from_attributes = True

class InternOut(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    training_role: Optional[str] = None
    class Config:
        from_attributes = True


# --- Progress ---
class ProgressUpdate(BaseModel):
    status: str = Field(..., pattern="^(not_started|in_progress|completed)$")

class ProgressOut(BaseModel):
    topic_id: uuid.UUID
    user_id: uuid.UUID
    status: str
    updated_at: datetime
    class Config:
        from_attributes = True


# --- Code execution ---
class CodeRunRequest(BaseModel):
    language: str = Field(..., min_length=1, max_length=30)
    code: str = Field(..., min_length=1, max_length=50000)

class CodeRunResult(BaseModel):
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    timed_out: bool = False
