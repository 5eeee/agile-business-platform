# API задач и бэклога
import math
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import select, or_, exists, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.board_column import BoardColumn
from app.models.task import Task, TaskAssignee, TaskComment, TaskHistory, TaskAttachment
from app.models.backlog import BacklogItem
from app.models.iteration import Iteration
from app.models.project import ProjectMember
from app.models.user import User, UserRole, ADMIN_ROLES
from app.schemas.task import (
    TaskCreate, TaskUpdate, TaskOut, TaskDetailOut, TaskCommentCreate,
    TaskCommentOut, TaskHistoryOut,
    BacklogItemCreate, BacklogItemOut, BacklogToTask, TaskKPIReview,
)
from app.schemas.board_column import BoardColumnCreate, BoardColumnOut
from app.middleware.auth import get_current_user, require_projects_access
from app.dependencies import get_project_member, get_project_member_by_iteration
from app.config import TASK_STATUSES, TASK_PRIORITIES

router = APIRouter(prefix="/tasks", tags=["Задачи"], dependencies=[Depends(require_projects_access)])


RETURN_REASON_CONFIG = {
    "requirements": ("Не соответствует ТЗ", "medium", Decimal("2.0"), False),
    "logic": ("Логические ошибки", "critical", Decimal("3.0"), False),
    "broken_code": ("Код не работает", "critical", Decimal("3.0"), False),
    "report_error": ("Ошибка в отчёте", "medium", Decimal("2.0"), False),
    "incomplete": ("Неполнота данных", "small", Decimal("1.0"), False),
    "external": ("Внешняя причина (не вина сотрудника)", "regular", Decimal("0.0"), True),
}


def _ordered_assignee_ids_from_task(t: Task) -> list[uuid.UUID]:
    rows = list(getattr(t, "assignees", None) or [])
    if rows:
        return [a.user_id for a in sorted(rows, key=lambda x: (x.created_at, x.id))]
    if t.assignee_id:
        return [t.assignee_id]
    return []


async def _sync_task_assignees(session: AsyncSession, task_id: uuid.UUID, user_ids: list[uuid.UUID]) -> None:
    want = list(dict.fromkeys(user_ids))
    want_set = set(want)
    r = await session.execute(select(TaskAssignee).where(TaskAssignee.task_id == task_id))
    existing_rows = list(r.scalars().all())
    existing_by_uid: dict[uuid.UUID, TaskAssignee] = {row.user_id: row for row in existing_rows}
    for uid, row in list(existing_by_uid.items()):
        if uid not in want_set:
            await session.delete(row)
            existing_by_uid.pop(uid, None)
    for uid in want:
        if uid not in existing_by_uid:
            session.add(TaskAssignee(task_id=task_id, user_id=uid))


async def _visible_task_user_ids(db: AsyncSession, user: User) -> set[uuid.UUID] | None:
    """Возвращает контур людей, чьи задачи разрешено видеть.

    None означает полный контур владельца/заместителя. Руководитель видит свой
    отдел и прямых подчинённых, штатный сотрудник — только себя.
    """
    if user.role in {UserRole.OWNER, UserRole.DEPUTY_OWNER}:
        return None
    if user.role != UserRole.ADMIN:
        return {user.id}

    conditions = [User.id == user.id, User.manager_id == user.id]
    if user.department_id:
        conditions.append(User.department_id == user.department_id)
    result = await db.execute(select(User.id).where(or_(*conditions)))
    return {row[0] for row in result.all()} | {user.id}


async def _can_view_task(db: AsyncSession, user: User, task: Task) -> bool:
    visible_ids = await _visible_task_user_ids(db, user)
    if visible_ids is None:
        return True
    task_people = set(_ordered_assignee_ids_from_task(task))
    task_people.add(task.creator_id)
    return bool(task_people & visible_ids)


@router.get("/iteration/{iteration_id}/board-columns", response_model=list[BoardColumnOut])
async def list_iteration_board_columns(
    iteration_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    _member: ProjectMember = Depends(get_project_member_by_iteration),
):
    """Колонки доски итерации (дубликат маршрута под /tasks для совместимости с прокси/кэшем)."""
    result = await db.execute(
        select(BoardColumn)
        .where(BoardColumn.iteration_id == iteration_id)
        .order_by(BoardColumn.sort_order, BoardColumn.created_at)
    )
    return [BoardColumnOut.model_validate(c) for c in result.scalars().all()]


@router.post("/iteration/{iteration_id}/board-columns", response_model=BoardColumnOut, status_code=201)
async def create_iteration_board_column(
    iteration_id: uuid.UUID,
    data: BoardColumnCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    _member: ProjectMember = Depends(get_project_member_by_iteration),
):
    col = BoardColumn(iteration_id=iteration_id, title=data.title.strip(), sort_order=data.sort_order)
    db.add(col)
    await db.commit()
    await db.refresh(col)
    from app.websocket import manager as ws_mgr
    await ws_mgr.broadcast_to_iteration(
        str(iteration_id),
        {"type": "resource_changed", "resource": "board_columns", "iteration_id": str(iteration_id)},
    )
    return BoardColumnOut.model_validate(col)


def _serialize_task(t: Task, user_names: dict[uuid.UUID, str]) -> TaskOut:
    ids = _ordered_assignee_ids_from_task(t)
    names = [user_names.get(i) or "" for i in ids]
    primary_id = ids[0] if ids else None
    primary_name = (names[0] or None) if names else None
    return TaskOut(
        id=t.id,
        iteration_id=t.iteration_id,
        title=t.title,
        description=t.description,
        status=t.status,
        priority=t.priority,
        assignee_id=primary_id,
        assignee_name=primary_name,
        assignee_ids=ids,
        assignee_names=names,
        creator_id=t.creator_id,
        creator_name=user_names.get(t.creator_id),
        start_date=t.start_date,
        deadline=t.deadline,
        parent_id=t.parent_id,
        board_column_id=t.board_column_id,
        is_completed=bool(getattr(t, "is_completed", False)),
        first_submitted_at=t.first_submitted_at,
        last_submitted_at=t.last_submitted_at,
        kpi_status=t.kpi_status,
        has_excuse=bool(t.has_excuse),
        excuse_reason=t.excuse_reason,
        is_discrepancy=bool(t.is_discrepancy),
        systematic_defect=bool(t.systematic_defect),
        return_count=int(t.return_count or 0),
        is_bonus_eligible=bool(t.is_bonus_eligible),
        created_at=t.created_at,
        updated_at=t.updated_at,
    )


@router.get("/iteration/{iteration_id}", response_model=list[TaskOut])
async def list_tasks(
    iteration_id: uuid.UUID,
    status: str | None = None,
    priority: str | None = None,
    assignee_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    _member: ProjectMember = Depends(get_project_member_by_iteration),
):
    """Список задач итерации с фильтрацией"""
    query = select(Task).options(selectinload(Task.assignees)).where(Task.iteration_id == iteration_id)
    visible_ids = await _visible_task_user_ids(db, user)
    if visible_ids is not None:
        in_visible_assignees = exists().where(
            TaskAssignee.task_id == Task.id,
            TaskAssignee.user_id.in_(visible_ids),
        )
        query = query.where(or_(
            Task.creator_id.in_(visible_ids),
            Task.assignee_id.in_(visible_ids),
            in_visible_assignees,
        ))
    if status:
        query = query.where(Task.status == status)
    if priority:
        query = query.where(Task.priority == priority)
    if assignee_id:
        in_junction = exists().where(
            TaskAssignee.task_id == Task.id,
            TaskAssignee.user_id == assignee_id,
        )
        query = query.where(or_(Task.assignee_id == assignee_id, in_junction))
    query = query.order_by(Task.created_at.desc())
    
    result = await db.execute(query)
    tasks = result.scalars().all()
    
    # Batch-fetch user names to avoid N+1 queries
    user_ids: set[uuid.UUID] = set()
    for t in tasks:
        for a in getattr(t, "assignees", None) or []:
            user_ids.add(a.user_id)
        if t.assignee_id:
            user_ids.add(t.assignee_id)
        user_ids.add(t.creator_id)
    
    user_names = {}
    if user_ids:
        users_result = await db.execute(select(User.id, User.name).where(User.id.in_(user_ids)))
        user_names = {row.id: row.name for row in users_result.all()}
    
    return [_serialize_task(t, user_names) for t in tasks]


@router.get("/{task_id}")
async def get_task(task_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Получение задачи с комментариями и историей"""
    result = await db.execute(
        select(Task)
        .options(
            selectinload(Task.comments),
            selectinload(Task.history),
            selectinload(Task.attachments),
            selectinload(Task.assignees),
        )
        .where(Task.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    
    if not await _can_view_task(db, user, task):
        raise HTTPException(status_code=404, detail="Задача не найдена")

    # Verify project membership via iteration
    if user.role not in ADMIN_ROLES:
        iter_result = await db.execute(select(Iteration).where(Iteration.id == task.iteration_id))
        iteration = iter_result.scalar_one_or_none()
        if iteration:
            member_result = await db.execute(
                select(ProjectMember).where(ProjectMember.project_id == iteration.project_id, ProjectMember.user_id == user.id)
            )
            if not member_result.scalar_one_or_none():
                raise HTTPException(status_code=403, detail="Вы не являетесь участником этого проекта")
    
    # Batch-fetch all user names needed
    user_ids = {task.creator_id}
    for a in getattr(task, "assignees", None) or []:
        user_ids.add(a.user_id)
    if task.assignee_id:
        user_ids.add(task.assignee_id)
    for cm in task.comments:
        user_ids.add(cm.user_id)
    for h in task.history:
        user_ids.add(h.user_id)
    
    users_result = await db.execute(select(User.id, User.name).where(User.id.in_(user_ids)))
    user_names = {row.id: row.name for row in users_result.all()}
    
    comments = [
        TaskCommentOut(
            id=cm.id, task_id=cm.task_id, user_id=cm.user_id,
            user_name=user_names.get(cm.user_id), content=cm.content, created_at=cm.created_at,
        )
        for cm in task.comments
    ]
    
    history = [
        TaskHistoryOut(
            id=h.id, task_id=h.task_id, user_id=h.user_id,
            user_name=user_names.get(h.user_id), field=h.field,
            old_value=h.old_value, new_value=h.new_value, created_at=h.created_at,
        )
        for h in task.history
    ]
    
    attachments = [
        {"id": str(a.id), "filename": a.filename, "file_url": a.file_url, "file_size": a.file_size, "mime_type": a.mime_type}
        for a in task.attachments
    ]
    
    base = _serialize_task(task, user_names)
    return TaskDetailOut(
        **base.model_dump(),
        comments=comments,
        history=history,
        attachments=attachments,
    )


@router.post("", response_model=TaskOut, status_code=201)
async def create_task(data: TaskCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    # Verify project membership via iteration
    iter_result = await db.execute(select(Iteration).where(Iteration.id == data.iteration_id))
    iteration = iter_result.scalar_one_or_none()
    if not iteration:
        raise HTTPException(status_code=404, detail="Итерация не найдена")
    if user.role not in ADMIN_ROLES:
        member_result = await db.execute(
            select(ProjectMember).where(ProjectMember.project_id == iteration.project_id, ProjectMember.user_id == user.id)
        )
        if not member_result.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Вы не являетесь участником этого проекта")
    
    if data.priority and data.priority not in TASK_PRIORITIES:
        raise HTTPException(status_code=400, detail=f"Приоритет должен быть: {', '.join(TASK_PRIORITIES)}")
    if data.start_date and data.deadline and data.start_date > data.deadline:
        raise HTTPException(status_code=400, detail="start_date не может быть позже deadline")

    parent_id = data.parent_id
    board_column_id = data.board_column_id
    if parent_id:
        pr = await db.execute(select(Task).where(Task.id == parent_id))
        parent = pr.scalar_one_or_none()
        if not parent or parent.iteration_id != data.iteration_id:
            raise HTTPException(status_code=400, detail="Некорректная родительская задача")
        board_column_id = None
    else:
        if board_column_id:
            cr = await db.execute(select(BoardColumn).where(BoardColumn.id == board_column_id))
            col = cr.scalar_one_or_none()
            if not col or col.iteration_id != data.iteration_id:
                raise HTTPException(status_code=400, detail="Некорректная колонка доски")
        else:
            # Backward-compatible fallback: use first column or create default one.
            first_col_result = await db.execute(
                select(BoardColumn)
                .where(BoardColumn.iteration_id == data.iteration_id)
                .order_by(BoardColumn.sort_order, BoardColumn.created_at)
            )
            first_col = first_col_result.scalars().first()
            if not first_col:
                first_col = BoardColumn(iteration_id=data.iteration_id, title="Колонка 1", sort_order=0)
                db.add(first_col)
                await db.flush()
            board_column_id = first_col.id

    initial_assignee_ids: list[uuid.UUID] = []
    if data.assignee_ids:
        initial_assignee_ids = list(dict.fromkeys(data.assignee_ids))
    elif data.assignee_id:
        initial_assignee_ids = [data.assignee_id]

    visible_ids = await _visible_task_user_ids(db, user)
    if visible_ids is not None and any(uid not in visible_ids for uid in initial_assignee_ids):
        raise HTTPException(status_code=403, detail="Можно назначать задачи только в пределах своего отдела")

    task = Task(
        iteration_id=data.iteration_id,
        title=data.title,
        description=data.description,
        assignee_id=initial_assignee_ids[0] if initial_assignee_ids else None,
        creator_id=user.id,
        start_date=data.start_date,
        deadline=data.deadline,
        priority=data.priority,
        parent_id=parent_id,
        board_column_id=board_column_id,
        is_completed=False,
    )
    db.add(task)
    await db.flush()
    for uid in initial_assignee_ids:
        db.add(TaskAssignee(task_id=task.id, user_id=uid))
    await db.commit()

    result = await db.execute(select(Task).options(selectinload(Task.assignees)).where(Task.id == task.id))
    task = result.scalar_one()

    from app.models.notification import Notification
    from app.services.telegram import notify_task_assigned
    from app.websocket import manager as ws_mgr

    for assign_uid in initial_assignee_ids:
        if assign_uid != user.id:
            notif = Notification(
                user_id=assign_uid,
                title="Новая задача",
                message=f"{user.name} назначил вам задачу: {task.title}",
                type="task",
            )
            db.add(notif)
            await db.commit()
            await ws_mgr.send_to_user(str(assign_uid), {
                "type": "notification",
                "title": notif.title,
                "message": notif.message,
            })
            assignee_row = await db.execute(select(User).where(User.id == assign_uid))
            assignee = assignee_row.scalar_one_or_none()
            if assignee and assignee.telegram_id and assignee.notify_tasks:
                iter_result = await db.execute(select(Iteration).where(Iteration.id == task.iteration_id))
                it = iter_result.scalar_one_or_none()
                await notify_task_assigned(assignee.telegram_id, task.title, it.name if it else "")

    uid_set = {user.id, *initial_assignee_ids}
    users_result = await db.execute(select(User.id, User.name).where(User.id.in_(uid_set)))
    unames = {row.id: row.name for row in users_result.all()}
    created_out = _serialize_task(task, unames)
    await ws_mgr.broadcast_to_iteration(
        str(task.iteration_id),
        {"type": "task_created", "task": created_out.model_dump(mode="json")},
    )
    return created_out


async def _can_review_task_kpi(db: AsyncSession, task: Task, user: User) -> bool:
    if user.role in ADMIN_ROLES or task.creator_id == user.id:
        return True
    iteration = await db.get(Iteration, task.iteration_id)
    if not iteration:
        return False
    member = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == iteration.project_id,
            ProjectMember.user_id == user.id,
            ProjectMember.is_admin == True,
        )
    )
    return member.scalar_one_or_none() is not None


async def _create_task_notification(
    db: AsyncSession,
    recipient_id: uuid.UUID | None,
    title: str,
    message: str,
    notification_type: str = "task",
    link: str | None = None,
) -> None:
    if not recipient_id:
        return
    from app.models.notification import Notification
    from app.websocket import manager as ws_manager

    db.add(Notification(user_id=recipient_id, title=title, message=message, type=notification_type, link=link))
    await ws_manager.send_to_user(
        str(recipient_id),
        {"type": "notification", "title": title, "message": message, "notification_type": notification_type, "link": link},
    )


async def _apply_manager_kpi7_overdue_penalty(db: AsyncSession, task: Task, previous_status: str | None) -> None:
    """Однократно начислить руководителю −2 за новую просрочку подчинённого."""
    if previous_status == "overdue" or task.kpi_status != "overdue" or task.has_excuse or task.is_discrepancy:
        return
    assignee = await db.get(User, task.assignee_id)
    if not assignee or not assignee.manager_id:
        return
    from app.models.gamification import KPI7ManagerPoints
    month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        select(KPI7ManagerPoints).where(
            KPI7ManagerPoints.manager_id == assignee.manager_id,
            KPI7ManagerPoints.month == month,
        )
    )
    counter = result.scalar_one_or_none()
    if counter:
        counter.total_points = Decimal(str(counter.total_points or 0)) - Decimal("2")
        counter.updated_at = datetime.utcnow()
    else:
        db.add(KPI7ManagerPoints(manager_id=assignee.manager_id, month=month, total_points=Decimal("-2")))


@router.post("/{task_id}/submit-for-review", response_model=TaskOut)
async def submit_task_for_review(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Record every submission attempt and send the task to KPI review."""
    result = await db.execute(
        select(Task).options(selectinload(Task.assignees)).where(Task.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")

    if not await _can_view_task(db, user, task):
        # Не раскрываем существование чужой приватной задачи.
        raise HTTPException(status_code=404, detail="Задача не найдена")

    assignee_ids = set(_ordered_assignee_ids_from_task(task))
    if user.id not in assignee_ids and user.role not in ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Отправить задачу может только исполнитель")

    now = datetime.utcnow()
    previous_status = task.kpi_status
    if task.first_submitted_at is None:
        task.first_submitted_at = now
    task.last_submitted_at = now
    task.kpi_status = "pending_review"
    task.is_completed = False
    task.updated_at = now
    db.add(
        TaskHistory(
            task_id=task.id,
            user_id=user.id,
            field="kpi_submission",
            old_value=previous_status,
            new_value=now.isoformat(),
        )
    )

    from app.models.gamification import TaskReturn
    pending_return = await db.execute(
        select(TaskReturn)
        .where(TaskReturn.task_id == task.id, TaskReturn.resend_time.is_(None))
        .order_by(TaskReturn.return_time.desc())
        .limit(1)
    )
    returned = pending_return.scalar_one_or_none()
    if returned:
        from app.services.kpi_calculator import calculate_working_hours
        returned.resend_time = now
        returned.effective_hours = calculate_working_hours(returned.return_time, now)
        norm_hours = {
            "critical": Decimal("4"),
            "medium": Decimal("6"),
            "small": Decimal("8"),
        }.get(returned.error_category, Decimal("8"))
        subordinates = await db.scalar(select(func.count(User.id)).where(User.manager_id == task.assignee_id)) or 0
        if assignee := await db.get(User, task.assignee_id):
            if assignee.role in ADMIN_ROLES or subordinates > 0:
                norm_hours = max(Decimal("1"), norm_hours - Decimal("1"))
        if not returned.is_external and returned.effective_hours > norm_hours:
            overtime_blocks = math.ceil(float((returned.effective_hours - norm_hours) / norm_hours))
            returned.extra_penalty = Decimal(str(overtime_blocks))
            returned.total_weight = returned.base_weight + returned.extra_penalty

        if not returned.is_external and returned.effective_hours <= norm_hours:
            from app.models.gamification import KPI9Bonus
            base_bonus = max(Decimal("0"), (norm_hours - returned.effective_hours) / norm_hours * Decimal("5"))
            quick_bonus = base_bonus if returned.is_iterative else base_bonus / Decimal(str(max(1, returned.return_count)))
            if quick_bonus > 0:
                db.add(KPI9Bonus(
                    employee_id=task.assignee_id,
                    month=now.replace(day=1, hour=0, minute=0, second=0, microsecond=0),
                    event_type="quick_rework",
                    percent=quick_bonus.quantize(Decimal("0.01")),
                    source_id=returned.id,
                ))

    await _create_task_notification(
        db,
        task.creator_id,
        "Задача отправлена на проверку",
        f"{user.name} отправил задачу «{task.title}» на KPI-проверку.",
    )
    await db.commit()

    from app.api.gamification import kpi_cache
    kpi_cache.clear()
    names = {user.id: user.name}
    return _serialize_task(task, names)


@router.post("/{task_id}/kpi-review", response_model=TaskOut)
async def review_task_kpi(
    task_id: uuid.UUID,
    data: TaskKPIReview,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Accept, mark overdue, or return a submitted task according to KPI rules."""
    result = await db.execute(
        select(Task).options(selectinload(Task.assignees)).where(Task.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    if not await _can_review_task_kpi(db, task, user):
        raise HTTPException(status_code=403, detail="Недостаточно прав для KPI-проверки")
    if task.last_submitted_at is None:
        raise HTTPException(status_code=400, detail="Сначала исполнитель должен отправить задачу на проверку")
    if not task.assignee_id:
        raise HTTPException(status_code=400, detail="У задачи не указан исполнитель")

    now = datetime.utcnow()
    assignee = await db.get(User, task.assignee_id)
    previous_status = task.kpi_status

    if data.decision == "rework":
        if not data.return_reason or data.return_reason not in RETURN_REASON_CONFIG:
            raise HTTPException(status_code=422, detail="Выберите причину возврата")
        if not data.comment or not data.comment.strip():
            raise HTTPException(status_code=422, detail="Комментарий руководителя обязателен")

        from app.models.gamification import TaskReturn
        _label, category, base_weight, is_external = RETURN_REASON_CONFIG[data.return_reason]
        same_reason_count = await db.scalar(
            select(func.count(TaskReturn.id)).where(
                TaskReturn.task_id == task.id,
                TaskReturn.reason_code == data.return_reason,
                TaskReturn.is_external == False,
            )
        ) or 0
        counted_return_number = int(task.return_count or 0) + (0 if is_external else 1)
        extra_penalty = Decimal("0.0")
        db.add(
            TaskReturn(
                task_id=task.id,
                employee_id=task.assignee_id,
                error_category=category,
                reason_code=data.return_reason,
                base_weight=base_weight,
                extra_penalty=extra_penalty,
                total_weight=base_weight + extra_penalty,
                return_count=max(1, counted_return_number),
                is_iterative=same_reason_count >= 1 and not is_external,
                is_external=is_external,
                comment=data.comment.strip(),
                created_by=user.id,
            )
        )
        task.kpi_status = "rework"
        task.is_completed = False
        task.has_excuse = False
        task.excuse_reason = None
        task.is_discrepancy = False
        task.is_bonus_eligible = False
        if not is_external:
            task.return_count = counted_return_number
            task.systematic_defect = same_reason_count >= 1
        await _create_task_notification(
            db,
            task.assignee_id,
            "Задача возвращена на доработку",
            f"«{task.title}»: {_label}. {data.comment.strip()}",
        )
    else:
        objective_status = "in_time" if task.deadline and task.last_submitted_at <= task.deadline else "overdue"
        task.is_discrepancy = data.decision != objective_status
        task.kpi_status = data.decision
        task.is_completed = True
        task.has_excuse = False
        task.excuse_reason = None

        if data.decision == "overdue" and data.has_excuse:
            if not data.excuse_reason or not data.excuse_reason.strip():
                raise HTTPException(status_code=422, detail="Укажите уважительную причину")
            task.has_excuse = True
            task.excuse_reason = data.excuse_reason.strip()
            from app.services.kpi_calculator import validate_and_apply_excuse
            if not await validate_and_apply_excuse(db, task.assignee_id, task):
                task.has_excuse = False
                task.excuse_reason = None

        await _apply_manager_kpi7_overdue_penalty(db, task, previous_status)

        task.is_bonus_eligible = bool(
            data.decision == "in_time"
            and not task.is_discrepancy
            and task.first_submitted_at
            and task.deadline
            and task.first_submitted_at <= task.deadline
            and int(task.return_count or 0) == 0
        )

        if task.is_bonus_eligible:
            from app.models.gamification import KPI9Bonus
            duplicate_bonus = await db.scalar(
                select(func.count(KPI9Bonus.id)).where(
                    KPI9Bonus.employee_id == task.assignee_id,
                    KPI9Bonus.event_type == "quality_first_submission",
                    KPI9Bonus.source_id == task.id,
                )
            ) or 0
            if duplicate_bonus == 0:
                db.add(
                    KPI9Bonus(
                        employee_id=task.assignee_id,
                        month=now.replace(day=1, hour=0, minute=0, second=0, microsecond=0),
                        event_type="quality_first_submission",
                        percent=Decimal("2.0"),
                        source_id=task.id,
                    )
                )

        if task.is_discrepancy:
            await _create_task_notification(
                db,
                user.id,
                "Расхождение KPI по задаче",
                f"Ваша отметка по задаче «{task.title}» не совпадает с датой отправки и дедлайном. Исправьте решение.",
                "critical_divergence",
            )
            owners = await db.execute(select(User).where(User.role.in_([UserRole.OWNER, UserRole.DEPUTY_OWNER])))
            for owner in owners.scalars().all():
                await _create_task_notification(
                    db,
                    owner.id,
                    "Расхождение KPI по задаче",
                    f"Отметка руководителя по задаче «{task.title}» не совпадает с датой отправки и дедлайном.",
                    "critical_divergence",
                )
        await _create_task_notification(
            db,
            task.assignee_id,
            "Результат KPI-проверки задачи",
            f"«{task.title}»: {('сдано в срок' if data.decision == 'in_time' else 'просрочено')}.",
        )

    task.updated_at = now
    db.add(
        TaskHistory(
            task_id=task.id,
            user_id=user.id,
            field="kpi_status",
            old_value=previous_status,
            new_value=task.kpi_status,
        )
    )
    await db.commit()

    from app.api.gamification import kpi_cache
    from app.websocket import manager as ws_manager
    kpi_cache.clear()
    names = {task.assignee_id: assignee.name if assignee else "", task.creator_id: user.name}
    serialized = _serialize_task(task, names)
    await ws_manager.broadcast_to_iteration(
        str(task.iteration_id),
        {"type": "task_update", "task_id": str(task.id), "task": serialized.model_dump(mode="json")},
    )
    return serialized


@router.put("/{task_id}", response_model=TaskOut)
async def update_task(task_id: uuid.UUID, data: TaskUpdate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(
        select(Task).options(selectinload(Task.assignees)).where(Task.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")

    if not await _can_view_task(db, user, task):
        raise HTTPException(status_code=404, detail="Задача не найдена")
    
    # Verify project membership via iteration
    if user.role not in ADMIN_ROLES:
        iter_result = await db.execute(select(Iteration).where(Iteration.id == task.iteration_id))
        iteration = iter_result.scalar_one_or_none()
        if iteration:
            member_result = await db.execute(
                select(ProjectMember).where(ProjectMember.project_id == iteration.project_id, ProjectMember.user_id == user.id)
            )
            if not member_result.scalar_one_or_none():
                raise HTTPException(status_code=403, detail="Вы не являетесь участником этого проекта")
    
    if data.status and data.status not in TASK_STATUSES:
        raise HTTPException(status_code=400, detail=f"Статус должен быть: {', '.join(TASK_STATUSES)}")
    if data.priority and data.priority not in TASK_PRIORITIES:
        raise HTTPException(status_code=400, detail=f"Приоритет должен быть: {', '.join(TASK_PRIORITIES)}")
    if data.start_date and data.deadline and data.start_date > data.deadline:
        raise HTTPException(status_code=400, detail="start_date не может быть позже deadline")

    if data.board_column_id is not None and task.parent_id is not None:
        raise HTTPException(status_code=400, detail="Нельзя переносить подзадачу в колонку")
    if data.board_column_id is not None:
        cr = await db.execute(select(BoardColumn).where(BoardColumn.id == data.board_column_id))
        col = cr.scalar_one_or_none()
        if not col or col.iteration_id != task.iteration_id:
            raise HTTPException(status_code=400, detail="Некорректная колонка доски")

    old_assignee_ids = _ordered_assignee_ids_from_task(task)
    was_completed = bool(task.is_completed)

    full_patch = data.model_dump(exclude_unset=True)
    assignee_ids_explicit = full_patch.pop("assignee_ids", None)
    if assignee_ids_explicit is not None:
        full_patch.pop("assignee_id", None)
    assignee_id_touched = "assignee_id" in full_patch
    assignee_id_value = full_patch.pop("assignee_id") if assignee_id_touched else None

    for key, value in full_patch.items():
        old_value = str(getattr(task, key)) if getattr(task, key) is not None else None
        new_value = str(value) if value is not None else None
        
        if old_value != new_value:
            history = TaskHistory(
                task_id=task.id, user_id=user.id, field=key,
                old_value=old_value, new_value=new_value,
            )
            db.add(history)
        
        setattr(task, key, value)

    new_assignee_ids_to_sync: list[uuid.UUID] | None = None
    if assignee_ids_explicit is not None:
        new_assignee_ids_to_sync = list(dict.fromkeys(assignee_ids_explicit))
        task.assignee_id = new_assignee_ids_to_sync[0] if new_assignee_ids_to_sync else None
    elif assignee_id_touched:
        new_assignee_ids_to_sync = [u for u in [assignee_id_value] if u is not None]
        task.assignee_id = assignee_id_value

    if new_assignee_ids_to_sync is not None:
        visible_ids = await _visible_task_user_ids(db, user)
        if visible_ids is not None and any(uid not in visible_ids for uid in new_assignee_ids_to_sync):
            raise HTTPException(status_code=403, detail="Можно назначать задачи только в пределах своего отдела")
        await _sync_task_assignees(db, task.id, new_assignee_ids_to_sync)
        if sorted(old_assignee_ids) != sorted(new_assignee_ids_to_sync):
            hist_uids = set(old_assignee_ids) | set(new_assignee_ids_to_sync)
            if hist_uids:
                hn = await db.execute(select(User.id, User.name).where(User.id.in_(hist_uids)))
                name_map = {row.id: row.name for row in hn.all()}
            else:
                name_map = {}

            def _lbl(ids: list[uuid.UUID]) -> str | None:
                if not ids:
                    return None
                return ", ".join(name_map.get(i) or str(i) for i in ids)

            db.add(
                TaskHistory(
                    task_id=task.id,
                    user_id=user.id,
                    field="assignee",
                    old_value=_lbl(old_assignee_ids),
                    new_value=_lbl(new_assignee_ids_to_sync),
                )
            )
    
    # Coin reward for task completion with anti-cheat protections.
    if full_patch.get("is_completed") is True and not was_completed and task.assignee_id:
        from app.models.gamification import CoinTransaction, CoinTransactionType
        # Strict dedupe: one reward per task ever.
        dup = await db.execute(
            select(CoinTransaction).where(
                CoinTransaction.reference_id == task.id,
                CoinTransaction.tx_type == CoinTransactionType.TASK_APPROVED,
            )
        )
        if not dup.scalar_one_or_none():
            now = datetime.utcnow()
            hour_ago = now - timedelta(hours=1)
            day_start = datetime(now.year, now.month, now.day)

            # Heuristic 1: too many completion toggles by same user in last hour.
            toggles = await db.execute(
                select(TaskHistory).where(
                    TaskHistory.user_id == user.id,
                    TaskHistory.field == "is_completed",
                    TaskHistory.created_at >= hour_ago,
                )
            )
            if len(toggles.scalars().all()) <= 10:
                # Heuristic 2: daily reward cap for task rewards.
                day_reward_sum = await db.execute(
                    select(CoinTransaction).where(
                        CoinTransaction.user_id == task.assignee_id,
                        CoinTransaction.tx_type == CoinTransactionType.TASK_APPROVED,
                        CoinTransaction.created_at >= day_start,
                    )
                )
                day_reward_total = Decimal("0")
                for row in day_reward_sum.scalars().all():
                    day_reward_total += Decimal(str(row.amount))

                if day_reward_total < Decimal("25"):
                    is_overdue = bool(task.deadline and task.deadline < now)
                    coins = Decimal("0.50") if is_overdue else Decimal("2.00")
                    tx = CoinTransaction(
                        user_id=task.assignee_id,
                        amount=coins,
                        tx_type=CoinTransactionType.TASK_APPROVED,
                        reason=f"Завершение задачи: {task.title}" + (" (просрочена)" if is_overdue else ""),
                        reference_id=task.id,
                    )
                    db.add(tx)

    task.updated_at = datetime.utcnow()
    await db.commit()

    result_reload = await db.execute(
        select(Task).options(selectinload(Task.assignees)).where(Task.id == task.id)
    )
    task = result_reload.scalar_one()

    from app.websocket import manager as ws_manager

    uid_batch = {task.creator_id, *_ordered_assignee_ids_from_task(task), user.id}
    users_res = await db.execute(select(User.id, User.name).where(User.id.in_(uid_batch)))
    user_names = {row.id: row.name for row in users_res.all()}
    user_names[user.id] = user.name
    serialized = _serialize_task(task, user_names)
    await ws_manager.broadcast_to_iteration(
        str(task.iteration_id),
        {
            "type": "task_update",
            "task_id": str(task.id),
            "task": serialized.model_dump(mode="json"),
        },
    )

    if new_assignee_ids_to_sync is not None:
        from app.models.notification import Notification
        from app.services.telegram import notify_task_assigned
        old_set = set(old_assignee_ids)
        for uid in new_assignee_ids_to_sync:
            if uid in old_set or uid == user.id:
                continue
            notif = Notification(
                user_id=uid,
                title="Назначена задача",
                message=f"{user.name} назначил вам задачу: {task.title}",
                type="task",
            )
            db.add(notif)
            await db.commit()
            await ws_manager.send_to_user(str(uid), {
                "type": "notification", "title": notif.title, "message": notif.message,
            })
            assignee_result = await db.execute(select(User).where(User.id == uid))
            assignee = assignee_result.scalar_one_or_none()
            if assignee and assignee.telegram_id and assignee.notify_tasks:
                iter_result = await db.execute(select(Iteration).where(Iteration.id == task.iteration_id))
                it = iter_result.scalar_one_or_none()
                await notify_task_assigned(assignee.telegram_id, task.title, it.name if it else "")

    return serialized


@router.delete("/{task_id}")
async def delete_task(task_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Task).options(selectinload(Task.assignees)).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")

    if not await _can_view_task(db, user, task):
        raise HTTPException(status_code=404, detail="Задача не найдена")
    
    # Only task creator, project member or admin can delete
    if user.role not in ADMIN_ROLES and task.creator_id != user.id:
        iter_result = await db.execute(select(Iteration).where(Iteration.id == task.iteration_id))
        iteration = iter_result.scalar_one_or_none()
        if iteration:
            member_result = await db.execute(
                select(ProjectMember).where(
                    ProjectMember.project_id == iteration.project_id,
                    ProjectMember.user_id == user.id,
                    ProjectMember.is_admin == True
                )
            )
            if not member_result.scalar_one_or_none():
                raise HTTPException(status_code=403, detail="Нет прав на удаление задачи")
    
    iteration_id_str = str(task.iteration_id)
    task_id_str = str(task.id)
    await db.delete(task)
    await db.commit()
    from app.websocket import manager as ws_manager
    await ws_manager.broadcast_to_iteration(
        iteration_id_str,
        {"type": "task_deleted", "task_id": task_id_str},
    )
    return {"message": "Задача удалена"}


@router.post("/{task_id}/comments", response_model=TaskCommentOut, status_code=201)
async def add_comment(task_id: uuid.UUID, data: TaskCommentCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    # Verify task exists and user has access
    task_result = await db.execute(select(Task).options(selectinload(Task.assignees)).where(Task.id == task_id))
    task = task_result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    if not await _can_view_task(db, user, task):
        raise HTTPException(status_code=404, detail="Задача не найдена")
    if user.role not in ADMIN_ROLES:
        iter_result = await db.execute(select(Iteration).where(Iteration.id == task.iteration_id))
        iteration = iter_result.scalar_one_or_none()
        if iteration:
            member_result = await db.execute(
                select(ProjectMember).where(ProjectMember.project_id == iteration.project_id, ProjectMember.user_id == user.id)
            )
            if not member_result.scalar_one_or_none():
                raise HTTPException(status_code=403, detail="Вы не являетесь участником этого проекта")

    comment = TaskComment(task_id=task_id, user_id=user.id, content=data.content)
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    
    return TaskCommentOut(
        id=comment.id, task_id=comment.task_id, user_id=comment.user_id,
        user_name=user.name, content=comment.content, created_at=comment.created_at,
    )


@router.post("/{task_id}/attachments", status_code=201)
async def upload_task_attachment(
    task_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Загрузка файла-вложения к задаче"""
    from app.services.s3 import upload_file_to_s3
    task_result = await db.execute(select(Task).options(selectinload(Task.assignees)).where(Task.id == task_id))
    task = task_result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    if not await _can_view_task(db, user, task):
        raise HTTPException(status_code=404, detail="Задача не найдена")
    if user.role not in ADMIN_ROLES:
        iter_result = await db.execute(select(Iteration).where(Iteration.id == task.iteration_id))
        iteration = iter_result.scalar_one_or_none()
        if iteration:
            member_result = await db.execute(
                select(ProjectMember).where(ProjectMember.project_id == iteration.project_id, ProjectMember.user_id == user.id)
            )
            if not member_result.scalar_one_or_none():
                raise HTTPException(status_code=403, detail="Вы не являетесь участником этого проекта")
    url = await upload_file_to_s3(file, f"tasks/{task_id}")
    attachment = TaskAttachment(
        task_id=task_id, user_id=user.id,
        filename=file.filename or "file",
        file_url=url,
        file_size=file.size,
        mime_type=file.content_type,
    )
    db.add(attachment)
    await db.commit()
    await db.refresh(attachment)
    return {"id": str(attachment.id), "filename": attachment.filename, "file_url": attachment.file_url}


# --- Бэклог ---

backlog_router = APIRouter(prefix="/backlog", tags=["Бэклог"], dependencies=[Depends(require_projects_access)])


@backlog_router.get("/{project_id}", response_model=list[BacklogItemOut])
async def list_backlog(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    _member: ProjectMember = Depends(get_project_member),
):
    result = await db.execute(
        select(BacklogItem).where(BacklogItem.project_id == project_id).order_by(BacklogItem.created_at.desc())
    )
    items = result.scalars().all()
    
    creator_ids = {item.creator_id for item in items}
    if creator_ids:
        users_result = await db.execute(select(User.id, User.name).where(User.id.in_(creator_ids)))
        user_names = {row.id: row.name for row in users_result.all()}
    else:
        user_names = {}
    
    return [
        BacklogItemOut(
            id=item.id, project_id=item.project_id, title=item.title,
            description=item.description, creator_id=item.creator_id,
            creator_name=user_names.get(item.creator_id), created_at=item.created_at,
        )
        for item in items
    ]


@backlog_router.post("", response_model=BacklogItemOut, status_code=201)
async def create_backlog_item(data: BacklogItemCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    # Verify project membership
    if user.role not in ADMIN_ROLES:
        member_result = await db.execute(
            select(ProjectMember).where(ProjectMember.project_id == data.project_id, ProjectMember.user_id == user.id)
        )
        if not member_result.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Вы не являетесь участником этого проекта")
    
    item = BacklogItem(project_id=data.project_id, title=data.title, description=data.description, creator_id=user.id)
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return BacklogItemOut(
        id=item.id, project_id=item.project_id, title=item.title,
        description=item.description, creator_id=item.creator_id,
        creator_name=user.name, created_at=item.created_at,
    )


@backlog_router.delete("/{item_id}")
async def delete_backlog_item(item_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(BacklogItem).where(BacklogItem.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Элемент бэклога не найден")
    # Verify: creator, project admin, or site admin
    if user.role not in ADMIN_ROLES and item.creator_id != user.id:
        member_result = await db.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == item.project_id, ProjectMember.user_id == user.id, ProjectMember.is_admin == True
            )
        )
        if not member_result.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Нет прав на удаление")
    await db.delete(item)
    await db.commit()
    return {"message": "Элемент удалён"}


@backlog_router.post("/{item_id}/to-task", response_model=TaskOut)
async def backlog_to_task(item_id: uuid.UUID, data: BacklogToTask, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Преобразование идеи из бэклога в задачу итерации"""
    result = await db.execute(select(BacklogItem).where(BacklogItem.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Элемент бэклога не найден")
    # Verify project membership
    if user.role not in ADMIN_ROLES:
        member_result = await db.execute(
            select(ProjectMember).where(ProjectMember.project_id == item.project_id, ProjectMember.user_id == user.id)
        )
        if not member_result.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Вы не являетесь участником этого проекта")
    
    board_column_id = data.board_column_id
    if board_column_id is None:
        fr = await db.execute(
            select(BoardColumn)
            .where(BoardColumn.iteration_id == data.iteration_id)
            .order_by(BoardColumn.sort_order, BoardColumn.created_at)
            .limit(1)
        )
        first_col = fr.scalars().first()
        if not first_col:
            raise HTTPException(
                status_code=400,
                detail="Создайте колонку на доске или укажите board_column_id",
            )
        board_column_id = first_col.id
    else:
        cr = await db.execute(select(BoardColumn).where(BoardColumn.id == board_column_id))
        col = cr.scalar_one_or_none()
        if not col or col.iteration_id != data.iteration_id:
            raise HTTPException(status_code=400, detail="Некорректная колонка доски")

    initial_ids = [data.assignee_id] if data.assignee_id else []
    task = Task(
        iteration_id=data.iteration_id,
        title=item.title,
        description=item.description,
        assignee_id=data.assignee_id,
        creator_id=user.id,
        start_date=data.start_date,
        deadline=data.deadline,
        priority=data.priority,
        board_column_id=board_column_id,
        is_completed=False,
    )
    db.add(task)
    await db.delete(item)
    await db.flush()
    for uid in initial_ids:
        db.add(TaskAssignee(task_id=task.id, user_id=uid))
    await db.commit()

    tr = await db.execute(select(Task).options(selectinload(Task.assignees)).where(Task.id == task.id))
    task = tr.scalar_one()

    uid_set = {user.id, *initial_ids}
    users_result = await db.execute(select(User.id, User.name).where(User.id.in_(uid_set)))
    unames = {row.id: row.name for row in users_result.all()}
    return _serialize_task(task, unames)


# --- Board Column Management ---

@router.put("/iteration/{iteration_id}/board-columns/{column_id}", response_model=BoardColumnOut)
async def rename_board_column(
    iteration_id: uuid.UUID,
    column_id: uuid.UUID,
    data: BoardColumnCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    _member: ProjectMember = Depends(get_project_member_by_iteration),
):
    """Rename a board column."""
    result = await db.execute(
        select(BoardColumn).where(BoardColumn.id == column_id, BoardColumn.iteration_id == iteration_id)
    )
    col = result.scalar_one_or_none()
    if not col:
        raise HTTPException(status_code=404, detail="Колонка не найдена")
    col.title = data.title.strip()
    if data.sort_order is not None:
        col.sort_order = data.sort_order
    if data.color is not None:
        col.color = data.color
    await db.commit()
    await db.refresh(col)
    return BoardColumnOut.model_validate(col)


@router.delete("/iteration/{iteration_id}/board-columns/{column_id}")
async def delete_board_column(
    iteration_id: uuid.UUID,
    column_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    _member: ProjectMember = Depends(get_project_member_by_iteration),
):
    """Delete a board column together with all its tasks."""
    result = await db.execute(
        select(BoardColumn).where(BoardColumn.id == column_id, BoardColumn.iteration_id == iteration_id)
    )
    col = result.scalar_one_or_none()
    if not col:
        raise HTTPException(status_code=404, detail="Колонка не найдена")
    # Delete all tasks in this column (children cascade via parent FK)
    tasks_result = await db.execute(
        select(Task).where(Task.board_column_id == column_id, Task.parent_id.is_(None))
    )
    for task in tasks_result.scalars().all():
        await db.delete(task)
    await db.delete(col)
    await db.commit()
    return {"message": "Колонка удалена"}


@router.patch("/iteration/{iteration_id}/board-columns/reorder")
async def reorder_board_columns(
    iteration_id: uuid.UUID,
    order: list[dict],
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    _member: ProjectMember = Depends(get_project_member_by_iteration),
):
    """Reorder board columns. Expects list of {id, sort_order}."""
    for item in order:
        col_id = item.get("id")
        sort_order = item.get("sort_order")
        if col_id is None or sort_order is None:
            continue
        result = await db.execute(
            select(BoardColumn).where(BoardColumn.id == uuid.UUID(col_id), BoardColumn.iteration_id == iteration_id)
        )
        col = result.scalar_one_or_none()
        if col:
            col.sort_order = sort_order
    await db.commit()
    return {"message": "OK"}
