import hashlib
import secrets
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.middleware.auth import FULL_ACCESS_ROLES, get_current_user
from app.models.application import Application, ApplicationStatus
from app.models.customer_satisfaction import (
    CustomerSurveyToken,
    ProjectContribution,
    ProjectReview,
    PromoCode,
)
from app.models.notification import Notification
from app.models.project import Project, ProjectMember
from app.models.user import User


router = APIRouter(prefix="/customer-satisfaction", tags=["Удовлетворённость заказчика"])
public_router = APIRouter(prefix="/public/customer-surveys", tags=["Опрос заказчика"])


class ContributionIn(BaseModel):
    user_id: uuid.UUID
    weight: Decimal = Field(..., gt=0, le=1)


class SurveySubmit(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    comment: str = Field(..., min_length=10, max_length=5000)


def _token_hash(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def _get_application(db: AsyncSession, application_id: uuid.UUID) -> Application:
    result = await db.execute(select(Application).where(Application.id == application_id))
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    return app


def _require_management(user: User) -> None:
    if user.role not in FULL_ACCESS_ROLES:
        raise HTTPException(status_code=403, detail="Доступно владельцу и руководству")


async def _ensure_default_contributions(db: AsyncSession, project_id: uuid.UUID) -> list[ProjectContribution]:
    existing_result = await db.execute(
        select(ProjectContribution)
        .options(selectinload(ProjectContribution.user))
        .where(ProjectContribution.project_id == project_id)
        .order_by(ProjectContribution.user_id)
    )
    existing = list(existing_result.scalars().all())
    if existing:
        return existing

    members_result = await db.execute(
        select(ProjectMember).where(ProjectMember.project_id == project_id).order_by(ProjectMember.joined_at)
    )
    members = list(members_result.scalars().all())
    if not members:
        return []
    weight = (Decimal("1") / Decimal(len(members))).quantize(Decimal("0.00001"))
    remainder = Decimal("1") - weight * len(members)
    for index, member in enumerate(members):
        db.add(ProjectContribution(
            project_id=project_id,
            user_id=member.user_id,
            weight=weight + (remainder if index == 0 else Decimal("0")),
        ))
    await db.flush()
    refreshed = await db.execute(
        select(ProjectContribution)
        .options(selectinload(ProjectContribution.user))
        .where(ProjectContribution.project_id == project_id)
        .order_by(ProjectContribution.user_id)
    )
    return list(refreshed.scalars().all())


def _contribution_out(rows: list[ProjectContribution]) -> list[dict]:
    return [
        {
            "user_id": str(row.user_id),
            "user_name": row.user.name if row.user else str(row.user_id),
            "weight": float(row.weight),
        }
        for row in rows
    ]


@router.get("/applications/{application_id}")
async def get_satisfaction_setup(
    application_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_management(user)
    app = await _get_application(db, application_id)
    contributions = await _ensure_default_contributions(db, app.project_id) if app.project_id else []
    reviews_result = await db.execute(
        select(ProjectReview).where(ProjectReview.application_id == application_id).order_by(ProjectReview.submitted_at.desc())
    )
    reviews = list(reviews_result.scalars().all())
    return {
        "ready": app.status == ApplicationStatus.COMPLETED and app.project_id is not None,
        "project_id": str(app.project_id) if app.project_id else None,
        "contributions": _contribution_out(contributions),
        "reviews": [
            {
                "id": str(review.id),
                "rating": review.rating,
                "comment": review.comment,
                "submitted_at": review.submitted_at,
            }
            for review in reviews
        ],
    }


@router.put("/applications/{application_id}/contributions")
async def update_contributions(
    application_id: uuid.UUID,
    payload: list[ContributionIn],
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_management(user)
    app = await _get_application(db, application_id)
    if not app.project_id:
        raise HTTPException(status_code=409, detail="Сначала сформируйте проект из заявки")
    if not payload:
        raise HTTPException(status_code=422, detail="Укажите хотя бы одного участника")
    if abs(sum((item.weight for item in payload), Decimal("0")) - Decimal("1")) > Decimal("0.00001"):
        raise HTTPException(status_code=422, detail="Сумма весов участников должна быть равна 1,00")
    ids = [item.user_id for item in payload]
    if len(ids) != len(set(ids)):
        raise HTTPException(status_code=422, detail="Участник не может повторяться")
    members_result = await db.execute(
        select(ProjectMember.user_id).where(ProjectMember.project_id == app.project_id, ProjectMember.user_id.in_(ids))
    )
    if set(members_result.scalars().all()) != set(ids):
        raise HTTPException(status_code=422, detail="Вес можно назначить только участнику проекта")
    await db.execute(delete(ProjectContribution).where(ProjectContribution.project_id == app.project_id))
    for item in payload:
        db.add(ProjectContribution(project_id=app.project_id, user_id=item.user_id, weight=item.weight))
    await db.commit()
    rows = await _ensure_default_contributions(db, app.project_id)
    return {"contributions": _contribution_out(rows)}


@router.post("/applications/{application_id}/survey-link")
async def create_survey_link(
    application_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_management(user)
    app = await _get_application(db, application_id)
    if app.status != ApplicationStatus.COMPLETED or not app.project_id:
        raise HTTPException(status_code=409, detail="Опрос доступен после завершения заявки и создания проекта")
    contributions = await _ensure_default_contributions(db, app.project_id)
    if not contributions:
        raise HTTPException(status_code=409, detail="В проекте нет участников для расчёта KPI")
    raw = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(days=30)
    db.add(CustomerSurveyToken(
        application_id=app.id,
        project_id=app.project_id,
        token_hash=_token_hash(raw),
        created_by_id=user.id,
        expires_at=expires_at,
    ))
    await db.commit()
    return {"survey_path": f"/#/review/{raw}", "expires_at": expires_at}


async def _resolve_public_token(db: AsyncSession, raw_token: str) -> tuple[CustomerSurveyToken, Application, Project]:
    result = await db.execute(
        select(CustomerSurveyToken, Application, Project)
        .join(Application, Application.id == CustomerSurveyToken.application_id)
        .join(Project, Project.id == CustomerSurveyToken.project_id)
        .where(CustomerSurveyToken.token_hash == _token_hash(raw_token))
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Ссылка на опрос недействительна")
    token, app, project = row
    if token.used_at:
        raise HTTPException(status_code=409, detail="Отзыв по этой ссылке уже отправлен")
    if token.expires_at < datetime.utcnow():
        raise HTTPException(status_code=410, detail="Срок действия ссылки истёк")
    return token, app, project


@public_router.get("/{raw_token}")
async def get_public_survey(raw_token: str, db: AsyncSession = Depends(get_db)):
    token, app, project = await _resolve_public_token(db, raw_token)
    return {
        "project_name": project.name,
        "customer_name": app.client_name,
        "expires_at": token.expires_at,
    }


@public_router.post("/{raw_token}")
async def submit_public_survey(raw_token: str, payload: SurveySubmit, db: AsyncSession = Depends(get_db)):
    token, app, project = await _resolve_public_token(db, raw_token)
    comment = payload.comment.strip()
    if len(comment) < 10:
        raise HTTPException(status_code=422, detail="Комментарий должен содержать не менее 10 символов")
    review = ProjectReview(
        project_id=project.id,
        application_id=app.id,
        survey_token_id=token.id,
        customer_name=app.client_name,
        customer_email=app.client_email,
        rating=payload.rating,
        comment=comment,
    )
    db.add(review)
    await db.flush()
    promo = f"AGILE15-{secrets.token_hex(4).upper()}"
    valid_until = datetime.utcnow() + timedelta(days=90)
    db.add(PromoCode(review_id=review.id, code=promo, discount_percent=15, valid_until=valid_until))
    token.used_at = datetime.utcnow()

    contributions = await _ensure_default_contributions(db, project.id)
    for contribution in contributions:
        db.add(Notification(
            user_id=contribution.user_id,
            title="Новый отзыв заказчика",
            message=f"Проект «{project.name}» получил оценку {payload.rating}/5.",
            type="kpi",
            link="/kpi",
        ))
    await db.commit()
    return {
        "message": "Спасибо за отзыв",
        "promo_code": promo,
        "discount_percent": 15,
        "valid_until": valid_until,
    }
