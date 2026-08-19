# Уведомления по WebSocket для глобальных обновлений (заявки, проекты)
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application, ApplicationMember, ApplicationSource
from app.models.project import ProjectMember
from app.models.user import User, UserRole


async def notify_application_watchers(db: AsyncSession, application_id: uuid.UUID) -> None:
    """Событие для списка/карточки заявки: консультант(ы), участники заявки, проекта и руководство."""
    from app.websocket import manager as ws_mgr

    uid_set: set[uuid.UUID] = set()
    row = (
        await db.execute(
            select(Application.consultant_id, Application.project_id, Application.source).where(
                Application.id == application_id
            )
        )
    ).first()
    if not row:
        return
    consultant_id, proj_id, source = row[0], row[1], row[2]
    if consultant_id:
        uid_set.add(consultant_id)
    elif source == ApplicationSource.WEBSITE:
        crows = await db.execute(select(User.id).where(User.role == UserRole.CONSULTANT))
        uid_set.update(r[0] for r in crows.all())
    mres = await db.execute(
        select(ApplicationMember.user_id).where(ApplicationMember.application_id == application_id)
    )
    uid_set.update(r[0] for r in mres.all())
    if proj_id:
        pres = await db.execute(select(ProjectMember.user_id).where(ProjectMember.project_id == proj_id))
        uid_set.update(r[0] for r in pres.all())
    lres = await db.execute(
        select(User.id).where(User.role.in_([UserRole.ADMIN, UserRole.OWNER, UserRole.DEPUTY_OWNER]))
    )
    uid_set.update(r[0] for r in lres.all())

    payload = {
        "type": "resource_changed",
        "resource": "application",
        "application_id": str(application_id),
        "project_id": str(proj_id) if proj_id else None,
    }
    for uid in uid_set:
        await ws_mgr.send_to_user(str(uid), payload)


async def notify_project_watchers(db: AsyncSession, project_id: uuid.UUID) -> None:
    """Обновление проекта/итераций для участников и руководства."""
    from app.websocket import manager as ws_mgr

    uids: set[uuid.UUID] = set()
    pres = await db.execute(select(ProjectMember.user_id).where(ProjectMember.project_id == project_id))
    uids.update(r[0] for r in pres.all())
    lres = await db.execute(
        select(User.id).where(User.role.in_([UserRole.ADMIN, UserRole.OWNER, UserRole.DEPUTY_OWNER]))
    )
    uids.update(r[0] for r in lres.all())

    payload = {
        "type": "resource_changed",
        "resource": "project",
        "project_id": str(project_id),
    }
    for uid in uids:
        await ws_mgr.send_to_user(str(uid), payload)
