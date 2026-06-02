# Модели обучения (LMS)
import uuid
import enum
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Integer, Boolean, ForeignKey, Enum as SAEnum, UniqueConstraint, Table, Column
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


# --- Enums ---

class DifficultyLevel(str, enum.Enum):
    BASIC = "basic"
    MEDIUM = "medium"
    HARD = "hard"


class ProgressStatus(str, enum.Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class ContentType(str, enum.Enum):
    THEORY = "theory"
    PRACTICE = "practice"
    TEST = "test"
    RESOURCES = "resources"
    TEXT = "text"


# --- Association table for Topic <-> Hashtag ---
topic_hashtags = Table(
    "topic_hashtags",
    Base.metadata,
    Column("topic_id", UUID(as_uuid=True), ForeignKey("training_topics.id", ondelete="CASCADE"), primary_key=True),
    Column("hashtag_id", UUID(as_uuid=True), ForeignKey("training_hashtags.id", ondelete="CASCADE"), primary_key=True),
)


class CourseAssignment(Base):
    """Назначение курса конкретному стажёру"""
    __tablename__ = "course_assignments"
    __table_args__ = (UniqueConstraint("course_id", "user_id", name="uq_course_user"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    course_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("training_courses.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    assigned_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    course = relationship("TrainingCourse", back_populates="assignments")
    user = relationship("User", foreign_keys=[user_id])
    assigner = relationship("User", foreign_keys=[assigned_by])


class TrainingCourse(Base):
    """Предмет/курс обучения (например 'IT Отдел обучение')"""
    __tablename__ = "training_courses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    order: Mapped[int] = mapped_column(Integer, default=0)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    topics: Mapped[list["TrainingTopic"]] = relationship(back_populates="course", cascade="all, delete-orphan", order_by="TrainingTopic.order")
    assignments: Mapped[list["CourseAssignment"]] = relationship(back_populates="course", cascade="all, delete-orphan")
    creator = relationship("User", foreign_keys=[created_by])


class TrainingTopic(Base):
    """Тема внутри курса (подтема с теорией, практикой, тестом)"""
    __tablename__ = "training_topics"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    course_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("training_courses.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    order: Mapped[int] = mapped_column(Integer, default=0)
    section_title: Mapped[str] = mapped_column(String(500), nullable=True)
    difficulty: Mapped[str] = mapped_column(String(20), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    course: Mapped["TrainingCourse"] = relationship(back_populates="topics")
    content_blocks: Mapped[list["TrainingContent"]] = relationship(back_populates="topic", cascade="all, delete-orphan", order_by="TrainingContent.order")
    task: Mapped["TrainingTask"] = relationship(back_populates="topic", uselist=False, cascade="all, delete-orphan")
    hashtags: Mapped[list["Hashtag"]] = relationship(secondary=topic_hashtags, back_populates="topics", lazy="selectin")
    progress_records: Mapped[list["TopicProgress"]] = relationship(back_populates="topic", cascade="all, delete-orphan")


class TrainingContent(Base):
    """Блок контента внутри темы (теория, практика, тест, ресурсы)"""
    __tablename__ = "training_content"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("training_topics.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=True)
    content_type: Mapped[str] = mapped_column(String(20), default="text")
    order: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    topic: Mapped["TrainingTopic"] = relationship(back_populates="content_blocks")


class TrainingTask(Base):
    """Задание привязанное к теме (одно задание на тему)"""
    __tablename__ = "training_tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("training_topics.id", ondelete="CASCADE"), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    topic: Mapped["TrainingTopic"] = relationship(back_populates="task")
    submissions: Mapped[list["TrainingSubmission"]] = relationship(back_populates="task", cascade="all, delete-orphan")


class SubmissionStatus(str, enum.Enum):
    PENDING = "pending"       # На проверке
    APPROVED = "approved"     # Принято
    REJECTED = "rejected"     # Отклонено (переделать)


class TrainingSubmission(Base):
    """Ответ стажёра на задание"""
    __tablename__ = "training_submissions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("training_tasks.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=True)
    file_url: Mapped[str] = mapped_column(String(500), nullable=True)
    status: Mapped[SubmissionStatus] = mapped_column(SAEnum(SubmissionStatus, values_callable=lambda e: [m.value for m in e]), default=SubmissionStatus.PENDING)
    reviewer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    review_comment: Mapped[str] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    task: Mapped["TrainingTask"] = relationship(back_populates="submissions")
    user = relationship("User", foreign_keys=[user_id])
    reviewer = relationship("User", foreign_keys=[reviewer_id])


class Hashtag(Base):
    """Хэштег для подтем обучения"""
    __tablename__ = "training_hashtags"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    color: Mapped[str] = mapped_column(String(7), default="#6366f1")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    topics: Mapped[list["TrainingTopic"]] = relationship(secondary=topic_hashtags, back_populates="hashtags", lazy="selectin")


class TopicProgress(Base):
    """Прогресс пользователя по подтеме"""
    __tablename__ = "topic_progress"
    __table_args__ = (UniqueConstraint("topic_id", "user_id", name="uq_topic_user_progress"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("training_topics.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="not_started")

    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    topic: Mapped["TrainingTopic"] = relationship(back_populates="progress_records")
    user = relationship("User", foreign_keys=[user_id])
