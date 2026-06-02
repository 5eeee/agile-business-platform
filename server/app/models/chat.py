# Модели чата: сообщения, опросы
import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Boolean, Integer, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        Index("ix_chat_message_iteration_created", "iteration_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    iteration_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("iterations.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Ответ на сообщение
    reply_to_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chat_messages.id", ondelete="SET NULL"), nullable=True)
    
    # Прикрепленный файл
    file_url: Mapped[str] = mapped_column(String(500), nullable=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=True)
    file_size: Mapped[int] = mapped_column(Integer, nullable=True)
    file_mime: Mapped[str] = mapped_column(String(100), nullable=True)
    
    is_edited: Mapped[bool] = mapped_column(Boolean, default=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Опрос, привязанный к сообщению
    poll_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chat_polls.id"), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    iteration = relationship("Iteration", back_populates="messages")
    user = relationship("User")
    poll = relationship("ChatPoll", uselist=False)


class ChatPoll(Base):
    __tablename__ = "chat_polls"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    creator_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    is_multiple: Mapped[bool] = mapped_column(Boolean, default=False)  # Множественный выбор
    is_closed: Mapped[bool] = mapped_column(Boolean, default=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    creator = relationship("User")
    options: Mapped[list["ChatPollOption"]] = relationship(back_populates="poll", cascade="all, delete-orphan")


class ChatPollOption(Base):
    __tablename__ = "chat_poll_options"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    poll_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chat_polls.id", ondelete="CASCADE"), nullable=False)
    text: Mapped[str] = mapped_column(String(255), nullable=False)
    order: Mapped[int] = mapped_column(Integer, default=0)
    
    poll: Mapped["ChatPoll"] = relationship(back_populates="options")
    votes: Mapped[list["ChatPollVote"]] = relationship(back_populates="option", cascade="all, delete-orphan")


class ChatPollVote(Base):
    __tablename__ = "chat_poll_votes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    option_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chat_poll_options.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    option: Mapped["ChatPollOption"] = relationship(back_populates="votes")
    user = relationship("User")
