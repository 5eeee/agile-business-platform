"""Operational KPI workflows that feed the calculators with real events."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.config import settings
from app.dependencies import get_current_user
from app.models.gamification import (
    AttentivenessLog,
    AttendanceLog,
    EmployeeIdea,
    EmployeeKPI8Points,
    KPI9Bonus,
    KPI7ManagerPoints,
    ManagerKPI4Points,
    ManagerResponsibility,
    ManagerOvertimeAction,
    OvertimeEvent,
    WeeklyReport,
    WeeklyReportReview,
)
from app.models.notification import Notification
from app.models.user import ADMIN_ROLES, User, UserRole


router = APIRouter(prefix="/gamification/kpi", tags=["KPI workflows"])

IDEA_SPHERES = {
    "technical",
    "process",
    "product",
    "marketing_pr",
    "resource_saving",
    "learning_development",
    "customer_service",
    "social_team",
    "other",
}
MANDATORY_REPORT_CRITERIA = {"1", "2", "3", "4", "5"}


class WeeklyReportDraftIn(BaseModel):
    criteria: dict[str, str] = Field(default_factory=dict)
    initiative_sphere: str | None = None
    week_start: datetime | None = None


class WeeklyReportReviewIn(BaseModel):
    checked_criteria: list[int] = Field(default_factory=list)
    comment: str | None = None


class IdeaCreateIn(BaseModel):
    idea_type: str = Field(..., min_length=2, max_length=50)
    sphere: str = Field(..., min_length=2, max_length=100)
    description: str = Field(..., min_length=1, max_length=5000)


class IdeaReviewIn(BaseModel):
    decision: str
    comment: str | None = None


def _week_start(value: datetime | None = None) -> datetime:
    current = value or _company_now()
    return datetime.combine((current - timedelta(days=current.weekday())).date(), datetime.min.time())


def _month_start(value: datetime) -> datetime:
    return value.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _company_now() -> datetime:
    return datetime.now(ZoneInfo(settings.COMPANY_TIMEZONE)).replace(tzinfo=None)


def _working_days_between(start: datetime, end: datetime) -> int:
    current = start.date()
    finish = end.date()
    total = 0
    while current < finish:
        current += timedelta(days=1)
        if current.weekday() < 5:
            total += 1
    return total


def _idea_payload(idea: EmployeeIdea, employee_name: str | None = None) -> dict:
    return {
        "id": str(idea.id),
        "employee_id": str(idea.employee_id),
        "employee_name": employee_name or (idea.employee.name if getattr(idea, "employee", None) else None),
        "manager_id": str(idea.manager_id) if idea.manager_id else None,
        "idea_type": idea.idea_type,
        "sphere": idea.sphere,
        "description": idea.description,
        "comment": idea.comment,
        "status": idea.status,
        "decision": idea.decision,
        "created_at": idea.created_at,
        "reviewed_at": idea.reviewed_at,
        "reaction_days": idea.reaction_days,
        "reaction_percentage": float(idea.reaction_percentage) if idea.reaction_percentage is not None else None,
    }


@router.post("/ideas")
async def create_idea(
    payload: IdeaCreateIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    idea = EmployeeIdea(
        employee_id=user.id,
        manager_id=user.manager_id,
        idea_type=payload.idea_type.strip(),
        sphere=payload.sphere.strip(),
        description=payload.description.strip(),
        status="submitted",
    )
    db.add(idea)
    await db.flush()
    recipients: list[uuid.UUID] = []
    if user.manager_id:
        recipients.append(user.manager_id)
    else:
        owners = await db.execute(select(User.id).where(User.role.in_([UserRole.OWNER, UserRole.DEPUTY_OWNER])))
        recipients.extend(owners.scalars().all())
    for recipient_id in set(recipients):
        db.add(Notification(
            user_id=recipient_id,
            title="Новая идея сотрудника",
            message=f"{user.name} отправил идею в сфере «{idea.sphere}».",
            type="kpi",
            link="/kpi",
        ))
    await db.commit()
    return _idea_payload(idea, user.name)


@router.get("/ideas/me")
async def get_my_ideas(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(EmployeeIdea).where(EmployeeIdea.employee_id == user.id).order_by(EmployeeIdea.created_at.desc())
    )
    return [_idea_payload(item, user.name) for item in result.scalars().all()]


@router.get("/ideas/pending")
async def get_pending_ideas(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = (
        select(EmployeeIdea, User.name)
        .join(User, User.id == EmployeeIdea.employee_id)
        .where(EmployeeIdea.status == "submitted")
        .order_by(EmployeeIdea.created_at)
    )
    if user.role not in ADMIN_ROLES:
        query = query.where(EmployeeIdea.manager_id == user.id)
    result = await db.execute(query)
    return [_idea_payload(idea, name) for idea, name in result.all()]


@router.post("/ideas/{idea_id}/review")
async def review_idea(
    idea_id: uuid.UUID,
    payload: IdeaReviewIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(EmployeeIdea).where(EmployeeIdea.id == idea_id))
    idea = result.scalar_one_or_none()
    if not idea:
        raise HTTPException(status_code=404, detail="Идея не найдена")
    if idea.status != "submitted":
        raise HTTPException(status_code=409, detail="Решение по идее уже принято")
    if user.role not in ADMIN_ROLES and idea.manager_id != user.id:
        raise HTTPException(status_code=403, detail="Можно рассматривать только идеи своих сотрудников")
    decision = payload.decision.strip().lower()
    if decision not in {"testing", "success", "fail"}:
        raise HTTPException(status_code=422, detail="Выберите решение по идее")
    comment = (payload.comment or "").strip()
    if decision == "fail" and len(comment) < 10:
        raise HTTPException(status_code=422, detail="При отклонении нужен комментарий не менее 10 символов")

    now = _company_now()
    days = _working_days_between(idea.created_at, now)
    scale = {0: 100, 1: 100, 2: 80, 3: 60, 4: 40, 5: 20}
    percentage = scale.get(days, 0)
    idea.manager_id = user.id
    idea.reviewed_at = now
    idea.decision = decision
    idea.status = decision
    idea.comment = comment or None
    idea.testing_start_date = now if decision == "testing" else None
    idea.reaction_days = days
    idea.reaction_percentage = Decimal(str(percentage))
    idea.is_counted_in_manager_kpi5 = days <= 5

    responsibility_points = Decimal("1") if days <= 1 else (Decimal("-1") if days > 5 else Decimal("0"))
    if responsibility_points:
        db.add(ManagerResponsibility(
            manager_id=user.id,
            date=now,
            event_type="idea_review",
            points=responsibility_points,
            description=f"Решение по идее за {days} раб. дн.",
            source_id=idea.id,
        ))
    month = _month_start(now)
    points_result = await db.execute(
        select(ManagerKPI4Points).where(ManagerKPI4Points.manager_id == user.id, ManagerKPI4Points.month == month)
    )
    attention = points_result.scalar_one_or_none()
    if not attention:
        attention = ManagerKPI4Points(manager_id=user.id, month=month, total_points=Decimal("0"))
        db.add(attention)
    attention.total_points = Decimal(str(attention.total_points or 0)) + Decimal("0.5")
    db.add(Notification(
        user_id=idea.employee_id,
        title="Решение по идее",
        message={"testing": "Идея отправлена на тестирование.", "success": "Идея одобрена без тестирования.", "fail": "Идея отклонена."}[decision],
        type="kpi",
        link="/kpi",
    ))
    await db.commit()
    return _idea_payload(idea)


def _report_payload(report: WeeklyReport, employee_name: str | None = None) -> dict:
    try:
        data = json.loads(report.report_data or "{}")
    except json.JSONDecodeError:
        data = {}
    return {
        "id": str(report.id),
        "employee_id": str(report.employee_id),
        "employee_name": employee_name,
        "manager_id": str(report.manager_id) if report.manager_id else None,
        "week_start": report.week_start,
        "submitted_at": report.submitted_at,
        "status": report.status,
        "criteria": data.get("criteria", {}),
        "initiative_sphere": data.get("initiative_sphere"),
        "created_at": report.created_at,
    }


async def _resolve_report_manager(db: AsyncSession, user: User) -> uuid.UUID | None:
    if user.manager_id:
        return user.manager_id
    if user.role == UserRole.OWNER:
        return None
    result = await db.execute(
        select(User.id)
        .where(User.role.in_([UserRole.OWNER, UserRole.DEPUTY_OWNER]), User.id != user.id)
        .order_by(User.created_at)
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _get_or_create_report(
    db: AsyncSession,
    user: User,
    requested_week: datetime | None,
) -> WeeklyReport:
    week = _week_start(requested_week)
    result = await db.execute(
        select(WeeklyReport).where(
            WeeklyReport.employee_id == user.id,
            WeeklyReport.week_start == week,
        )
    )
    report = result.scalar_one_or_none()
    if report:
        return report
    report = WeeklyReport(
        employee_id=user.id,
        manager_id=await _resolve_report_manager(db, user),
        week_start=week,
        report_data=json.dumps({"criteria": {}, "initiative_sphere": None}, ensure_ascii=False),
        status="draft",
    )
    db.add(report)
    await db.flush()
    return report


def _validate_report(data: dict) -> list[str]:
    criteria = data.get("criteria") if isinstance(data.get("criteria"), dict) else {}
    errors: list[str] = []
    for key in sorted(MANDATORY_REPORT_CRITERIA):
        value = str(criteria.get(key, "")).strip()
        if len(value) < 10:
            errors.append(f"критерий {key}: минимум 10 символов")

    plans = str(criteria.get("4", "")).strip()
    plan_items = [item.strip() for item in re.split(r"[\n;•]+", plans) if item.strip()]
    if len(plan_items) < 3:
        errors.append("критерий 4: укажите минимум 3 пункта плана с новой строки")

    initiative = str(criteria.get("6", "")).strip()
    sphere = str(data.get("initiative_sphere") or "").strip()
    if initiative or sphere:
        if len(initiative) < 10:
            errors.append("критерий 6: минимум 10 символов")
        if sphere not in IDEA_SPHERES:
            errors.append("критерий 6: выберите сферу инициативы")
    return errors


@router.get("/reports/me")
async def get_my_weekly_report(
    week_start: datetime | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    report = await _get_or_create_report(db, user, week_start)
    await db.commit()
    return _report_payload(report, f"{user.last_name or ''} {user.name}".strip())


@router.put("/reports/me")
async def save_my_weekly_report(
    payload: WeeklyReportDraftIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    report = await _get_or_create_report(db, user, payload.week_start)
    if report.status == "approved":
        raise HTTPException(status_code=409, detail="Принятый отчёт нельзя изменять")
    clean_criteria = {str(key): str(value).strip() for key, value in payload.criteria.items() if str(key) in {"1", "2", "3", "4", "5", "6"}}
    report.report_data = json.dumps(
        {"criteria": clean_criteria, "initiative_sphere": payload.initiative_sphere},
        ensure_ascii=False,
    )
    if report.status != "rework":
        report.status = "draft"
    await db.commit()
    return _report_payload(report, f"{user.last_name or ''} {user.name}".strip())


@router.post("/reports/me/submit")
async def submit_my_weekly_report(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    report = await _get_or_create_report(db, user, None)
    if report.status == "approved":
        raise HTTPException(status_code=409, detail="Отчёт уже принят")
    try:
        data = json.loads(report.report_data or "{}")
    except json.JSONDecodeError:
        data = {}
    errors = _validate_report(data)
    now = _company_now()
    attempt_result = await db.execute(
        select(func.count(AttentivenessLog.id)).where(
            AttentivenessLog.action_type == "weekly_report",
            AttentivenessLog.action_id == str(report.id),
        )
    )
    attempt_number = int(attempt_result.scalar() or 0) + 1
    friday_deadline = report.week_start + timedelta(days=4, hours=22)
    is_overtime = now > friday_deadline and now.weekday() in {4, 5, 6}
    attention = AttentivenessLog(
        user_id=user.id,
        action_type="weekly_report",
        action_id=str(report.id),
        attempt_number=attempt_number,
        success=not errors,
        is_overtime=is_overtime,
        penalty_points=Decimal("0"),
        created_at=now,
    )
    db.add(attention)
    await db.flush()

    if errors:
        await db.commit()
        raise HTTPException(status_code=422, detail="; ".join(errors))

    previous_success_result = await db.execute(
        select(func.count(AttentivenessLog.id)).where(
            AttentivenessLog.action_type == "weekly_report",
            AttentivenessLog.action_id == str(report.id),
            AttentivenessLog.success == True,
            AttentivenessLog.id != attention.id,
        )
    )
    first_success = int(previous_success_result.scalar() or 0) == 0
    failed_before_result = await db.execute(
        select(func.count(AttentivenessLog.id)).where(
            AttentivenessLog.action_type == "weekly_report",
            AttentivenessLog.action_id == str(report.id),
            AttentivenessLog.success == False,
        )
    )
    failed_before = int(failed_before_result.scalar() or 0) > 0

    if first_success:
        attention_points = (
            Decimal("-0.25") if is_overtime else Decimal("-0.5")
        ) if failed_before else (
            Decimal("1.0") if is_overtime else Decimal("0.5")
        )
        attention.penalty_points = attention_points
        db.add(EmployeeKPI8Points(
            employee_id=user.id,
            month=_month_start(now),
            points=attention_points,
            source_action_id=attention.id,
        ))

        if is_overtime:
            percent = Decimal("5") if failed_before else Decimal("10")
            count_result = await db.execute(
                select(func.count(OvertimeEvent.id)).where(
                    OvertimeEvent.employee_id == user.id,
                    OvertimeEvent.month == _month_start(now),
                )
            )
            db.add(OvertimeEvent(
                employee_id=user.id,
                month=_month_start(now),
                order_number=int(count_result.scalar() or 0) + 1,
                event_type="weekly_report_poor" if failed_before else "weekly_report_quality",
                percent_awarded=percent,
                source_id=report.id,
            ))
            db.add(KPI9Bonus(
                employee_id=user.id,
                month=_month_start(now),
                event_type="weekly_report_overtime",
                percent=percent,
                source_id=report.id,
            ))

        criteria = data.get("criteria", {})
        initiative = str(criteria.get("6", "")).strip()
        sphere = str(data.get("initiative_sphere") or "").strip()
        if initiative and sphere in IDEA_SPHERES:
            db.add(EmployeeIdea(
                employee_id=user.id,
                idea_type=sphere,
                description=initiative,
                status="testing",
                testing_start_date=now,
                created_at=now,
            ))

    report.submitted_at = now
    report.status = "on_review"
    report.manager_id = report.manager_id or await _resolve_report_manager(db, user)
    if report.manager_id:
        db.add(Notification(
            user_id=report.manager_id,
            title="Еженедельный отчёт на проверке",
            message=f"{user.last_name or ''} {user.name} отправил(а) отчёт за неделю.",
            type="kpi",
            link="#/kpi",
        ))
    await db.commit()
    return _report_payload(report, f"{user.last_name or ''} {user.name}".strip())


@router.get("/reports/pending")
async def list_pending_weekly_reports(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = (
        select(WeeklyReport, User)
        .join(User, User.id == WeeklyReport.employee_id)
        .where(WeeklyReport.status == "on_review")
        .order_by(WeeklyReport.submitted_at)
    )
    if user.role not in ADMIN_ROLES:
        query = query.where(WeeklyReport.manager_id == user.id)
    rows = (await db.execute(query)).all()
    return [_report_payload(report, f"{employee.last_name or ''} {employee.name}".strip()) for report, employee in rows]


@router.post("/reports/{report_id}/review")
async def review_weekly_report(
    report_id: uuid.UUID,
    payload: WeeklyReportReviewIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    report = await db.get(WeeklyReport, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Отчёт не найден")
    if user.role not in ADMIN_ROLES and report.manager_id != user.id:
        raise HTTPException(status_code=403, detail="Нет доступа к проверке этого отчёта")
    if report.status != "on_review":
        raise HTTPException(status_code=409, detail="Отчёт сейчас не находится на проверке")

    checked = sorted({int(item) for item in payload.checked_criteria if 1 <= int(item) <= 6})
    mandatory_ok = {1, 2, 3, 4, 5}.issubset(set(checked))
    status = "approved" if mandatory_ok else "rework"
    comment = (payload.comment or "").strip()
    if status == "rework" and len(comment) < 3:
        raise HTTPException(status_code=422, detail="Для доработки обязательно укажите пояснение")

    now = _company_now()
    review = WeeklyReportReview(
        report_id=report.id,
        reviewer_id=user.id,
        reviewed_at=now,
        checked_criteria=json.dumps(checked),
        comment=comment or None,
        status=status,
        created_at=now,
    )
    db.add(review)
    report.status = status

    if now.weekday() in {5, 6}:
        existing = await db.execute(
            select(ManagerOvertimeAction.id).where(
                ManagerOvertimeAction.manager_id == user.id,
                ManagerOvertimeAction.action_type == "weekly_report_review",
                ManagerOvertimeAction.source_id == report.id,
            )
        )
        if existing.scalar_one_or_none() is None:
            db.add(ManagerOvertimeAction(
                manager_id=user.id,
                month=_month_start(now),
                action_type="weekly_report_review",
                source_id=report.id,
                percent_awarded=Decimal("10"),
                awarded_at=now,
            ))

    points_result = await db.execute(
        select(KPI7ManagerPoints).where(
            KPI7ManagerPoints.manager_id == user.id,
            KPI7ManagerPoints.month == _month_start(now),
        )
    )
    points = points_result.scalar_one_or_none()
    if not points:
        points = KPI7ManagerPoints(manager_id=user.id, month=_month_start(now), total_points=Decimal("0"))
        db.add(points)
    if status == "approved":
        points.total_points = Decimal(str(points.total_points or 0)) + Decimal("1")

    db.add(Notification(
        user_id=report.employee_id,
        title="Еженедельный отчёт принят" if status == "approved" else "Еженедельный отчёт возвращён",
        message="Отчёт принят руководителем." if status == "approved" else comment,
        type="kpi",
        link="#/kpi",
    ))
    await db.commit()
    return {"status": status, "checked_criteria": checked, "comment": comment or None}


def _attendance_payload(row: AttendanceLog | None, now: datetime) -> dict:
    return {
        "date": datetime.combine(now.date(), datetime.min.time()),
        "check_in": row.check_in if row else None,
        "check_out": row.check_out if row else None,
        "late_minutes": int(row.late_minutes or 0) if row else 0,
        "early_leave_minutes": int(row.early_leave_minutes or 0) if row else 0,
        "penalty_points": float(row.penalty_points or 0) if row else 0.0,
        "is_weekend": now.weekday() >= 5,
    }


async def _today_attendance(db: AsyncSession, employee_id: uuid.UUID, now: datetime) -> AttendanceLog | None:
    day = datetime.combine(now.date(), datetime.min.time())
    result = await db.execute(
        select(AttendanceLog).where(
            AttendanceLog.employee_id == employee_id,
            AttendanceLog.date == day,
        )
    )
    return result.scalar_one_or_none()


@router.get("/attendance/today")
async def get_today_attendance(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    now = _company_now()
    return _attendance_payload(await _today_attendance(db, user.id, now), now)


@router.post("/attendance/check-in")
async def attendance_check_in(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    now = _company_now()
    row = await _today_attendance(db, user.id, now)
    if row and row.check_in:
        raise HTTPException(status_code=409, detail="Приход за сегодня уже зафиксирован")
    if not row:
        row = AttendanceLog(
            employee_id=user.id,
            date=datetime.combine(now.date(), datetime.min.time()),
            penalty_points=Decimal("0"),
        )
        db.add(row)
    row.check_in = now
    if now.weekday() < 5:
        planned = now.replace(hour=9, minute=0, second=0, microsecond=0)
        if now > planned + timedelta(minutes=15):
            row.late_minutes = max(1, int((now - planned).total_seconds() // 60))
            row.penalty_points = Decimal(str(row.penalty_points or 0)) + Decimal("1")
    await db.commit()
    return _attendance_payload(row, now)


@router.post("/attendance/check-out")
async def attendance_check_out(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    now = _company_now()
    row = await _today_attendance(db, user.id, now)
    if row and row.check_out:
        raise HTTPException(status_code=409, detail="Уход за сегодня уже зафиксирован")
    if not row:
        row = AttendanceLog(
            employee_id=user.id,
            date=datetime.combine(now.date(), datetime.min.time()),
            penalty_points=Decimal("0"),
        )
        db.add(row)
    row.check_out = now
    if now.weekday() < 5:
        planned_end = now.replace(hour=18, minute=0, second=0, microsecond=0)
        if now < planned_end - timedelta(minutes=15):
            row.early_leave_minutes = max(1, int((planned_end - now).total_seconds() // 60))
            row.penalty_points = Decimal(str(row.penalty_points or 0)) + Decimal("1")
        if not row.check_in:
            row.penalty_points = Decimal(str(row.penalty_points or 0)) + Decimal("0.5")
    await db.commit()
    return _attendance_payload(row, now)
