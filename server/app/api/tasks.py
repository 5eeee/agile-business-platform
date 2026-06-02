# API задач и бэклога
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.board_column import BoardColumn
from app.models.task import Task, TaskComment, TaskHistory, TaskAttachment
from app.models.backlog import BacklogItem
from app.models.iteration import Iteration
from app.models.project import ProjectMember
from app.models.user import User, UserRole
from app.schemas.task import (
    TaskCreate, TaskUpdate, TaskOut, TaskDetailOut, TaskCommentCreate,
    TaskCommentOut, TaskHistoryOut,
    BacklogItemCreate, BacklogItemOut, BacklogToTask,
)
from app.schemas.board_column import BoardColumnCreate, BoardColumnOut
from app.middleware.auth import get_current_user
from app.dependencies import get_project_member, get_project_member_by_iteration
from app.config import TASK_STATUSES, TASK_PRIORITIES

router = APIRouter(prefix="/tasks", tags=["Задачи"])


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
    return BoardColumnOut.model_validate(col)


def _serialize_task(t: Task, user_names: dict[uuid.UUID, str]) -> TaskOut:
    return TaskOut(
        id=t.id,
        iteration_id=t.iteration_id,
        title=t.title,
        description=t.description,
        status=t.status,
        priority=t.priority,
        assignee_id=t.assignee_id,
        assignee_name=user_names.get(t.assignee_id) if t.assignee_id else None,
        creator_id=t.creator_id,
        creator_name=user_names.get(t.creator_id),
        start_date=t.start_date,
        deadline=t.deadline,
        parent_id=t.parent_id,
        board_column_id=t.board_column_id,
        is_completed=bool(getattr(t, "is_completed", False)),
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
    query = select(Task).where(Task.iteration_id == iteration_id)
    if status:
        query = query.where(Task.status == status)
    if priority:
        query = query.where(Task.priority == priority)
    if assignee_id:
        query = query.where(Task.assignee_id == assignee_id)
    query = query.order_by(Task.created_at.desc())
    
    result = await db.execute(query)
    tasks = result.scalars().all()
    
    # Batch-fetch user names to avoid N+1 queries
    user_ids: set[uuid.UUID] = set()
    for t in tasks:
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
        .options(selectinload(Task.comments), selectinload(Task.history), selectinload(Task.attachments))
        .where(Task.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    
    # Verify project membership via iteration
    if user.role != UserRole.ADMIN:
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
    if user.role != UserRole.ADMIN:
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

    task = Task(
        iteration_id=data.iteration_id,
        title=data.title,
        description=data.description,
        assignee_id=data.assignee_id,
        creator_id=user.id,
        start_date=data.start_date,
        deadline=data.deadline,
        priority=data.priority,
        parent_id=parent_id,
        board_column_id=board_column_id,
        is_completed=False,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    
    # Notify assignee
    if task.assignee_id and task.assignee_id != user.id:
        from app.models.notification import Notification
        from app.services.telegram import notify_task_assigned
        from app.websocket import manager
        notif = Notification(
            user_id=task.assignee_id,
            title="Новая задача",
            message=f"{user.name} назначил вам задачу: {task.title}",
            type="task",
        )
        db.add(notif)
        await db.commit()
        # Push via WebSocket
        await manager.send_to_user(str(task.assignee_id), {
            "type": "notification",
            "title": notif.title,
            "message": notif.message,
        })
        # Telegram
        assignee_result = await db.execute(select(User).where(User.id == task.assignee_id))
        assignee = assignee_result.scalar_one_or_none()
        if assignee and assignee.telegram_id and assignee.notify_tasks:
            iter_result = await db.execute(select(Iteration).where(Iteration.id == task.iteration_id))
            it = iter_result.scalar_one_or_none()
            await notify_task_assigned(assignee.telegram_id, task.title, it.name if it else "")
    
    unames = {user.id: user.name}
    if task.assignee_id:
        ar = await db.execute(select(User.name).where(User.id == task.assignee_id))
        row = ar.one_or_none()
        if row:
            unames[task.assignee_id] = row[0]
    return _serialize_task(task, unames)


@router.put("/{task_id}", response_model=TaskOut)
async def update_task(task_id: uuid.UUID, data: TaskUpdate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    
    # Verify project membership via iteration
    if user.role != UserRole.ADMIN:
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

    old_assignee_id = task.assignee_id
    was_completed = bool(task.is_completed)
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        old_value = str(getattr(task, key)) if getattr(task, key) is not None else None
        new_value = str(value) if value is not None else None
        
        if old_value != new_value:
            history = TaskHistory(
                task_id=task.id, user_id=user.id, field=key,
                old_value=old_value, new_value=new_value,
            )
            db.add(history)
        
        setattr(task, key, value)
    
    # Coin reward for task completion with anti-cheat protections.
    if update_data.get("is_completed") is True and not was_completed and task.assignee_id:
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
    await db.refresh(task)
    
    # Broadcast task update to all WebSocket clients in this iteration
    from app.websocket import manager as ws_manager
    await ws_manager.broadcast_to_iteration(str(task.iteration_id), {
        "type": "task_update",
        "task_id": str(task.id),
        "status": task.status,
        "priority": task.priority,
        "title": task.title,
        "is_completed": task.is_completed,
    })
    
    # Notify new assignee if reassigned
    if task.assignee_id and task.assignee_id != old_assignee_id and task.assignee_id != user.id:
        from app.models.notification import Notification
        from app.services.telegram import notify_task_assigned
        from app.websocket import manager as ws_manager
        notif = Notification(
            user_id=task.assignee_id,
            title="Назначена задача",
            message=f"{user.name} назначил вам задачу: {task.title}",
            type="task",
        )
        db.add(notif)
        await db.commit()
        await ws_manager.send_to_user(str(task.assignee_id), {
            "type": "notification", "title": notif.title, "message": notif.message,
        })
        # Telegram
        assignee_result = await db.execute(select(User).where(User.id == task.assignee_id))
        assignee = assignee_result.scalar_one_or_none()
        if assignee and assignee.telegram_id and assignee.notify_tasks:
            iter_result = await db.execute(select(Iteration).where(Iteration.id == task.iteration_id))
            it = iter_result.scalar_one_or_none()
            await notify_task_assigned(assignee.telegram_id, task.title, it.name if it else "")
    
    user_names = {user.id: user.name}
    if task.assignee_id:
        ar = await db.execute(select(User.name).where(User.id == task.assignee_id))
        row = ar.one_or_none()
        if row:
            user_names[task.assignee_id] = row[0]
    if task.creator_id not in user_names:
        cr = await db.execute(select(User.name).where(User.id == task.creator_id))
        row = cr.one_or_none()
        if row:
            user_names[task.creator_id] = row[0]
    return _serialize_task(task, user_names)


@router.delete("/{task_id}")
async def delete_task(task_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    
    # Only task creator, project member or admin can delete
    if user.role != UserRole.ADMIN and task.creator_id != user.id:
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
    
    await db.delete(task)
    await db.commit()
    return {"message": "Задача удалена"}


@router.post("/{task_id}/comments", response_model=TaskCommentOut, status_code=201)
async def add_comment(task_id: uuid.UUID, data: TaskCommentCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    # Verify task exists and user has access
    task_result = await db.execute(select(Task).where(Task.id == task_id))
    task = task_result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    if user.role != UserRole.ADMIN:
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
    task_result = await db.execute(select(Task).where(Task.id == task_id))
    task = task_result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    if user.role != UserRole.ADMIN:
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

backlog_router = APIRouter(prefix="/backlog", tags=["Бэклог"])


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
    if user.role != UserRole.ADMIN:
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
    if user.role != UserRole.ADMIN and item.creator_id != user.id:
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
    if user.role != UserRole.ADMIN:
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
    await db.commit()
    await db.refresh(task)
    
    unames = {user.id: user.name}
    if task.assignee_id:
        ar = await db.execute(select(User.name).where(User.id == task.assignee_id))
        row = ar.one_or_none()
        if row:
            unames[task.assignee_id] = row[0]
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
