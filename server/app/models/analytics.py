# Модель аналитических отчётов
import uuid
from datetime import datetime
from sqlalchemy import Text, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class AnalyticsReport(Base):
    __tablename__ = "analytics_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content: Mapped[str] = mapped_column(Text, nullable=False)  # Текст отчёта
    report_data: Mapped[str] = mapped_column(Text, nullable=True)  # JSON с метриками
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
