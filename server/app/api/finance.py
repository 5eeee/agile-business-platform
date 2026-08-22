import uuid
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.finance import FinancialOperation
from app.models.user import User, UserRole
from app.schemas.finance import FinancialOperationCreate, FinancialOperationOut, FinanceSummaryOut


router = APIRouter(prefix="/finance", tags=["Финансы владельца"])


def _require_owner(user: User) -> User:
    if user.role != UserRole.OWNER:
        raise HTTPException(status_code=403, detail="Финансовая аналитика доступна только владельцу")
    return user


def _period_filters(date_from: datetime | None, date_to: datetime | None) -> list[object]:
    filters: list[object] = []
    if date_from:
        filters.append(FinancialOperation.occurred_at >= date_from)
    if date_to:
        filters.append(FinancialOperation.occurred_at <= date_to)
    return filters


@router.get("/operations", response_model=list[FinancialOperationOut])
async def list_financial_operations(
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[FinancialOperation]:
    _require_owner(current_user)
    query = select(FinancialOperation).where(*_period_filters(date_from, date_to)).order_by(
        FinancialOperation.occurred_at.desc(), FinancialOperation.created_at.desc(),
    )
    result = await db.execute(query)
    return list(result.scalars().all())


@router.get("/summary", response_model=FinanceSummaryOut)
async def get_finance_summary(
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FinanceSummaryOut:
    _require_owner(current_user)
    filters = _period_filters(date_from, date_to)
    income_result = await db.execute(
        select(func.coalesce(func.sum(FinancialOperation.amount), 0)).where(
            FinancialOperation.operation_type == "income", *filters,
        )
    )
    expense_result = await db.execute(
        select(func.coalesce(func.sum(FinancialOperation.amount), 0)).where(
            FinancialOperation.operation_type == "expense", *filters,
        )
    )
    count_result = await db.execute(select(func.count(FinancialOperation.id)).where(*filters))
    income = Decimal(str(income_result.scalar() or 0))
    expense = Decimal(str(expense_result.scalar() or 0))
    return FinanceSummaryOut(
        income=float(income),
        expense=float(expense),
        profit=float(income - expense),
        operations_count=int(count_result.scalar() or 0),
        date_from=date_from,
        date_to=date_to,
    )


@router.post("/operations", response_model=FinancialOperationOut, status_code=201)
async def create_financial_operation(
    data: FinancialOperationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FinancialOperation:
    owner = _require_owner(current_user)
    operation = FinancialOperation(
        operation_type=data.operation_type,
        category=data.category,
        description=data.description,
        amount=Decimal(str(data.amount)).quantize(Decimal("0.01")),
        occurred_at=data.occurred_at or datetime.utcnow(),
        created_by_id=owner.id,
    )
    db.add(operation)
    await db.commit()
    await db.refresh(operation)
    return operation


@router.delete("/operations/{operation_id}", status_code=204)
async def delete_financial_operation(
    operation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    _require_owner(current_user)
    result = await db.execute(select(FinancialOperation).where(FinancialOperation.id == operation_id))
    operation = result.scalar_one_or_none()
    if not operation:
        raise HTTPException(status_code=404, detail="Финансовая операция не найдена")
    await db.delete(operation)
    await db.commit()
