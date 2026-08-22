import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class FinancialOperationCreate(BaseModel):
    operation_type: Literal["income", "expense"]
    category: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=1, max_length=2000)
    amount: float = Field(..., gt=0, le=999_999_999_999)
    occurred_at: datetime | None = None

    @field_validator("category", "description")
    @classmethod
    def trim_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Поле не может быть пустым")
        return value


class FinancialOperationOut(BaseModel):
    id: uuid.UUID
    operation_type: str
    category: str
    description: str
    amount: float
    occurred_at: datetime
    created_by_id: uuid.UUID
    created_at: datetime

    class Config:
        from_attributes = True


class FinanceSummaryOut(BaseModel):
    income: float
    expense: float
    profit: float
    operations_count: int
    date_from: datetime | None = None
    date_to: datetime | None = None
