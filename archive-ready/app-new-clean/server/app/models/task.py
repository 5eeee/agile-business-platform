# Модель задачи
import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey, Index, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        Index("ix_task_iteration_status", "iteration_id", "status"),
        Index("ix_task_assignee_status", "assignee_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    iteration_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("iterations.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    
    status: Mapped[str] = mapped_column(String(50), default="Готово к запуску")  # Готово к запуску / Создаёт ценность / Доставлено клиенту
    priority: Mapped[str] = mapped_column(String(20), default="Средний")  # Низкий / Средний / Высокий
    
    assignee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    creator_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    start_date: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    deadline: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=True
    )
    board_column_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("iteration_board_columns.id", ondelete="SET NULL"), nullable=True
    )
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Отношения
    iteration = relationship("Iteration", back_populates="tasks")
    assignee = relationship("User", foreign_keys=[assignee_id])
    creator = relationship("User", foreign_keys=[creator_id])
    comments: Mapped[list["TaskComment"]] = relationship(back_populates="task", cascade="all, delete-orphan")
    history: Mapped[list["TaskHistory"]] = relationship(back_populates="task", cascade="all, delete-orphan")
    attachments: Mapped[list["TaskAttachment"]] = relationship(back_populates="task", cascade="all, delete-orphan")

    parent: Mapped["Task | None"] = relationship(
        "Task", remote_side="Task.id", back_populates="children", foreign_keys=[parent_id]
    )
    children: Mapped[list["Task"]] = relationship(
        "Task", back_populates="parent", foreign_keys=[parent_id], cascade="all, delete-orphan"
    )
    board_column = relationship("BoardColumn", back_populates="tasks")


class TaskComment(Base):
    __tablename__ = "task_comments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    task: Mapped["Task"] = relationship(back_populates="comments")
    user = relationship("User")


class TaskHistory(Base):
    __tablename__ = "task_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    field: Mapped[str] = mapped_column(String(50), nullable=False)  # status, assignee, priority и т.д.
    old_value: Mapped[str] = mapped_column(Text, nullable=True)
    new_value: Mapped[str] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    task: Mapped["Task"] = relationship(back_populates="history")
    user = relationship("User")


class TaskAttachment(Base):
    __tablename__ = "task_attachments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_url: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(nullable=True)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    task: Mapped["Task"] = relationship(back_populates="attachments")
    user = relationship("User")
