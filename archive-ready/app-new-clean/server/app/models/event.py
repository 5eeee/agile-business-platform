# Модель событий
import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Boolean, Integer, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Event(Base):
    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    location: Mapped[str] = mapped_column(String(255), nullable=True)
    photo_url: Mapped[str] = mapped_column(String(500), nullable=True)
    event_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    
    creator_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    creator = relationship("User")
    participants: Mapped[list["EventParticipant"]] = relationship(back_populates="event", cascade="all, delete-orphan")
    photos: Mapped[list["EventPhoto"]] = relationship(back_populates="event", cascade="all, delete-orphan")


class EventParticipant(Base):
    __tablename__ = "event_participants"
    __table_args__ = (
        Index("ix_event_participant_event_user", "event_id", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # attending / not_attending
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    event: Mapped["Event"] = relationship(back_populates="participants")
    user = relationship("User")


class EventPhoto(Base):
    __tablename__ = "event_photos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    photo_url: Mapped[str] = mapped_column(String(500), nullable=False)
    uploader_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    event: Mapped["Event"] = relationship(back_populates="photos")
    uploader = relationship("User")


class EventChatMessage(Base):
    """Сообщение в чате события (отдельный чат для каждого события)"""
    __tablename__ = "event_chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    event = relationship("Event")
    user = relationship("User")


class EventReminder(Base):
    """Напоминание о событии"""
    __tablename__ = "event_reminders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    minutes_before: Mapped[int] = mapped_column(Integer, nullable=False)
    sent: Mapped[bool] = mapped_column(Boolean, default=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    event = relationship("Event")
