# Колонки доски итерации (YouGile-style)
import uuid
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class BoardColumn(Base):
    __tablename__ = "iteration_board_columns"
    __table_args__ = (Index("ix_board_column_iteration", "iteration_id", "sort_order"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    iteration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("iterations.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    color: Mapped[str] = mapped_column(String(30), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    iteration = relationship("Iteration", back_populates="board_columns")
    tasks = relationship("Task", back_populates="board_column", foreign_keys="Task.board_column_id")
