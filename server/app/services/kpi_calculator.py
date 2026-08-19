import uuid
import math
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any

from sqlalchemy import select, func, and_, or_, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.task import Task
from app.models.gamification import (
    AttendanceLog, EmployeeIdea, EmployeeActivityLog, TaskReturn,
    OvertimeEvent, HelpLog, KPI9Bonus, KPI9Cache, WeeklyReport,
    WeeklyReportReview, EmployeeKPIHistory, ManagerKPI2Cache,
    ManagerKPI4Points, ManagerResponsibility, EmployeeKPI8Points,
    KPIManagerHistory, PerformanceReview, ManagerOvertimeCounter, ManagerOvertimeAction,
    KPI7ManagerPoints
)
from app.models.customer_satisfaction import ProjectContribution, ProjectReview


def calculate_working_hours(start_ts: datetime, end_ts: datetime) -> Decimal:
    """
    Чистые рабочие часы по базовому графику Пн–Пт 09:00–18:00
    с исключением обеда 13:00–14:00. Индивидуальные графики можно
    подключить без изменения формул KPI через этот единый слой.
    """
    if start_ts >= end_ts:
        return Decimal("0.0")
    
    total_minutes = 0
    current_date = start_ts.date()
    end_date = end_ts.date()
    
    while current_date <= end_date:
        if current_date.weekday() < 5:  # Понедельник-Пятница
            day_start = datetime.combine(current_date, datetime.min.time())
            for work_start, work_end in (
                (day_start + timedelta(hours=9), day_start + timedelta(hours=13)),
                (day_start + timedelta(hours=14), day_start + timedelta(hours=18)),
            ):
                intersect_start = max(start_ts, work_start)
                intersect_end = min(end_ts, work_end)
                if intersect_start < intersect_end:
                    total_minutes += (intersect_end - intersect_start).total_seconds() / 60.0
                
        current_date += timedelta(days=1)
        
    return Decimal(str(total_minutes / 60.0)).quantize(Decimal("0.01"))


def calculate_working_days(start_ts: datetime, end_ts: datetime) -> Decimal:
    """Рабочие дни для KPI руководителя: 8 часов = 1 рабочий день."""
    hours = calculate_working_hours(start_ts, end_ts)
    return (hours / Decimal("8.0")).quantize(Decimal("0.1"))


def punctuality_score(total_penalty: Decimal, max_consecutive_lates: int = 0) -> Decimal:
    """Чистая функция шкалы KPI2 из документа."""
    if total_penalty <= 0:
        value = Decimal("100")
    elif total_penalty <= 1:
        value = Decimal("95")
    elif total_penalty <= 2:
        value = Decimal("90")
    elif total_penalty <= 3:
        value = Decimal("85")
    elif total_penalty <= 4:
        value = Decimal("75")
    elif total_penalty <= 5:
        value = Decimal("70")
    else:
        value = Decimal("60")
    if max_consecutive_lates >= 5:
        value = max(Decimal("0"), value - Decimal("30"))
    return value.quantize(Decimal("1"))


async def validate_and_apply_excuse(db: AsyncSession, employee_id: uuid.UUID, task: Task) -> bool:
    """
    Проверяет лимиты уважительных причин для KPI1 (Deadlines) для сотрудника.
    Правила:
    - Не более 3 уважительных причин в месяц.
    - Не более 2 одинаковых причин в месяц.
    - Нельзя использовать уважительную причину два раза подряд (по дате завершения/сдачи).
    Возвращает True, если уважительная причина применима, иначе False.
    """
    if not task.has_excuse or not task.excuse_reason:
        return False

    deadline = task.deadline or datetime.utcnow()
    month_start = datetime(deadline.year, deadline.month, 1)
    month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(seconds=1)

    # 1. Лимит: не более 3 уважительных причин в месяц
    monthly_excuses_res = await db.execute(
        select(Task).where(
            Task.assignee_id == employee_id,
            Task.has_excuse == True,
            Task.updated_at >= month_start,
            Task.updated_at <= month_end,
            Task.id != task.id
        )
    )
    monthly_excuses = monthly_excuses_res.scalars().all()
    if len(monthly_excuses) >= 3:
        return False

    # 2. Лимит: не более 2 одинаковых причин в месяц
    same_reason_count = sum(1 for t in monthly_excuses if t.excuse_reason == task.excuse_reason)
    if same_reason_count >= 2:
        return False

    # 3. Лимит: не подряд
    # Ищем предыдущую задачу, имевшую отметку
    prev_task_res = await db.execute(
        select(Task).where(
            Task.assignee_id == employee_id,
            Task.is_completed == True,
            Task.updated_at < task.updated_at,
            Task.id != task.id
        ).order_by(Task.updated_at.desc()).limit(1)
    )
    prev_task = prev_task_res.scalar_one_or_none()
    if prev_task and prev_task.has_excuse:
        return False

    return True


async def calculate_kpi1_deadlines(db: AsyncSession, employee_id: uuid.UUID, period_start: datetime, period_end: datetime) -> Optional[Decimal]:
    """
    KPI 1: Соблюдение дедлайнов.
    KPI1 = (tasks_in_time / actual_tasks) * 100
    actual_tasks = tasks_in_time + tasks_overdue
    Исключаются задачи с уважительной причиной (если прошли валидацию) и расхождениями (is_discrepancy).
    """
    tasks_res = await db.execute(
        select(Task).where(
            Task.assignee_id == employee_id,
            Task.is_completed == True,
            Task.updated_at >= period_start,
            Task.updated_at <= period_end
        )
    )
    tasks = tasks_res.scalars().all()

    in_time_count = 0
    overdue_count = 0

    for t in tasks:
        if t.is_discrepancy:
            continue
        
        if t.kpi_status == "in_time":
            in_time_count += 1
        elif t.kpi_status == "overdue":
            if t.has_excuse:
                # Проверим, проходит ли по лимитам
                is_valid = await validate_and_apply_excuse(db, employee_id, t)
                if is_valid:
                    # Исключается из расчёта
                    continue
                else:
                    # Лимит превышен -> идёт в просрочку
                    overdue_count += 1
            else:
                overdue_count += 1
        elif t.kpi_status == "excused":
            # Проверяем лимиты
            is_valid = await validate_and_apply_excuse(db, employee_id, t)
            if is_valid:
                continue
            else:
                overdue_count += 1

    total = in_time_count + overdue_count
    if total == 0:
        return None
    
    return (Decimal(str(in_time_count)) / Decimal(str(total)) * Decimal("100.0")).quantize(Decimal("1"))


async def calculate_kpi2_punctuality(db: AsyncSession, employee_id: uuid.UUID, period_start: datetime, period_end: datetime) -> Optional[Decimal]:
    """
    KPI 2: Пунктуальность / Индекс дисциплины рабочего времени.
    Недельная ступенчатая шкала из документа: 0/1/2/3/4/5/6+
    баллов дают 100/95/90/85/75/70/60 процентов. Пять опозданий
    подряд дополнительно уменьшают результат на 30 п.п.
    """
    now = min(datetime.utcnow(), period_end)
    week_start = datetime.combine((now - timedelta(days=now.weekday())).date(), datetime.min.time())
    res = await db.execute(
        select(AttendanceLog).where(
            AttendanceLog.employee_id == employee_id,
            AttendanceLog.date >= max(period_start, week_start),
            AttendanceLog.date <= now,
        )
    )
    logs = list(res.scalars().all())
    total_penalty = sum((Decimal(str(row.penalty_points or 0)) for row in logs), Decimal("0"))
    late_dates = sorted({row.date.date() for row in logs if int(row.late_minutes or 0) > 0})
    consecutive = 1
    max_consecutive = 1 if late_dates else 0
    for previous, current in zip(late_dates, late_dates[1:]):
        expected = previous + timedelta(days=1)
        while expected.weekday() >= 5:
            expected += timedelta(days=1)
        consecutive = consecutive + 1 if current == expected else 1
        max_consecutive = max(max_consecutive, consecutive)
    return punctuality_score(total_penalty, max_consecutive)


async def calculate_kpi3_initiative(db: AsyncSession, employee_id: uuid.UUID, period_start: datetime, period_end: datetime) -> Optional[Decimal]:
    """
    KPI 3: Индекс инициативности и заинтересованности.
    Формула: KPI3 = 0.2 * (% идей) + 0.5 * (% мероприятий) + 0.3 * (% интереса)
    % идей = min(sum(weights) * 100, 100)
    % мероприятий: 0=0%, 1=50%, >=2=100%
    % интереса: 0=0%, 1=10%, 2=20%, ..., >=10=100%
    """
    # 1. Идеи
    ideas_res = await db.execute(
        select(EmployeeIdea).where(
            EmployeeIdea.employee_id == employee_id,
            EmployeeIdea.created_at >= period_start,
            EmployeeIdea.created_at <= period_end
        )
    )
    ideas = ideas_res.scalars().all()
    idea_weight = Decimal("0.0")
    for idea in ideas:
        if idea.status == "testing":
            idea_weight += Decimal("0.0625")
        elif idea.status == "success":
            idea_weight += Decimal("0.25")
            
    ideas_pct = min(idea_weight * Decimal("100.0"), Decimal("100.0"))

    # 2. Мероприятия
    events_res = await db.execute(
        select(func.count()).where(
            EmployeeActivityLog.employee_id == employee_id,
            EmployeeActivityLog.activity_type == "event",
            EmployeeActivityLog.date >= period_start,
            EmployeeActivityLog.date <= period_end
        )
    )
    events_count = events_res.scalar() or 0
    if events_count == 0:
        events_pct = Decimal("0.0")
    elif events_count == 1:
        events_pct = Decimal("50.0")
    else:
        events_pct = Decimal("100.0")

    # 3. Интерес
    interest_res = await db.execute(
        select(func.count()).where(
            EmployeeActivityLog.employee_id == employee_id,
            EmployeeActivityLog.activity_type == "interest",
            EmployeeActivityLog.date >= period_start,
            EmployeeActivityLog.date <= period_end
        )
    )
    interest_count = interest_res.scalar() or 0
    interest_pct = min(Decimal(str(interest_count * 10)) , Decimal("100.0"))

    if len(ideas) == 0 and events_count == 0 and interest_count == 0:
        return None

    kpi3 = Decimal("0.2") * ideas_pct + Decimal("0.5") * events_pct + Decimal("0.3") * interest_pct
    return kpi3.quantize(Decimal("1.0"))


async def calculate_kpi4_overtime_load(db: AsyncSession, employee_id: uuid.UUID, period_start: datetime, period_end: datetime) -> Optional[Decimal]:
    """
    KPI 4: Индекс сверхурочной загрузки.
    Сумма начисленных процентов, ограничено 100%.
    """
    res = await db.execute(
        select(func.coalesce(func.sum(OvertimeEvent.percent_awarded), 0)).where(
            OvertimeEvent.employee_id == employee_id,
            OvertimeEvent.month >= period_start,
            OvertimeEvent.month <= period_end
        )
    )
    total_pct = Decimal(str(res.scalar() or 0.0))
    return min(total_pct, Decimal("100.0")).quantize(Decimal("0.1"))


async def calculate_kpi5_quality(db: AsyncSession, employee_id: uuid.UUID, period_start: datetime, period_end: datetime) -> Optional[Decimal]:
    """
    KPI 5: Качество выполнения работ.
    Индекс_качества_для_рейтинга = 100% – Исходный_KPI5_%
    Исходный_KPI5_% = total_penalty_weight
    """
    res = await db.execute(
        select(func.coalesce(func.sum(TaskReturn.total_weight), 0)).where(
            TaskReturn.employee_id == employee_id,
            TaskReturn.return_time >= period_start,
            TaskReturn.return_time <= period_end,
            TaskReturn.is_external == False
        )
    )
    total_penalty = Decimal(str(res.scalar() or 0.0))
    val = Decimal("100.0") - total_penalty
    return max(Decimal("0.0"), min(Decimal("100.0"), val)).quantize(Decimal("0.1"))


async def calculate_kpi8_attentiveness(db: AsyncSession, employee_id: uuid.UUID, period_start: datetime, period_end: datetime) -> Optional[Decimal]:
    """
    KPI 8: Индекс внимательности сотрудника.
    KPI8_% = max(0, min(100, (сумма_баллов / 20) * 100%))
    """
    res = await db.execute(
        select(func.coalesce(func.sum(EmployeeKPI8Points.points), 0)).where(
            EmployeeKPI8Points.employee_id == employee_id,
            EmployeeKPI8Points.month >= period_start,
            EmployeeKPI8Points.month <= period_end
        )
    )
    points_sum = Decimal(str(res.scalar() or 0.0))
    val = (points_sum / Decimal("20.0")) * Decimal("100.0")
    return max(Decimal("0.0"), min(Decimal("100.0"), val)).quantize(Decimal("0.1"))


async def calculate_kpi9_bonus(db: AsyncSession, employee_id: uuid.UUID, period_start: datetime, period_end: datetime) -> Optional[Decimal]:
    """
    KPI 9: Бонусный индекс активности.
    Накопленная сумма процентов по бонусам.
    """
    value, _carry = await calculate_kpi9_bonus_breakdown(db, employee_id, period_start, period_end)
    return value


async def calculate_kpi9_bonus_breakdown(
    db: AsyncSession,
    employee_id: uuid.UUID,
    period_start: datetime,
    period_end: datetime,
) -> tuple[Decimal, Decimal]:
    """Cap the visible month at 100 and carry every excess point forward."""
    target_month = period_start.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    rows = await db.execute(
        select(KPI9Bonus.month, func.coalesce(func.sum(KPI9Bonus.percent), 0))
        .where(KPI9Bonus.employee_id == employee_id, KPI9Bonus.month <= period_end)
        .group_by(KPI9Bonus.month)
        .order_by(KPI9Bonus.month)
    )
    monthly = {
        month.replace(day=1, hour=0, minute=0, second=0, microsecond=0): Decimal(str(total or 0))
        for month, total in rows.all()
    }
    carry = Decimal("0.0")
    current_value = Decimal("0.0")
    for month in sorted(set(monthly) | {target_month}):
        if month > target_month:
            break
        available = monthly.get(month, Decimal("0.0")) + carry
        current_value = min(available, Decimal("100.0"))
        carry = max(Decimal("0.0"), available - Decimal("100.0"))
    return current_value.quantize(Decimal("0.1")), carry.quantize(Decimal("0.1"))


async def calculate_kpi10_responsibility(db: AsyncSession, employee_id: uuid.UUID, period_start: datetime, period_end: datetime) -> Optional[Decimal]:
    """
    KPI 10: Индекс ответственности сотрудника.
    KPI10_% = max(0, min(100, (сумма_баллов / 20) * 100%))
    Вычисляется динамически на основе:
    - Нарушений дедлайнов подчинённым/сотрудником (если применимо)
    - Своевременности сдачи еженедельных отчётов (WeeklyReport)
    - Валидации отчётов (WeeklyReportReview)
    """
    points = Decimal("0.0")
    has_events = False

    # +1 за каждый завершившийся календарный день без принятой просрочки.
    today = min(datetime.utcnow(), period_end).date()
    cursor = period_start.date()
    accepted_tasks_res = await db.execute(
        select(Task).where(
            Task.assignee_id == employee_id,
            Task.is_completed == True,
            Task.updated_at >= period_start,
            Task.updated_at <= period_end,
        )
    )
    accepted_tasks = list(accepted_tasks_res.scalars().all())
    overdue_dates = {
        task.deadline.date()
        for task in accepted_tasks
        if task.deadline and task.kpi_status == "overdue" and not task.has_excuse and not task.is_discrepancy
    }
    while cursor < today:
        has_events = True
        if cursor not in overdue_dates:
            points += Decimal("1")
        cursor += timedelta(days=1)

    # 1. Еженедельные отчёты:
    # - Отчёт не отправлен в срок (до 22:00 пятницы) -> -3 балла
    # - При наличии всех обязательных критериев (1-5) -> +1 балл
    # - Доп критерий "Инициативы" (6) -> +1 балл
    reports_res = await db.execute(
        select(WeeklyReport).where(
            WeeklyReport.employee_id == employee_id,
            WeeklyReport.created_at >= period_start,
            WeeklyReport.created_at <= period_end
        )
    )
    reports = reports_res.scalars().all()
    for r in reports:
        has_events = True
        # Проверяем своевременность
        # Крайний срок: пятница 22:00
        # Найдем пятницу той недели
        days_to_friday = (4 - r.week_start.weekday()) % 7
        friday_deadline = datetime.combine(r.week_start.date() + timedelta(days=days_to_friday), datetime.min.time()) + timedelta(hours=22)
        
        if not r.submitted_at or r.submitted_at > friday_deadline:
            points -= Decimal("3.0")
            
        # Проверим разборы / критерии
        review_res = await db.execute(
            select(WeeklyReportReview).where(WeeklyReportReview.report_id == r.id)
        )
        review = review_res.scalar_one_or_none()
        if review:
            import json
            try:
                criteria = json.loads(review.checked_criteria)
            except Exception:
                criteria = []
            
            # Обязательные критерии 1-5
            mandatory = {1, 2, 3, 4, 5}
            criteria_set = set(criteria)
            
            missing_count = len(mandatory - criteria_set)
            points -= Decimal(str(missing_count))  # -1 за каждый отсутствующий
            
            if missing_count == 0:
                points += Decimal("1.0")  # все 1-5 на месте
                
            if 6 in criteria_set:
                points += Decimal("1.0")  # инициативы на месте

    # 2. Быстрые исправления ошибок (KPI10.2):
    # - Быстрое исправление критической ошибки (+2 балла)
    # - Средней или мелкой (+1 балл)
    returns_res = await db.execute(
        select(TaskReturn).where(
            TaskReturn.employee_id == employee_id,
            TaskReturn.return_time >= period_start,
            TaskReturn.return_time <= period_end
        )
    )
    returns = returns_res.scalars().all()
    for ret in returns:
        if ret.resend_time:
            has_events = True
            norm_hours = Decimal("4.0") if ret.error_category == "critical" else (Decimal("6.0") if ret.error_category == "medium" else Decimal("8.0"))
            if ret.effective_hours is not None and ret.effective_hours <= norm_hours:
                points += Decimal("1.0")

    # Просрочки и нарушения лимитов уважительных причин.
    overdue_by_week: dict[datetime, int] = {}
    for task in accepted_tasks:
        if task.kpi_status != "overdue" or task.is_discrepancy:
            continue
        has_events = True
        valid_excuse = task.has_excuse and await validate_and_apply_excuse(db, employee_id, task)
        if valid_excuse:
            continue
        points -= Decimal("1")
        if task.has_excuse:
            points -= Decimal("4")
        event_time = task.last_submitted_at or task.updated_at
        week_key = datetime.combine((event_time - timedelta(days=event_time.weekday())).date(), datetime.min.time())
        overdue_by_week[week_key] = overdue_by_week.get(week_key, 0) + 1
    points -= Decimal("5") * sum(1 for count in overdue_by_week.values() if count >= 3)

    # Опоздание, ранний уход и неотработанный штрафной день.
    attendance_res = await db.execute(
        select(AttendanceLog).where(
            AttendanceLog.employee_id == employee_id,
            AttendanceLog.date >= period_start,
            AttendanceLog.date <= period_end,
        )
    )
    for row in attendance_res.scalars().all():
        has_events = True
        if int(row.late_minutes or 0) > 0:
            points -= Decimal("1")
        if int(row.early_leave_minutes or 0) > 0:
            points -= Decimal("1")
        if row.is_penalty_day and not row.attendance_fulfilled:
            points -= Decimal("3")

    if not has_events:
        return None
    val = (points / Decimal("20.0")) * Decimal("100.0")
    return max(Decimal("0.0"), min(Decimal("100.0"), val)).quantize(Decimal("0.1"))


async def calculate_customer_satisfaction(
    db: AsyncSession,
    employee_id: uuid.UUID,
    period_start: datetime,
    period_end: datetime,
) -> Optional[Decimal]:
    """Взвешенная оценка заказчиков за период: sum(rating*weight) / sum(5*weight)."""
    result = await db.execute(
        select(ProjectReview.rating, ProjectContribution.weight)
        .join(ProjectContribution, ProjectContribution.project_id == ProjectReview.project_id)
        .where(
            ProjectContribution.user_id == employee_id,
            ProjectReview.submitted_at >= period_start,
            ProjectReview.submitted_at <= period_end,
        )
    )
    rows = result.all()
    if not rows:
        return None
    weighted_sum = sum((Decimal(str(rating)) * Decimal(str(weight)) for rating, weight in rows), Decimal("0"))
    max_sum = sum((Decimal("5") * Decimal(str(weight)) for _rating, weight in rows), Decimal("0"))
    if max_sum <= 0:
        return None
    value = weighted_sum / max_sum * Decimal("100")
    return max(Decimal("0"), min(Decimal("100"), value)).quantize(Decimal("1"))


# =====================================================================
# MANAGER-SPECIFIC KPIs (KPI1 - KPI4)
# =====================================================================

async def calculate_manager_kpi1_reaction_index(db: AsyncSession, manager_id: uuid.UUID, month_start: datetime, month_end: datetime) -> Optional[Decimal]:
    """
    Manager KPI 1: Взаимодействие с сотрудниками своего отдела.
    Индекс скорости реакции на падения KPI подчинённых.
    Шкала:
    - 0-1 день: 100%
    - 2 дня: 70%
    - 3 дня: 20%
    - 4+ дней: 0%
    - Непроведённые разборы > 5 дней: 0%
    """
    subordinates_res = await db.execute(select(User.id).where(User.manager_id == manager_id))
    sub_ids = [r[0] for r in subordinates_res.fetchall()]
    from app.models.gamification import KPIDrop
    drops = []
    if sub_ids:
        drops_res = await db.execute(
            select(KPIDrop).where(
                KPIDrop.employee_id.in_(sub_ids),
                KPIDrop.drop_date >= month_start,
                KPIDrop.drop_date <= month_end,
            )
        )
        drops = list(drops_res.scalars().all())

    sum_pct = Decimal("0.0")
    count = len(drops)

    for drop in drops:
        # Проверим, есть ли разбор
        review_res = await db.execute(
            select(PerformanceReview).where(PerformanceReview.drop_id == drop.id)
        )
        review = review_res.scalar_one_or_none()
        if review and review.reaction_days is not None:
            days = review.reaction_days
            if days <= 1:
                sum_pct += Decimal("100.0")
            elif days <= 2:
                sum_pct += Decimal("70.0")
            elif days <= 3:
                sum_pct += Decimal("20.0")
            else:
                sum_pct += Decimal("0.0")
        else:
            # Разбор не проведён
            # Проверим, прошло ли более 5 календарных дней с момента падения
            now = datetime.utcnow()
            if (now - drop.drop_date).days > 5:
                sum_pct += Decimal("0.0")
            else:
                # Если разбор ещё в процессе и 5 дней не прошло, не учитываем его в промежуточном расчете,
                # либо считаем 0. Давайте исключим из знаменателя пока не просрочено, чтобы не занижать "живой" KPI.
                count -= 1

    base = Decimal("100.0") if count == 0 else sum_pct / Decimal(str(count))
    overdue_cutoff = min(datetime.utcnow(), month_end) - timedelta(days=5)
    overdue_ideas_result = await db.execute(
        select(func.count()).where(
            EmployeeIdea.manager_id == manager_id,
            EmployeeIdea.created_at >= month_start,
            EmployeeIdea.created_at <= month_end,
            or_(
                and_(EmployeeIdea.reviewed_at.is_(None), EmployeeIdea.created_at <= overdue_cutoff),
                EmployeeIdea.reaction_days > 5,
            ),
        )
    )
    overdue_ideas = int(overdue_ideas_result.scalar() or 0)
    return max(Decimal("0"), base - Decimal("2") * overdue_ideas).quantize(Decimal("0.1"))


async def calculate_manager_kpi2_reaction_days(db: AsyncSession, manager_id: uuid.UUID, month_start: datetime, month_end: datetime) -> Optional[Decimal]:
    """
    Manager KPI 2: Среднее время реакции руководителя на падение KPI подчинённых (в рабочих днях).
    """
    # Получим подчиненных
    subordinates_res = await db.execute(select(User.id).where(User.manager_id == manager_id))
    sub_ids = [r[0] for r in subordinates_res.fetchall()]
    if not sub_ids:
        return None

    # Получим разборы
    reviews_res = await db.execute(
        select(PerformanceReview.reaction_days).where(
            PerformanceReview.manager_id == manager_id,
            PerformanceReview.review_date >= month_start,
            PerformanceReview.review_date <= month_end,
            PerformanceReview.reaction_days != None
        )
    )
    reaction_days_list = [Decimal(str(r[0])) for r in reviews_res.fetchall()]
    if not reaction_days_list:
        return None

    avg_days = sum(reaction_days_list) / Decimal(str(len(reaction_days_list)))
    return avg_days.quantize(Decimal("0.1"))


async def calculate_manager_kpi3_responsibility(db: AsyncSession, manager_id: uuid.UUID, month_start: datetime, month_end: datetime) -> Optional[Decimal]:
    """
    Manager KPI 3: Индекс ответственности руководителя.
    KPI3_% = max(0, min(100, (накопленные_баллы / 40) * 100%))
    """
    res = await db.execute(
        select(func.coalesce(func.sum(ManagerResponsibility.points), 0)).where(
            ManagerResponsibility.manager_id == manager_id,
            ManagerResponsibility.date >= month_start,
            ManagerResponsibility.date <= month_end
        )
    )
    points_sum = Decimal(str(res.scalar() or 0.0))
    val = (points_sum / Decimal("40.0")) * Decimal("100.0")
    return max(Decimal("0.0"), min(Decimal("100.0"), val)).quantize(Decimal("0.1"))


async def calculate_manager_kpi4_attentiveness(db: AsyncSession, manager_id: uuid.UUID, month_start: datetime, month_end: datetime) -> Optional[Decimal]:
    """
    Manager KPI 4: Индекс внимательности руководителя.
    KPI4_% = max(0, min(100, (total_points / 20) * 100%))
    """
    res = await db.execute(
        select(ManagerKPI4Points).where(
            ManagerKPI4Points.manager_id == manager_id,
            ManagerKPI4Points.month == month_start
        )
    )
    points_obj = res.scalar_one_or_none()
    points_sum = points_obj.total_points if points_obj else Decimal("0.0")
    val = (points_sum / Decimal("20.0")) * Decimal("100.0")
    return max(Decimal("0.0"), min(Decimal("100.0"), val)).quantize(Decimal("0.1"))


async def calculate_manager_kpi5_idea_reaction(
    db: AsyncSession,
    manager_id: uuid.UUID,
    month_start: datetime,
    month_end: datetime,
) -> Optional[Decimal]:
    """Средний процент скорости рассмотрения идей в пределах пяти рабочих дней."""
    result = await db.execute(
        select(EmployeeIdea).where(
            EmployeeIdea.manager_id == manager_id,
            EmployeeIdea.created_at >= month_start,
            EmployeeIdea.created_at <= month_end,
        )
    )
    ideas = list(result.scalars().all())
    if not ideas:
        return Decimal("100.0")
    counted = [
        Decimal(str(item.reaction_percentage))
        for item in ideas
        if item.reviewed_at is not None and item.is_counted_in_manager_kpi5 and item.reaction_percentage is not None
    ]
    if not counted:
        if any(item.reviewed_at is not None and (item.reaction_days or 0) > 5 for item in ideas):
            return None
        return Decimal("100.0")
    return (sum(counted, Decimal("0")) / Decimal(len(counted))).quantize(Decimal("0.1"))


async def calculate_manager_kpi6_overtime(db: AsyncSession, manager_id: uuid.UUID, month_start: datetime, month_end: datetime) -> Decimal:
    """Должностной KPI6: сумма процентов за сверхурочные управленческие действия, максимум 100%."""
    result = await db.execute(
        select(func.coalesce(func.sum(ManagerOvertimeCounter.percent_awarded), 0)).where(
            ManagerOvertimeCounter.manager_id == manager_id,
            ManagerOvertimeCounter.month >= month_start,
            ManagerOvertimeCounter.month <= month_end,
        )
    )
    actions_result = await db.execute(
        select(func.coalesce(func.sum(ManagerOvertimeAction.percent_awarded), 0)).where(
            ManagerOvertimeAction.manager_id == manager_id,
            ManagerOvertimeAction.month >= month_start,
            ManagerOvertimeAction.month <= month_end,
        )
    )
    total = Decimal(str(result.scalar() or 0)) + Decimal(str(actions_result.scalar() or 0))
    return max(Decimal("0.0"), min(Decimal("100.0"), total)).quantize(Decimal("0.1"))


async def calculate_manager_kpi7_department_control(db: AsyncSession, manager_id: uuid.UUID, month_start: datetime, month_end: datetime) -> Decimal:
    """Должностной KPI7: накопленные баллы контроля отдела, норма 40 баллов = 100%."""
    result = await db.execute(
        select(func.coalesce(func.sum(KPI7ManagerPoints.total_points), 0)).where(
            KPI7ManagerPoints.manager_id == manager_id,
            KPI7ManagerPoints.month >= month_start,
            KPI7ManagerPoints.month <= month_end,
        )
    )
    points = Decimal(str(result.scalar() or 0))
    value = points / Decimal("40.0") * Decimal("100.0")
    return max(Decimal("0.0"), min(Decimal("100.0"), value)).quantize(Decimal("0.1"))
