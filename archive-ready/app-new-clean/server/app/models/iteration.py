# Модель итерации
import uuid
from datetime import datetime, date
from sqlalchemy import String, Text, DateTime, Date, Integer, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
import enum


class IterationStatus(str, enum.Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class Iteration(Base):
    __tablename__ = "iterations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[IterationStatus] = mapped_column(SAEnum(IterationStatus), default=IterationStatus.ACTIVE)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    template_name: Mapped[str] = mapped_column(String(100), nullable=True)  # Шаблон, из которого создана
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    project = relationship("Project")
    tasks = relationship("Task", back_populates="iteration", cascade="all, delete-orphan")
    board_columns = relationship(
        "BoardColumn",
        back_populates="iteration",
        cascade="all, delete-orphan",
        order_by="BoardColumn.sort_order",
    )
    retrospective = relationship("Retrospective", back_populates="iteration", uselist=False)
    messages = relationship("ChatMessage", back_populates="iteration", cascade="all, delete-orphan")


class IterationTemplate(Base):
    """Шаблоны итераций"""
    __tablename__ = "iteration_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)  # Финансы, HR, IT и т.д.
    sphere: Mapped[str] = mapped_column(String(100), nullable=True)
    
    tasks: Mapped[list["IterationTemplateTask"]] = relationship(back_populates="template", cascade="all, delete-orphan")
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class IterationTemplateTask(Base):
    """Типовые задачи шаблона итерации"""
    __tablename__ = "iteration_template_tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("iteration_templates.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    priority: Mapped[str] = mapped_column(String(20), default="Средний")
    
    template: Mapped["IterationTemplate"] = relationship(back_populates="tasks")
