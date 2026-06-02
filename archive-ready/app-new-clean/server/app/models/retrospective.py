# Модель ретроспективы
import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Retrospective(Base):
    __tablename__ = "retrospectives"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    iteration_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("iterations.id", ondelete="CASCADE"), nullable=False, unique=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    iteration = relationship("Iteration", back_populates="retrospective")
    answers: Mapped[list["RetrospectiveAnswer"]] = relationship(back_populates="retrospective", cascade="all, delete-orphan")


class RetrospectiveAnswer(Base):
    __tablename__ = "retrospective_answers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    retrospective_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("retrospectives.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    went_well: Mapped[str] = mapped_column(Text, nullable=True)        # Что прошло хорошо?
    to_improve: Mapped[str] = mapped_column(Text, nullable=True)       # Что можно улучшить?
    to_try: Mapped[str] = mapped_column(Text, nullable=True)           # Что попробуем в следующий раз?
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    retrospective: Mapped["Retrospective"] = relationship(back_populates="answers")
    user = relationship("User")
