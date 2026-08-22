import json
import uuid
import logging
import hashlib
import hmac
import asyncio
import base64
import binascii
import re
import time
from datetime import datetime, date, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from sqlalchemy import select, delete, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.config import settings, SPHERES
from app.rate_limit import limiter
from app.models.user import User, UserRole
from app.models.notification import Notification
from app.models.application import (
    Application,
    ApplicationMember,
    ApplicationHistory,
    ApplicationTask,
    ApplicationTaskAssignee,
    ApplicationSource,
    ApplicationStatus,
)
from app.models.project import Project, ProjectMember, ProjectRole
from app.models.iteration import Iteration, IterationStatus
from app.models.board_column import BoardColumn
from app.models.task import Task, TaskAssignee
from app.schemas.application import (
    ApplicationCreate, ApplicationWebhookCreate, ApplicationUpdate,
    ApplicationStatusChange, ApplicationMemberAdd,
    ApplicationTaskCreate, ApplicationTaskUpdate,
    ApplicationOut, ApplicationMemberOut, ApplicationHistoryOut, ApplicationTaskOut,
)
from app.middleware.auth import get_current_user, require_applications_access, FULL_ACCESS_ROLES
from app.services.telegram import notify_application_tz_approved

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/applications", tags=["Заявки"])

VALID_TRANSITIONS = {
    ApplicationStatus.NEW: {ApplicationStatus.CONTACTING},
    ApplicationStatus.CONTACTING: {ApplicationStatus.TZ_RECEIVED, ApplicationStatus.REVIEW},
    ApplicationStatus.TZ_RECEIVED: {ApplicationStatus.REVIEW},
    ApplicationStatus.REVIEW: {ApplicationStatus.APPROVED, ApplicationStatus.REVISION},
    ApplicationStatus.REVISION: {ApplicationStatus.REVIEW},
    ApplicationStatus.APPROVED: {ApplicationStatus.DISTRIBUTING},
    ApplicationStatus.DISTRIBUTING: {ApplicationStatus.COMPLETED},
}

# Консультант: только свои заявки и ограниченные переходы
CONSULTANT_STATUS_TRANSITIONS = {
    ApplicationStatus.NEW: {ApplicationStatus.CONTACTING},
    ApplicationStatus.CONTACTING: {ApplicationStatus.REVIEW},
    ApplicationStatus.TZ_RECEIVED: {ApplicationStatus.REVIEW},
    ApplicationStatus.REVISION: {ApplicationStatus.REVIEW},
}


def _is_full_access(user: User) -> bool:
    return user.role in FULL_ACCESS_ROLES


def _consultant_owns(user: User, app: Application) -> bool:
    if app.consultant_id is not None:
        return app.consultant_id == user.id
    # Общая очередь: заявка с сайта без закреплённого консультанта — доступна всем консультантам
    return user.role == UserRole.CONSULTANT and app.source == ApplicationSource.WEBSITE


def _consultant_may_edit(user: User, app: Application) -> bool:
    if _is_full_access(user):
        return True
    if user.role != UserRole.CONSULTANT:
        return False
    if not _consultant_owns(user, app):
        return False
    return app.status in (
        ApplicationStatus.NEW,
        ApplicationStatus.CONTACTING,
        ApplicationStatus.REVISION,
        ApplicationStatus.TZ_RECEIVED,
    )


def _consultant_may_change_status(user: User, app: Application, new_status: ApplicationStatus) -> bool:
    if not _consultant_owns(user, app):
        return False
    allowed = CONSULTANT_STATUS_TRANSITIONS.get(app.status, set())
    return new_status in allowed


def _parse_app_deadline(value: str | None) -> datetime | None:
    if not value or not str(value).strip():
        return None
    s = str(value).strip()
    for fmt in ("%d.%m.%Y %H.%M", "%d.%m.%Y %H:%M", "%d.%m.%Y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _resolve_assignee_ids(
    assignee_id: uuid.UUID | None,
    assignee_ids: list[uuid.UUID] | None,
) -> list[uuid.UUID]:
    out: list[uuid.UUID] = []
    if assignee_ids:
        out.extend(assignee_ids)
    if assignee_id:
        if assignee_id not in out:
            out.insert(0, assignee_id)
    seen: set[uuid.UUID] = set()
    uniq: list[uuid.UUID] = []
    for uid in out:
        if uid not in seen:
            seen.add(uid)
            uniq.append(uid)
    return uniq


def _task_to_out(t: ApplicationTask) -> ApplicationTaskOut:
    aids: list[uuid.UUID] = []
    anames: list[str] = []
    if t.assignees:
        for a in sorted(t.assignees, key=lambda x: (str(x.user_id),)):
            aids.append(a.user_id)
            if a.user and a.user.name:
                anames.append(a.user.name)
    if (not aids) and t.assignee_id:
        aids = [t.assignee_id]
        if t.assignee and t.assignee.name:
            anames = [t.assignee.name]
    assignee_name = None
    if anames:
        assignee_name = ", ".join(anames)
    elif t.assignee and t.assignee.name:
        assignee_name = t.assignee.name
    return ApplicationTaskOut(
        id=t.id,
        application_id=t.application_id,
        parent_id=t.parent_id,
        assignee_id=t.assignee_id,
        assignee_name=assignee_name,
        assignee_ids=aids,
        assignee_names=anames,
        title=t.title,
        description=t.description,
        department=t.department,
        deadline=t.deadline,
        is_completed=t.is_completed,
        created_at=t.created_at,
    )


async def _validate_application_task_parent(
    db: AsyncSession,
    app_id: uuid.UUID,
    task_id: uuid.UUID | None,
    new_parent_id: uuid.UUID | None,
) -> None:
    if new_parent_id is None:
        return
    if task_id is not None and new_parent_id == task_id:
        raise HTTPException(status_code=400, detail="Задача не может быть родителем самой себя")
    pres = await db.execute(
        select(ApplicationTask).where(
            ApplicationTask.id == new_parent_id,
            ApplicationTask.application_id == app_id,
        )
    )
    if not pres.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Родительская задача не найдена")
    if task_id is None:
        return
    tres = await db.execute(
        select(ApplicationTask).where(ApplicationTask.application_id == app_id),
    )
    by_id = {t.id: t for t in tres.scalars().all()}
    cur: uuid.UUID | None = new_parent_id
    for _ in range(len(by_id) + 2):
        if cur is None:
            return
        if cur == task_id:
            raise HTTPException(status_code=400, detail="Нельзя сделать родителем дочернюю задачу (цикл)")
        p = by_id.get(cur)
        cur = p.parent_id if p else None


def _ordered_application_tasks(tasks: list[ApplicationTask]) -> list[ApplicationTask]:
    children: dict[uuid.UUID | None, list[ApplicationTask]] = {}
    for t in tasks:
        children.setdefault(t.parent_id, []).append(t)
    for lst in children.values():
        lst.sort(key=lambda x: x.created_at)
    out: list[ApplicationTask] = []

    def walk(pid: uuid.UUID | None) -> None:
        for ch in children.get(pid, []):
            out.append(ch)
            walk(ch.id)

    walk(None)
    return out


def _canonical_board_column_title(dept: str | None) -> str:
    """Имя колонки на доске: стандартное название сферы из SPHERES или произвольный отдел («Без сферы»)."""
    if not dept or not str(dept).strip():
        return "Без сферы"
    d = str(dept).strip()
    low = d.lower()
    for s in SPHERES:
        if s.strip().lower() == low:
            return s
    return d[:255]


def _ordered_sphere_columns_for_roots(roots: list[ApplicationTask]) -> list[str]:
    """Порядок колонок: как в SPHERES, затем остальные отделы из корневых задач."""
    order: list[str] = []
    seen: set[str] = set()
    for s in SPHERES:
        for t in roots:
            if _canonical_board_column_title(t.department) == s:
                if s not in seen:
                    seen.add(s)
                    order.append(s)
                break
    for t in roots:
        can = _canonical_board_column_title(t.department)
        if can not in seen:
            seen.add(can)
            order.append(can)
    return order


def _sphere_deadline_note(app: Application, dept: str | None, base_desc: str) -> str:
    desc = base_desc or ""
    if not app.sphere_deadlines_json or not dept:
        return desc
    try:
        sd = json.loads(app.sphere_deadlines_json)
    except json.JSONDecodeError:
        return desc
    if not isinstance(sd, dict):
        return desc
    key_norm = dept.strip().lower()
    for k, v in sd.items():
        if str(k).strip().lower() == key_norm and v:
            extra = f"\n\nДедлайн по сфере ({k}): {v}"
            desc = (desc + extra).strip()
            break
    return desc


async def _sync_application_to_project(
    db: AsyncSession,
    app: Application,
    user: User,
) -> None:
    """Создаёт проект и задачи из заявки; выставляет app.project_id."""
    if app.project_id:
        return
    name = (app.project_name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Укажите название проекта перед завершением заявки")
    tasks_res = await db.execute(
        select(ApplicationTask)
        .where(ApplicationTask.application_id == app.id)
        .options(
            selectinload(ApplicationTask.assignee),
            selectinload(ApplicationTask.assignees).selectinload(ApplicationTaskAssignee.user),
        )
    )
    tasks = list(tasks_res.scalars().all())
    roots = [t for t in tasks if t.parent_id is None]
    if not roots:
        raise HTTPException(
            status_code=400,
            detail="Добавьте хотя бы одну задачу (корневую) перед завершением заявки",
        )

    proj_desc = app.description
    if not proj_desc and app.client_name:
        proj_desc = f"Заявка: {app.client_name}"
    if proj_desc:
        proj_desc = proj_desc[:10000]

    project = Project(
        name=name[:255],
        description=proj_desc,
        creator_id=user.id,
    )
    db.add(project)
    await db.flush()

    owner_member = ProjectMember(
        project_id=project.id,
        user_id=user.id,
        is_admin=True,
        role=ProjectRole.OWNER,
    )
    db.add(owner_member)

    member_ids: set[uuid.UUID] = {user.id}
    if app.consultant_id:
        member_ids.add(app.consultant_id)
    for m in app.members or []:
        member_ids.add(m.user_id)
    for t in tasks:
        if t.assignee_id:
            member_ids.add(t.assignee_id)
        for a in t.assignees or []:
            member_ids.add(a.user_id)

    for uid in member_ids:
        if uid == user.id:
            continue
        db.add(
            ProjectMember(
                project_id=project.id,
                user_id=uid,
                is_admin=False,
                role=ProjectRole.MEMBER,
            )
        )

    today = date.today()
    iteration = Iteration(
        project_id=project.id,
        name="Итерация 1",
        start_date=today,
        end_date=today + timedelta(days=13),
        status=IterationStatus.ACTIVE,
        sort_order=0,
    )
    db.add(iteration)
    await db.flush()

    roots_only = [t for t in tasks if t.parent_id is None]
    column_titles = _ordered_sphere_columns_for_roots(roots_only)
    column_by_title: dict[str, uuid.UUID] = {}
    for sort_i, col_title in enumerate(column_titles):
        col = BoardColumn(
            iteration_id=iteration.id,
            title=col_title[:255],
            sort_order=sort_i,
        )
        db.add(col)
        await db.flush()
        column_by_title[col_title] = col.id

    if not column_by_title:
        col = BoardColumn(iteration_id=iteration.id, title="Колонка 1", sort_order=0)
        db.add(col)
        await db.flush()
        column_by_title["Колонка 1"] = col.id

    user_names: dict[uuid.UUID, str] = {}
    all_uids = set(member_ids)
    for t in tasks:
        for a in t.assignees or []:
            all_uids.add(a.user_id)
    if all_uids:
        ures = await db.execute(select(User).where(User.id.in_(all_uids)))
        for u in ures.scalars().all():
            user_names[u.id] = u.name or str(u.id)[:8]

    id_map: dict[uuid.UUID, uuid.UUID] = {}
    first_col_id = next(iter(column_by_title.values()))

    for at in _ordered_application_tasks(tasks):
        aid_list = _resolve_assignee_ids(at.assignee_id, [a.user_id for a in (at.assignees or [])])
        first_id = aid_list[0] if aid_list else None
        desc = at.description or ""
        desc = _sphere_deadline_note(app, at.department, desc)
        co_names = [user_names.get(uid) for uid in aid_list[1:]]
        co_names = [n for n in co_names if n]
        if co_names:
            desc = (desc + "\n\nСоисполнители: " + ", ".join(co_names)).strip()

        if at.parent_id is None:
            dept_key = _canonical_board_column_title(at.department)
            col_id = column_by_title.get(dept_key) or first_col_id
        else:
            col_id = None

        pt = Task(
            iteration_id=iteration.id,
            title=at.title[:255],
            description=desc or None,
            assignee_id=first_id,
            creator_id=user.id,
            start_date=None,
            deadline=at.deadline,
            parent_id=id_map.get(at.parent_id) if at.parent_id else None,
            board_column_id=col_id,
            is_completed=bool(at.is_completed),
        )
        db.add(pt)
        await db.flush()
        for uid in aid_list:
            db.add(TaskAssignee(task_id=pt.id, user_id=uid))
        id_map[at.id] = pt.id

    app.project_id = project.id


def _to_out(app: Application) -> ApplicationOut:
    members = [
        ApplicationMemberOut(
            id=m.id,
            user_id=m.user_id,
            user_name=m.user.name if m.user else None,
            created_at=m.created_at,
        )
        for m in (app.members or [])
    ]
    history = [
        ApplicationHistoryOut(
            id=h.id,
            user_id=h.user_id,
            user_name=h.user.name if h.user else None,
            old_status=h.old_status,
            new_status=h.new_status,
            comment=h.comment,
            created_at=h.created_at,
        )
        for h in sorted((app.history or []), key=lambda x: x.created_at)
    ]
    task_list = sorted((app.tasks or []), key=lambda x: (x.parent_id is None, x.created_at))
    tasks = [_task_to_out(t) for t in task_list]
    return ApplicationOut(
        id=app.id,
        source=app.source,
        external_reference=app.external_reference,
        status=app.status,
        client_name=app.client_name,
        client_email=app.client_email,
        client_phone=app.client_phone,
        client_company=app.client_company,
        description=app.description,
        tz_content=app.tz_content,
        departments=app.departments,
        consultant_id=app.consultant_id,
        consultant_name=app.consultant.name if app.consultant else None,
        approved_by_id=app.approved_by_id,
        approved_by_name=app.approved_by.name if app.approved_by else None,
        review_comment=app.review_comment,
        project_name=app.project_name,
        project_id=app.project_id,
        sphere_deadlines_json=app.sphere_deadlines_json,
        created_at=app.created_at,
        updated_at=app.updated_at,
        members=members,
        history=history,
        tasks=tasks,
    )


def _load_options():
    return [
        selectinload(Application.consultant),
        selectinload(Application.approved_by),
        selectinload(Application.linked_project),
        selectinload(Application.members).selectinload(ApplicationMember.user),
        selectinload(Application.history).selectinload(ApplicationHistory.user),
        selectinload(Application.tasks).selectinload(ApplicationTask.assignee),
        selectinload(Application.tasks).selectinload(ApplicationTask.assignees).selectinload(ApplicationTaskAssignee.user),
    ]


@router.get("", response_model=list[ApplicationOut])
async def list_applications(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_applications_access),
):
    q = select(Application).options(*_load_options()).order_by(Application.created_at.desc())
    if user.role == UserRole.CONSULTANT:
        q = q.where(
            or_(
                Application.consultant_id == user.id,
                (Application.source == ApplicationSource.WEBSITE)
                & (Application.consultant_id.is_(None)),
            )
        )
    result = await db.execute(q)
    return [_to_out(a) for a in result.scalars().all()]


@router.get("/{app_id}", response_model=ApplicationOut)
async def get_application(
    app_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_applications_access),
):
    result = await db.execute(
        select(Application).where(Application.id == app_id).options(*_load_options())
    )
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    if user.role == UserRole.CONSULTANT and not _consultant_owns(user, app):
        raise HTTPException(status_code=403, detail="Нет доступа к этой заявке")
    return _to_out(app)


@router.post("", response_model=ApplicationOut, status_code=201)
async def create_application(
    data: ApplicationCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_applications_access),
):
    if not (data.project_name and str(data.project_name).strip()):
        raise HTTPException(status_code=400, detail="Укажите название проекта")
    app = Application(
        source=ApplicationSource.MANUAL,
        client_name=data.client_name,
        client_email=data.client_email,
        client_phone=data.client_phone,
        client_company=data.client_company,
        description=data.description,
        consultant_id=user.id,
        project_name=str(data.project_name).strip(),
    )
    db.add(app)
    hist = ApplicationHistory(
        application=app, user_id=user.id,
        new_status=ApplicationStatus.NEW.value, comment="Заявка создана",
    )
    db.add(hist)
    await db.commit()

    result = await db.execute(
        select(Application).where(Application.id == app.id).options(*_load_options())
    )
    from app.services.realtime import notify_application_watchers
    await notify_application_watchers(db, app.id)
    return _to_out(result.scalar_one())


@router.put("/{app_id}", response_model=ApplicationOut)
async def update_application(
    app_id: uuid.UUID,
    data: ApplicationUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_applications_access),
):
    result = await db.execute(
        select(Application).where(Application.id == app_id).options(*_load_options())
    )
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    if not _consultant_may_edit(user, app):
        raise HTTPException(status_code=403, detail="Редактирование заявки недоступно на этом этапе")
    payload = data.model_dump(exclude_unset=True)
    if "sphere_deadlines_json" in payload and not _is_full_access(user):
        raise HTTPException(status_code=403, detail="Дедлайны по сферам может менять только руководство")
    if payload.get("sphere_deadlines_json") is not None:
        raw = payload["sphere_deadlines_json"]
        if raw == "":
            app.sphere_deadlines_json = None
            payload.pop("sphere_deadlines_json", None)
        else:
            try:
                json.loads(raw)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="sphere_deadlines_json должен быть валидным JSON")
    for key, value in payload.items():
        setattr(app, key, value)
    await db.commit()
    await db.refresh(app)
    result = await db.execute(
        select(Application).where(Application.id == app_id).options(*_load_options())
    )
    from app.services.realtime import notify_application_watchers
    await notify_application_watchers(db, app_id)
    return _to_out(result.scalar_one())


@router.post("/{app_id}/status", response_model=ApplicationOut)
async def change_status(
    app_id: uuid.UUID,
    data: ApplicationStatusChange,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_applications_access),
):
    result = await db.execute(
        select(Application).where(Application.id == app_id).options(*_load_options())
    )
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Заявка не найдена")

    try:
        new_status = ApplicationStatus(data.status)
    except ValueError:
        raise HTTPException(status_code=400, detail="Неизвестный статус")

    allowed = VALID_TRANSITIONS.get(app.status, set())
    if new_status not in allowed:
        raise HTTPException(status_code=400, detail=f"Переход {app.status.value} → {new_status.value} запрещён")

    if _is_full_access(user):
        pass  # полный набор переходов уже проверен
    elif user.role == UserRole.CONSULTANT:
        if not _consultant_may_change_status(user, app, new_status):
            raise HTTPException(status_code=403, detail="Недостаточно прав для смены статуса")
    else:
        raise HTTPException(status_code=403, detail="Недостаточно прав для смены статуса")

    if new_status == ApplicationStatus.APPROVED:
        app.approved_by_id = user.id
    if new_status == ApplicationStatus.REVISION:
        app.review_comment = data.comment

    if new_status == ApplicationStatus.COMPLETED:
        sync_res = await db.execute(
            select(Application).where(Application.id == app_id).options(*_load_options())
        )
        app_for_sync = sync_res.scalar_one()
        await _sync_application_to_project(db, app_for_sync, user)
        app.project_id = app_for_sync.project_id

    old_status = app.status.value
    app.status = new_status
    hist = ApplicationHistory(
        application_id=app.id, user_id=user.id,
        old_status=old_status, new_status=new_status.value,
        comment=data.comment,
    )
    db.add(hist)

    if new_status == ApplicationStatus.APPROVED:
        if app.consultant_id:
            cons_res = await db.execute(select(User).where(User.id == app.consultant_id))
            consultant = cons_res.scalar_one_or_none()
            if consultant:
                db.add(Notification(
                    user_id=app.consultant_id,
                    title="Заявка одобрена",
                    message=f"ТЗ по заявке «{app.client_name}» проверено и одобрено.",
                    type="application",
                    link=f"/applications/{app.id}",
                ))
                if consultant.telegram_id and getattr(consultant, "notify_tasks", True):
                    await notify_application_tz_approved(
                        consultant.telegram_id,
                        app.client_name,
                        str(app.id),
                    )
        elif app.source == ApplicationSource.WEBSITE:
            cres = await db.execute(select(User).where(User.role == UserRole.CONSULTANT))
            for consultant in cres.scalars().all():
                db.add(Notification(
                    user_id=consultant.id,
                    title="Заявка одобрена",
                    message=f"ТЗ по заявке «{app.client_name}» проверено и одобрено.",
                    type="application",
                    link=f"/applications/{app.id}",
                ))
                if consultant.telegram_id and getattr(consultant, "notify_tasks", True):
                    await notify_application_tz_approved(
                        consultant.telegram_id,
                        app.client_name,
                        str(app.id),
                    )

    await db.commit()

    result = await db.execute(
        select(Application).where(Application.id == app_id).options(*_load_options())
    )
    out_app = result.scalar_one()
    from app.services.realtime import notify_application_watchers, notify_project_watchers
    await notify_application_watchers(db, app_id)
    if out_app.project_id:
        await notify_project_watchers(db, out_app.project_id)
    return _to_out(out_app)


@router.post("/{app_id}/members", response_model=ApplicationMemberOut, status_code=201)
async def add_member(
    app_id: uuid.UUID,
    data: ApplicationMemberAdd,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_applications_access),
):
    if not _is_full_access(user):
        raise HTTPException(status_code=403, detail="Только руководство может назначать участников")
    result = await db.execute(select(Application).where(Application.id == app_id))
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Заявка не найдена")

    existing = await db.execute(
        select(ApplicationMember).where(
            ApplicationMember.application_id == app_id,
            ApplicationMember.user_id == data.user_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Сотрудник уже добавлен")

    target = await db.execute(select(User).where(User.id == data.user_id))
    target_user = target.scalar_one_or_none()
    if not target_user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    member = ApplicationMember(application_id=app_id, user_id=data.user_id)
    db.add(member)
    await db.commit()
    await db.refresh(member)
    from app.services.realtime import notify_application_watchers
    await notify_application_watchers(db, app_id)
    return ApplicationMemberOut(
        id=member.id, user_id=member.user_id,
        user_name=target_user.name, created_at=member.created_at,
    )


@router.delete("/{app_id}/members/{member_id}", status_code=204)
async def remove_member(
    app_id: uuid.UUID,
    member_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_applications_access),
):
    if not _is_full_access(user):
        raise HTTPException(status_code=403, detail="Только руководство может изменять участников")
    result = await db.execute(
        select(ApplicationMember).where(
            ApplicationMember.id == member_id, ApplicationMember.application_id == app_id,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Участник не найден")
    await db.delete(member)
    await db.commit()
    from app.services.realtime import notify_application_watchers
    await notify_application_watchers(db, app_id)


# --- Application Tasks (distribution by owner/deputy) ---

@router.post("/{app_id}/tasks", response_model=ApplicationTaskOut, status_code=201)
async def create_task(
    app_id: uuid.UUID,
    data: ApplicationTaskCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_applications_access),
):
    if not _is_full_access(user):
        raise HTTPException(status_code=403, detail="Только руководство может создавать задачи по заявке")
    result = await db.execute(select(Application).where(Application.id == app_id))
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Заявка не найдена")

    await _validate_application_task_parent(db, app_id, None, data.parent_id)

    assignee_ids = _resolve_assignee_ids(data.assignee_id, data.assignee_ids)
    if assignee_ids:
        ures = await db.execute(select(User.id).where(User.id.in_(assignee_ids)))
        found = set(ures.scalars().all())
        if any(x not in found for x in assignee_ids):
            raise HTTPException(status_code=404, detail="Пользователь-исполнитель не найден")

    dl: datetime | None = None
    if data.deadline is not None and str(data.deadline).strip():
        dl = _parse_app_deadline(data.deadline)
        if dl is None:
            raise HTTPException(
                status_code=400,
                detail="Дедлайн: используйте дд.мм.гггг чч.мм или дд.мм.гггг чч:мм",
            )

    task = ApplicationTask(
        application_id=app_id,
        parent_id=data.parent_id,
        assignee_id=assignee_ids[0] if assignee_ids else None,
        title=data.title,
        description=data.description,
        department=data.department,
        deadline=dl,
    )
    db.add(task)
    await db.flush()
    for uid in assignee_ids:
        db.add(ApplicationTaskAssignee(application_task_id=task.id, user_id=uid))
    await db.commit()

    loaded = await db.execute(
        select(ApplicationTask)
        .where(ApplicationTask.id == task.id)
        .options(
            selectinload(ApplicationTask.assignee),
            selectinload(ApplicationTask.assignees).selectinload(ApplicationTaskAssignee.user),
        )
    )
    from app.services.realtime import notify_application_watchers
    await notify_application_watchers(db, app_id)
    return _task_to_out(loaded.scalar_one())


@router.put("/{app_id}/tasks/{task_id}", response_model=ApplicationTaskOut)
async def update_task(
    app_id: uuid.UUID,
    task_id: uuid.UUID,
    data: ApplicationTaskUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_applications_access),
):
    if not _is_full_access(user):
        raise HTTPException(status_code=403, detail="Только руководство может изменять задачи")
    result = await db.execute(
        select(ApplicationTask).where(
            ApplicationTask.id == task_id, ApplicationTask.application_id == app_id,
        )
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")

    payload = data.model_dump(exclude_unset=True)
    new_parent = payload.get("parent_id", task.parent_id)
    if "parent_id" in payload:
        await _validate_application_task_parent(db, app_id, task_id, new_parent)

    if "deadline" in payload:
        raw_dl = payload.get("deadline")
        if raw_dl is None or (isinstance(raw_dl, str) and not raw_dl.strip()):
            task.deadline = None
        else:
            dl = _parse_app_deadline(raw_dl if isinstance(raw_dl, str) else str(raw_dl))
            if dl is None:
                raise HTTPException(
                    status_code=400,
                    detail="Дедлайн: используйте дд.мм.гггг чч.мм или дд.мм.гггг чч:мм",
                )
            task.deadline = dl
        payload.pop("deadline", None)

    reassign = False
    new_assignee_ids: list[uuid.UUID] | None = None
    if "assignee_ids" in payload or "assignee_id" in payload:
        aid = payload.pop("assignee_id", None) if "assignee_id" in payload else None
        aids = payload.pop("assignee_ids", None) if "assignee_ids" in payload else None
        new_assignee_ids = _resolve_assignee_ids(aid, aids)
        reassign = True

    for key, value in payload.items():
        setattr(task, key, value)

    if reassign and new_assignee_ids is not None:
        if new_assignee_ids:
            ures = await db.execute(select(User.id).where(User.id.in_(new_assignee_ids)))
            found = set(ures.scalars().all())
            if any(x not in found for x in new_assignee_ids):
                raise HTTPException(status_code=404, detail="Пользователь-исполнитель не найден")
        await db.execute(
            delete(ApplicationTaskAssignee).where(
                ApplicationTaskAssignee.application_task_id == task.id,
            )
        )
        task.assignee_id = new_assignee_ids[0] if new_assignee_ids else None
        for uid in new_assignee_ids:
            db.add(ApplicationTaskAssignee(application_task_id=task.id, user_id=uid))

    await db.commit()

    loaded = await db.execute(
        select(ApplicationTask)
        .where(ApplicationTask.id == task.id)
        .options(
            selectinload(ApplicationTask.assignee),
            selectinload(ApplicationTask.assignees).selectinload(ApplicationTaskAssignee.user),
        )
    )
    from app.services.realtime import notify_application_watchers
    await notify_application_watchers(db, app_id)
    return _task_to_out(loaded.scalar_one())


@router.delete("/{app_id}/tasks/{task_id}", status_code=204)
async def delete_task(
    app_id: uuid.UUID,
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_applications_access),
):
    if not _is_full_access(user):
        raise HTTPException(status_code=403, detail="Только руководство может удалять задачи")
    result = await db.execute(
        select(ApplicationTask).where(
            ApplicationTask.id == task_id, ApplicationTask.application_id == app_id,
        )
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    await db.delete(task)
    await db.commit()
    from app.services.realtime import notify_application_watchers
    await notify_application_watchers(db, app_id)


# --- Public webhook for website form (server-to-server) ---

webhook_router = APIRouter(tags=["Заявки (webhook)"])

WEBHOOK_SECRET = (settings.WEBSITE_WEBHOOK_SECRET or "").strip()
WEBSITE_PROOF_SEMAPHORE = asyncio.Semaphore(8)


def _precheck_website_proof(token: str, source_reference: str) -> None:
    """Reject malformed attacker input before spending an outbound HTTP request."""
    if len(token) < 40 or len(token) > 2048 or len(source_reference) > 160:
        raise HTTPException(status_code=403, detail="Invalid website proof")
    parts = token.split(".")
    if len(parts) != 2 or not all(parts):
        raise HTTPException(status_code=403, detail="Invalid website proof")
    try:
        padded = parts[0] + "=" * (-len(parts[0]) % 4)
        claims = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
    except (UnicodeError, ValueError, binascii.Error, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=403, detail="Invalid website proof") from exc
    expires_at = claims.get("exp")
    digest = claims.get("digest")
    now_ms = int(time.time() * 1000)
    if not (
        claims.get("reference") == source_reference
        and isinstance(digest, str)
        and re.fullmatch(r"[a-fA-F0-9]{64}", digest)
        and isinstance(expires_at, (int, float))
        and now_ms <= expires_at <= now_ms + 10 * 60_000
    ):
        raise HTTPException(status_code=403, detail="Invalid website proof")


@webhook_router.post("/applications/webhook", status_code=201)
@limiter.limit("15/minute")
async def webhook_create_application(
    request: Request,
    data: ApplicationWebhookCreate,
    db: AsyncSession = Depends(get_db),
    x_webhook_secret: str = Header("", alias="X-Webhook-Secret"),
):
    shared_secret_valid = bool(
        WEBHOOK_SECRET
        and hmac.compare_digest(x_webhook_secret.encode("utf-8"), WEBHOOK_SECRET.encode("utf-8"))
    )
    if not shared_secret_valid:
        token = (data.source_verification_token or "").strip()
        source_reference_candidate = (data.source_reference or "").strip()
        if not token or not source_reference_candidate:
            raise HTTPException(status_code=403, detail="Invalid website proof")
        _precheck_website_proof(token, source_reference_candidate)
        try:
            async with WEBSITE_PROOF_SEMAPHORE:
                async with httpx.AsyncClient(timeout=5, follow_redirects=False) as client:
                    proof_response = await client.post(
                        "https://agile-business-platform.vercel.app/api/platform/verify-lead-token",
                        json={"token": token},
                    )
            proof = proof_response.json() if proof_response.is_success else {}
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Website proof verification unavailable: %s", exc)
            raise HTTPException(status_code=503, detail="Website verification unavailable") from exc
        canonical = "\n".join((source_reference_candidate, (data.email or "").strip().lower(), data.name.strip()))
        expected_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        if not (
            proof.get("ok")
            and proof.get("reference") == source_reference_candidate
            and isinstance(proof.get("digest"), str)
            and hmac.compare_digest(proof["digest"], expected_digest)
        ):
            raise HTTPException(status_code=403, detail="Invalid website proof")

    source_reference = (data.source_reference or "").strip() or None
    if source_reference:
        existing_result = await db.execute(
            select(Application.id).where(Application.external_reference == source_reference)
        )
        existing_id = existing_result.scalar_one_or_none()
        if existing_id:
            return {"id": str(existing_id), "status": "existing"}

    # Название проекта: с визитки часто приходит только текст сообщения — подставляем сами
    raw_pn = (data.project_name or "").strip()
    if not raw_pn:
        msg = (data.message or "").strip()
        raw_pn = (msg.split("\n", 1)[0].strip()[:500] if msg else "") or f"Заявка: {data.name}"
    project_name = raw_pn[:500]

    description_parts = []
    if data.message:
        description_parts.append(data.message)
    if data.service:
        description_parts.append(f"Услуга: {data.service}")

    app = Application(
        source=ApplicationSource.WEBSITE,
        external_reference=source_reference,
        client_name=data.name,
        client_email=data.email,
        client_phone=data.phone,
        client_company=data.company,
        description="\n".join(description_parts) or None,
        project_name=project_name,
    )
    db.add(app)
    hist = ApplicationHistory(
        application=app, new_status=ApplicationStatus.NEW.value,
        comment="Заявка с сайта",
    )
    db.add(hist)
    await db.commit()
    logger.info("Website application created: %s (%s)", app.id, data.name)
    from app.services.realtime import notify_application_watchers
    await notify_application_watchers(db, app.id)
    return {"id": str(app.id), "status": "created"}
