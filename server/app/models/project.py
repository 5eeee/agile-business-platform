# Модель проекта
import enum
import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Boolean, ForeignKey, UniqueConstraint, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class ProjectRole(str, enum.Enum):
    OWNER = "owner"
    MEMBER = "member"
    VIEWER = "viewer"


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    
    creator_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Отношения
    members: Mapped[list["ProjectMember"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    creator = relationship("User", foreign_keys=[creator_id])


class ProjectMember(Base):
    __tablename__ = "project_members"
    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_member"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)  # Backward compat
    role: Mapped[str] = mapped_column(
        String(10),
        default="member",
        server_default="member",
    )
    
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    project: Mapped["Project"] = relationship(back_populates="members")
    user = relationship("User")
