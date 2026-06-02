# API чата (HTTP-эндпоинты, WebSocket — в websocket/manager.py)
import uuid
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.chat import ChatMessage, ChatPoll, ChatPollOption, ChatPollVote
from app.models.project import ProjectMember
from app.models.user import User, UserRole
from app.schemas.chat import ChatMessageCreate, ChatMessageUpdate, ChatMessageOut, PollCreate, PollVote
from app.middleware.auth import get_current_user
from app.dependencies import get_project_member_by_iteration
from app.services.search import index_message, delete_message as es_delete_message, search_messages
from app.services.s3 import upload_file_to_s3, delete_file_from_s3

router = APIRouter(prefix="/chat", tags=["Чат"])

MESSAGE_EDIT_WINDOW_HOURS = 24  # Редактирование в течение 24 часов
MAX_POLL_OPTIONS = 20


# --- Полнотекстовый поиск (Elasticsearch) ---
# NB: must be BEFORE /{iteration_id}/* routes to avoid FastAPI matching "search" as UUID
@router.get("/search/messages")
async def search_chat(
    q: str = Query(..., min_length=1, max_length=200, description="Поисковый запрос"),
    iteration_id: uuid.UUID | None = None,
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Полнотекстовый поиск по сообщениям чата (ТЗ 3.9.5)"""
    if iteration_id:
        from app.models.iteration import Iteration
        iter_result = await db.execute(select(Iteration).where(Iteration.id == iteration_id))
        iteration = iter_result.scalar_one_or_none()
        if not iteration:
            raise HTTPException(status_code=404, detail="Итерация не найдена")
        if user.role != UserRole.ADMIN:
            member_result = await db.execute(
                select(ProjectMember).where(ProjectMember.project_id == iteration.project_id, ProjectMember.user_id == user.id)
            )
            if not member_result.scalar_one_or_none():
                raise HTTPException(status_code=403, detail="Вы не являетесь участником этого проекта")
    else:
        if user.role != UserRole.ADMIN:
            from app.models.iteration import Iteration
            member_iters = await db.execute(
                select(Iteration.id)
                .join(ProjectMember, ProjectMember.project_id == Iteration.project_id)
                .where(ProjectMember.user_id == user.id)
            )
            accessible_ids = [str(row[0]) for row in member_iters.all()]
            if not accessible_ids:
                return []
            all_results = []
            for aid in accessible_ids[:50]:
                results = await search_messages(query=q, iteration_id=aid, limit=limit)
                all_results.extend(results)
            all_results.sort(key=lambda x: x.get('created_at', ''), reverse=True)
            return all_results[:limit]

    results = await search_messages(
        query=q,
        iteration_id=str(iteration_id) if iteration_id else None,
        limit=limit,
    )
    return results


@router.get("/{iteration_id}/messages", response_model=list[ChatMessageOut])
async def list_messages(
    iteration_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    _member: ProjectMember = Depends(get_project_member_by_iteration),
):
    """Список сообщений итерации с пагинацией"""
    result = await db.execute(
        select(ChatMessage)
        .options(selectinload(ChatMessage.poll).selectinload(ChatPoll.options).selectinload(ChatPollOption.votes))
        .where(ChatMessage.iteration_id == iteration_id)
        .order_by(ChatMessage.created_at.asc())
        .offset(offset).limit(limit)
    )
    messages = result.scalars().all()
    
    # Batch-fetch user names
    user_ids = {m.user_id for m in messages}
    if user_ids:
        users_result = await db.execute(select(User.id, User.name, User.avatar_url).where(User.id.in_(user_ids)))
        user_map = {row.id: (row.name, row.avatar_url) for row in users_result.all()}
    else:
        user_map = {}
    
    out = []
    for m in messages:
        msg_user_name, msg_user_avatar = user_map.get(m.user_id, (None, None))
        
        poll_data = None
        if m.poll:
            poll_data = {
                "id": str(m.poll.id),
                "question": m.poll.question,
                "is_multiple": m.poll.is_multiple,
                "is_closed": m.poll.is_closed,
                "options": [
                    {
                        "id": str(opt.id),
                        "text": opt.text,
                        "votes_count": len(opt.votes),
                        "voters": [
                            {"user_id": str(v.user_id)} for v in opt.votes
                        ],
                    }
                    for opt in sorted(m.poll.options, key=lambda o: o.order)
                ],
            }
        
        out.append(ChatMessageOut(
            id=m.id, iteration_id=m.iteration_id, user_id=m.user_id,
            user_name=msg_user_name,
            user_avatar=msg_user_avatar,
            content=m.content if not m.is_deleted else "[Сообщение удалено]",
            file_url=None if m.is_deleted else m.file_url,
            file_name=None if m.is_deleted else m.file_name,
            file_size=None if m.is_deleted else m.file_size,
            file_mime=None if m.is_deleted else m.file_mime,
            reply_to_id=m.reply_to_id,
            reply_to_content=None, reply_to_user_name=None,
            is_edited=m.is_edited, is_deleted=m.is_deleted,
            poll=poll_data, created_at=m.created_at, updated_at=m.updated_at,
        ))
    
    # Fill reply info in a second pass
    msg_map = {str(o.id): o for o in out}

    # Avoid N+1: batch-fetch missing reply messages + their users.
    missing_reply_ids = {
        str(o.reply_to_id)
        for o in out
        if o.reply_to_id and not msg_map.get(str(o.reply_to_id))
    }
    missing_msg_map: dict[str, tuple[str, uuid.UUID]] = {}
    missing_user_ids: set[uuid.UUID] = set()

    if missing_reply_ids:
        missing_uuid_ids = [uuid.UUID(mid) for mid in missing_reply_ids]
        rr = await db.execute(
            select(ChatMessage.id, ChatMessage.content, ChatMessage.user_id)
            .where(ChatMessage.id.in_(missing_uuid_ids))
        )
        rows = rr.all()
        for row in rows:
            mid = str(row.id)
            missing_msg_map[mid] = (row.content or "", row.user_id)
            missing_user_ids.add(row.user_id)

    user_name_map: dict[uuid.UUID, str] = {}
    if missing_user_ids:
        users_result = await db.execute(
            select(User.id, User.name).where(User.id.in_(missing_user_ids))
        )
        for row in users_result.all():
            user_name_map[row.id] = row.name

    for o in out:
        if not o.reply_to_id:
            continue
        ref = msg_map.get(str(o.reply_to_id))
        if ref:
            o.reply_to_content = ref.content[:100]
            o.reply_to_user_name = ref.user_name
            continue

        reply_tuple = missing_msg_map.get(str(o.reply_to_id))
        if not reply_tuple:
            continue

        reply_content, reply_user_id = reply_tuple
        o.reply_to_content = reply_content[:100]
        o.reply_to_user_name = user_name_map.get(reply_user_id)
    return out


@router.post("/{iteration_id}/messages", response_model=ChatMessageOut, status_code=201)
async def send_message(
    iteration_id: uuid.UUID, data: ChatMessageCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    _member: ProjectMember = Depends(get_project_member_by_iteration),
):
    msg = ChatMessage(iteration_id=iteration_id, user_id=user.id, content=data.content, reply_to_id=data.reply_to_id)
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    
    # Reply info
    reply_to_content = None
    reply_to_user_name = None
    if msg.reply_to_id:
        rr = await db.execute(select(ChatMessage).where(ChatMessage.id == msg.reply_to_id))
        reply_msg = rr.scalar_one_or_none()
        if reply_msg:
            reply_to_content = reply_msg.content[:100]
            ru = await db.execute(select(User.name).where(User.id == reply_msg.user_id))
            reply_to_user_name = ru.scalar_one_or_none()
    
    # Index in Elasticsearch
    await index_message(
        message_id=str(msg.id), iteration_id=str(iteration_id),
        user_id=str(user.id), user_name=user.name, content=data.content, created_at=msg.created_at,
    )
    
    return ChatMessageOut(
        id=msg.id, iteration_id=msg.iteration_id, user_id=msg.user_id,
        user_name=user.name, user_avatar=user.avatar_url,
        content=msg.content, reply_to_id=msg.reply_to_id,
        reply_to_content=reply_to_content, reply_to_user_name=reply_to_user_name,
        created_at=msg.created_at, updated_at=msg.updated_at,
    )


@router.post("/{iteration_id}/messages/upload", response_model=ChatMessageOut, status_code=201)
async def send_message_with_file(
    iteration_id: uuid.UUID,
    file: UploadFile = File(...),
    content: str = Form(""),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    _member: ProjectMember = Depends(get_project_member_by_iteration),
):
    """Отправка сообщения с файлом"""
    # Validate file size
    if file.size and file.size > 100 * 1024 * 1024:  # 100MB
        raise HTTPException(status_code=400, detail="Файл слишком большой (максимум 100MB)")
    file_url = await upload_file_to_s3(file, f"chat/{iteration_id}")
    msg = ChatMessage(
        iteration_id=iteration_id, user_id=user.id,
        content=content or file.filename,
        file_url=file_url, file_name=file.filename,
        file_size=file.size, file_mime=file.content_type,
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    return ChatMessageOut(
        id=msg.id, iteration_id=msg.iteration_id, user_id=msg.user_id,
        user_name=user.name, user_avatar=user.avatar_url,
        content=msg.content, file_url=msg.file_url, file_name=msg.file_name,
        file_size=msg.file_size, file_mime=msg.file_mime,
        created_at=msg.created_at, updated_at=msg.updated_at,
    )


@router.put("/messages/{message_id}", response_model=ChatMessageOut)
async def edit_message(message_id: uuid.UUID, data: ChatMessageUpdate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Редактирование сообщения — в течение 24 часов"""
    result = await db.execute(select(ChatMessage).where(ChatMessage.id == message_id))
    msg = result.scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=404, detail="Сообщение не найдено")
    if msg.user_id != user.id:
        raise HTTPException(status_code=403, detail="Можно редактировать только свои сообщения")
    
    if datetime.utcnow() - msg.created_at > timedelta(hours=MESSAGE_EDIT_WINDOW_HOURS):
        raise HTTPException(status_code=403, detail="Время для редактирования истекло (24 часа)")
    
    msg.content = data.content
    msg.is_edited = True
    msg.updated_at = datetime.utcnow()
    await db.commit()
    
    return ChatMessageOut(
        id=msg.id, iteration_id=msg.iteration_id, user_id=msg.user_id,
        user_name=user.name, content=msg.content, is_edited=True,
        created_at=msg.created_at, updated_at=msg.updated_at,
    )


@router.delete("/messages/{message_id}")
async def delete_message(message_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Удаление сообщения (автор или администратор)"""
    result = await db.execute(select(ChatMessage).where(ChatMessage.id == message_id))
    msg = result.scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=404, detail="Сообщение не найдено")
    
    if msg.user_id != user.id and user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Нет прав на удаление")
    
    # Delete attached file from S3 if present
    if msg.file_url:
        delete_file_from_s3(msg.file_url)
    
    msg.is_deleted = True
    msg.content = ""
    msg.file_url = None
    msg.file_name = None
    msg.file_size = None
    msg.file_mime = None
    await db.commit()
    
    # Remove from Elasticsearch
    await es_delete_message(str(msg.id))
    
    return {"message": "Сообщение удалено"}


# --- Опросы ---

@router.post("/{iteration_id}/polls", status_code=201)
async def create_poll(
    iteration_id: uuid.UUID, data: PollCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    _member: ProjectMember = Depends(get_project_member_by_iteration),
):
    """Создание опроса (до 20 вариантов, только открытое голосование)"""
    if len(data.options) > MAX_POLL_OPTIONS:
        raise HTTPException(status_code=400, detail=f"Максимум {MAX_POLL_OPTIONS} вариантов ответа")
    
    poll = ChatPoll(question=data.question, creator_id=user.id, is_multiple=data.is_multiple)
    db.add(poll)
    await db.flush()
    
    for i, opt_text in enumerate(data.options):
        option = ChatPollOption(poll_id=poll.id, text=opt_text, order=i)
        db.add(option)
    
    # Создаём сообщение с опросом
    msg = ChatMessage(
        iteration_id=iteration_id, user_id=user.id,
        content=f"📊 Опрос: {data.question}", poll_id=poll.id,
    )
    db.add(msg)
    await db.commit()
    
    return {"message": "Опрос создан", "poll_id": str(poll.id)}


@router.post("/polls/{poll_id}/vote")
async def vote_poll(poll_id: uuid.UUID, data: PollVote, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Голосование (открытое, видны имена проголосовавших)"""
    result = await db.execute(
        select(ChatPoll).options(selectinload(ChatPoll.options)).where(ChatPoll.id == poll_id)
    )
    poll = result.scalar_one_or_none()
    if not poll:
        raise HTTPException(status_code=404, detail="Опрос не найден")
    if poll.is_closed:
        raise HTTPException(status_code=400, detail="Опрос завершён")
    
    # Проверить, что option принадлежит этому опросу
    option_ids = [opt.id for opt in poll.options]
    if data.option_id not in option_ids:
        raise HTTPException(status_code=400, detail="Вариант не принадлежит этому опросу")
    
    if not poll.is_multiple:
        # Удалить предыдущий голос
        for opt in poll.options:
            existing = await db.execute(
                select(ChatPollVote).where(ChatPollVote.option_id == opt.id, ChatPollVote.user_id == user.id)
            )
            ev = existing.scalar_one_or_none()
            if ev:
                await db.delete(ev)
    
    # Проверить, не голосовал ли за этот вариант
    existing = await db.execute(
        select(ChatPollVote).where(ChatPollVote.option_id == data.option_id, ChatPollVote.user_id == user.id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Вы уже голосовали за этот вариант")
    
    vote = ChatPollVote(option_id=data.option_id, user_id=user.id)
    db.add(vote)
    await db.commit()
    return {"message": "Голос учтён"}


@router.post("/polls/{poll_id}/close")
async def close_poll(poll_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Завершение опроса (только автор)"""
    result = await db.execute(select(ChatPoll).where(ChatPoll.id == poll_id))
    poll = result.scalar_one_or_none()
    if not poll:
        raise HTTPException(status_code=404, detail="Опрос не найден")
    if poll.creator_id != user.id:
        raise HTTPException(status_code=403, detail="Только автор может завершить опрос")
    
    poll.is_closed = True
    await db.commit()
    return {"message": "Опрос завершён"}
