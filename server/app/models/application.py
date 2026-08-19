import uuid
import enum
from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey, Enum as SAEnum, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class ApplicationSource(str, enum.Enum):
    WEBSITE = "website"
    MANUAL = "manual"


class ApplicationStatus(str, enum.Enum):
    NEW = "new"
    CONTACTING = "contacting"
    TZ_RECEIVED = "tz_received"
    REVIEW = "review"
    REVISION = "revision"
    APPROVED = "approved"
    DISTRIBUTING = "distributing"
    COMPLETED = "completed"


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source: Mapped[ApplicationSource] = mapped_column(
        SAEnum(ApplicationSource, values_callable=lambda e: [m.value for m in e]),
        default=ApplicationSource.MANUAL, nullable=False,
    )
    status: Mapped[ApplicationStatus] = mapped_column(
        SAEnum(ApplicationStatus, values_callable=lambda e: [m.value for m in e]),
        default=ApplicationStatus.NEW, nullable=False,
    )

    client_name: Mapped[str] = mapped_column(String(255), nullable=False)
    client_email: Mapped[str] = mapped_column(String(255), nullable=True)
    client_phone: Mapped[str] = mapped_column(String(100), nullable=True)
    client_company: Mapped[str] = mapped_column(String(255), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    tz_content: Mapped[str] = mapped_column(Text, nullable=True)
    departments: Mapped[str] = mapped_column(Text, nullable=True)

    consultant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True,
    )
    approved_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True,
    )
    review_comment: Mapped[str] = mapped_column(Text, nullable=True)

    project_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True,
    )
    sphere_deadlines_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    consultant = relationship("User", foreign_keys=[consultant_id])
    linked_project = relationship("Project", foreign_keys=[project_id])
    approved_by = relationship("User", foreign_keys=[approved_by_id])
    members: Mapped[list["ApplicationMember"]] = relationship(
        back_populates="application", cascade="all, delete-orphan",
    )
    history: Mapped[list["ApplicationHistory"]] = relationship(
        back_populates="application", cascade="all, delete-orphan",
    )
    tasks: Mapped[list["ApplicationTask"]] = relationship(
        back_populates="application", cascade="all, delete-orphan",
    )


class ApplicationMember(Base):
    """Staff members attached to an application by the consultant."""
    __tablename__ = "application_members"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    application = relationship("Application", back_populates="members")
    user = relationship("User")


class ApplicationTask(Base):
    """Tasks created by owner/deputy during distribution, assigned to application members."""
    __tablename__ = "application_tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False,
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("application_tasks.id", ondelete="CASCADE"), nullable=True,
    )
    assignee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    department: Mapped[str] = mapped_column(String(255), nullable=True)
    deadline: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_completed: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    application = relationship("Application", back_populates="tasks")
    assignee = relationship("User", foreign_keys=[assignee_id])
    parent = relationship(
        "ApplicationTask", remote_side="ApplicationTask.id", back_populates="children", foreign_keys=[parent_id],
    )
    children: Mapped[list["ApplicationTask"]] = relationship(
        "ApplicationTask", back_populates="parent", foreign_keys=[parent_id],
    )
    assignees: Mapped[list["ApplicationTaskAssignee"]] = relationship(
        back_populates="task", cascade="all, delete-orphan",
    )


class ApplicationTaskAssignee(Base):
    __tablename__ = "application_task_assignees"
    __table_args__ = (
        UniqueConstraint("application_task_id", "user_id", name="uq_application_task_assignee"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("application_tasks.id", ondelete="CASCADE"), nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )

    task = relationship("ApplicationTask", back_populates="assignees")
    user = relationship("User")


class ApplicationHistory(Base):
    __tablename__ = "application_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True,
    )
    old_status: Mapped[str] = mapped_column(String(50), nullable=True)
    new_status: Mapped[str] = mapped_column(String(50), nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    application = relationship("Application", back_populates="history")
    user = relationship("User")
