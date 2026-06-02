# API обучения (LMS)
import uuid
import asyncio
import subprocess
import tempfile
import os
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import Optional

from app.database import get_db
from app.middleware.auth import get_current_user, require_admin
from app.models.user import User, UserRole
from app.models.notification import Notification
from app.models.training import (
    TrainingCourse, TrainingTopic, TrainingContent,
    TrainingTask, TrainingSubmission, SubmissionStatus,
    CourseAssignment, Hashtag, TopicProgress, topic_hashtags,
)
from app.models.gamification import TopicTestResult, CoinTransaction, CoinTransactionType
from app.schemas.training import (
    CourseCreate, CourseUpdate, CourseOut,
    TopicCreate, TopicUpdate, TopicOut, TopicDetailOut, ContentBlockOut, TaskBriefOut,
    ContentCreate, ContentUpdate,
    TaskCreate, TaskUpdate, TaskOut,
    SubmissionCreate, SubmissionReview, SubmissionOut,
    CourseAssign, CourseAssignmentOut, InternOut,
    HashtagCreate, HashtagOut,
    ProgressUpdate, ProgressOut,
    CodeRunRequest, CodeRunResult,
)
from app.rate_limit import limiter

router = APIRouter(prefix="/training", tags=["Обучение"])

# Allowed languages for code execution (whitelist)
ALLOWED_LANGUAGES = {
    "python": {"ext": ".py", "cmd": ["python3", "-u"], "timeout": 10},
    "javascript": {"ext": ".js", "cmd": ["node"], "timeout": 10},
    "typescript": {"ext": ".ts", "cmd": ["ts-node", "--transpile-only"], "timeout": 15},
    "bash": {"ext": ".sh", "cmd": ["bash"], "timeout": 10},
    "html": {"ext": ".html", "cmd": None, "timeout": 0},
}


async def grant_coin_once(
    db: AsyncSession,
    user_id: uuid.UUID,
    amount: int,
    tx_type: CoinTransactionType,
    reason: str,
    reference_id: uuid.UUID,
) -> bool:
    """Create coin transaction only once per (user, type, reference)."""
    exists = await db.execute(
        select(CoinTransaction.id).where(
            CoinTransaction.user_id == user_id,
            CoinTransaction.tx_type == tx_type,
            CoinTransaction.reference_id == reference_id,
        )
    )
    if exists.scalar_one_or_none():
        return False
    db.add(CoinTransaction(
        user_id=user_id,
        amount=amount,
        tx_type=tx_type,
        reason=reason,
        reference_id=reference_id,
    ))
    return True


def require_training_editor(user: User = Depends(get_current_user)) -> User:
    """Доступ для admin и training_editor"""
    if user.role == UserRole.ADMIN:
        return user
    if user.training_role == "training_editor":
        return user
    raise HTTPException(status_code=403, detail="Требуются права редактора обучения")


# ===================== COURSES =====================

@router.get("/courses", response_model=list[CourseOut])
async def list_courses(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Список курсов. Редакторы/админы видят все. Стажёры — только назначенные и опубликованные."""
    is_editor = user.role == UserRole.ADMIN or getattr(user, 'training_role', None) == "training_editor"
    q = select(TrainingCourse).options(selectinload(TrainingCourse.topics))
    if not is_editor:
        assigned_ids = select(CourseAssignment.course_id).where(CourseAssignment.user_id == user.id)
        q = q.where(TrainingCourse.is_published == True, TrainingCourse.id.in_(assigned_ids))
    q = q.order_by(TrainingCourse.order, TrainingCourse.created_at)
    result = await db.execute(q)
    courses = result.scalars().all()
    out = []
    for c in courses:
        out.append(CourseOut(
            id=c.id, title=c.title, description=c.description,
            order=c.order, is_published=c.is_published,
            topic_count=len(c.topics), created_at=c.created_at,
        ))
    return out


@router.post("/courses", response_model=CourseOut, status_code=201)
async def create_course(data: CourseCreate, db: AsyncSession = Depends(get_db), user: User = Depends(require_training_editor)):
    course = TrainingCourse(title=data.title, description=data.description, created_by=user.id)
    db.add(course)
    await db.commit()
    await db.refresh(course)
    return CourseOut(id=course.id, title=course.title, description=course.description,
                     order=course.order, is_published=course.is_published, topic_count=0, created_at=course.created_at)


@router.put("/courses/{course_id}", response_model=CourseOut)
async def update_course(course_id: uuid.UUID, data: CourseUpdate, db: AsyncSession = Depends(get_db), user: User = Depends(require_training_editor)):
    result = await db.execute(select(TrainingCourse).options(selectinload(TrainingCourse.topics)).where(TrainingCourse.id == course_id))
    course = result.scalar_one_or_none()
    if not course:
        raise HTTPException(404, "Курс не найден")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(course, k, v)
    await db.commit()
    await db.refresh(course)
    return CourseOut(id=course.id, title=course.title, description=course.description,
                     order=course.order, is_published=course.is_published, topic_count=len(course.topics), created_at=course.created_at)


@router.delete("/courses/{course_id}")
async def delete_course(course_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(require_training_editor)):
    result = await db.execute(select(TrainingCourse).where(TrainingCourse.id == course_id))
    course = result.scalar_one_or_none()
    if not course:
        raise HTTPException(404, "Курс не найден")
    await db.delete(course)
    await db.commit()
    return {"message": "Курс удалён"}


# ===================== TOPICS =====================

@router.get("/courses/{course_id}/topics", response_model=list[TopicOut])
async def list_topics(course_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Темы курса с информацией о разблокировке (последовательное прохождение)"""
    result = await db.execute(
        select(TrainingTopic)
        .options(selectinload(TrainingTopic.task), selectinload(TrainingTopic.hashtags))
        .where(TrainingTopic.course_id == course_id)
        .order_by(TrainingTopic.order, TrainingTopic.created_at)
    )
    topics = result.scalars().all()

    # Load progress for this user
    progress_result = await db.execute(
        select(TopicProgress).where(
            TopicProgress.user_id == user.id,
            TopicProgress.topic_id.in_([t.id for t in topics])
        )
    )
    progress_map = {p.topic_id: p.status for p in progress_result.scalars().all()}

    # Which topics contain tests
    test_topics_result = await db.execute(
        select(TrainingContent.topic_id)
        .where(
            TrainingContent.topic_id.in_([t.id for t in topics]),
            TrainingContent.content_type == "test",
        )
    )
    test_topic_ids = set(test_topics_result.scalars().all())

    # Passed tests for this user
    test_result_rows = await db.execute(
        select(TopicTestResult.topic_id, TopicTestResult.passed)
        .where(
            TopicTestResult.user_id == user.id,
            TopicTestResult.topic_id.in_([t.id for t in topics]),
        )
    )
    test_passed_map = {topic_id: bool(passed) for topic_id, passed in test_result_rows.all()}

    # Определяем какие темы разблокированы
    unlocked_set = set()
    completed_set = set()
    prev_unlocked = True
    for t in topics:
        topic_unlocked = prev_unlocked
        if topic_unlocked:
            unlocked_set.add(t.id)

        has_task = t.task is not None
        has_test = t.id in test_topic_ids

        task_ok = True
        if has_task and topic_unlocked:
            sub_result = await db.execute(
                select(TrainingSubmission).where(
                    TrainingSubmission.task_id == t.task.id,
                    TrainingSubmission.user_id == user.id,
                    TrainingSubmission.status == SubmissionStatus.APPROVED,
                )
            )
            approved = sub_result.scalars().first()
            task_ok = approved is not None

        test_ok = True
        if has_test:
            test_ok = bool(test_passed_map.get(t.id, False))

        if not has_task and not has_test:
            user_progress = progress_map.get(t.id, "not_started")
            topic_completed = user_progress == "completed"
        else:
            topic_completed = task_ok and test_ok

        if topic_completed:
            completed_set.add(t.id)

        prev_unlocked = topic_unlocked and topic_completed

    is_editor = user.role == UserRole.ADMIN or getattr(user, 'training_role', None) == "training_editor"

    out = []
    for t in topics:
        unlocked = True if is_editor else (t.id in unlocked_set)
        user_progress = progress_map.get(t.id, "not_started")
        if not unlocked:
            st = "locked"
        elif t.id in completed_set or user_progress == "completed":
            st = "completed"
        else:
            st = "in_progress"
        out.append(TopicOut(
            id=t.id, course_id=t.course_id, title=t.title,
            description=t.description, order=t.order,
            section_title=t.section_title,
            difficulty=t.difficulty,
            has_task=t.task is not None,
            is_unlocked=unlocked,
            status=st,
            progress=user_progress,
            hashtags=[HashtagOut.model_validate(h) for h in t.hashtags],
            created_at=t.created_at,
        ))
    return out


@router.post("/courses/{course_id}/topics", response_model=TopicOut, status_code=201)
async def create_topic(course_id: uuid.UUID, data: TopicCreate, db: AsyncSession = Depends(get_db), user: User = Depends(require_training_editor)):
    count = await db.execute(select(func.count(TrainingTopic.id)).where(TrainingTopic.course_id == course_id))
    order = count.scalar() or 0
    topic = TrainingTopic(
        course_id=course_id, title=data.title, description=data.description,
        order=order, section_title=data.section_title, difficulty=data.difficulty,
    )
    db.add(topic)
    await db.commit()
    await db.refresh(topic)
    return TopicOut(id=topic.id, course_id=topic.course_id, title=topic.title,
                    description=topic.description, order=topic.order,
                    section_title=topic.section_title, difficulty=topic.difficulty,
                    has_task=False, is_unlocked=True, status="in_progress", created_at=topic.created_at)


@router.get("/topics/{topic_id}", response_model=TopicDetailOut)
async def get_topic_detail(topic_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Детали темы с контент-блоками"""
    result = await db.execute(
        select(TrainingTopic)
        .options(selectinload(TrainingTopic.content_blocks), selectinload(TrainingTopic.task), selectinload(TrainingTopic.hashtags))
        .where(TrainingTopic.id == topic_id)
    )
    topic = result.scalar_one_or_none()
    if not topic:
        raise HTTPException(404, "Тема не найдена")
    is_editor = user.role == UserRole.ADMIN or getattr(user, 'training_role', None) == "training_editor"
    if not is_editor:
        assigned = await db.execute(
            select(CourseAssignment.id).where(
                CourseAssignment.course_id == topic.course_id,
                CourseAssignment.user_id == user.id,
            )
        )
        if not assigned.scalar_one_or_none():
            raise HTTPException(403, "Курс не назначен")

        # Lock guard: cannot open next topic until previous requirements are complete
        ordered_topics_result = await db.execute(
            select(TrainingTopic)
            .options(selectinload(TrainingTopic.task))
            .where(TrainingTopic.course_id == topic.course_id)
            .order_by(TrainingTopic.order, TrainingTopic.created_at)
        )
        ordered_topics = ordered_topics_result.scalars().all()
        ids = [t.id for t in ordered_topics]

        progress_result = await db.execute(
            select(TopicProgress).where(
                TopicProgress.user_id == user.id,
                TopicProgress.topic_id.in_(ids),
            )
        )
        progress_map = {p.topic_id: p.status for p in progress_result.scalars().all()}

        test_topics_result = await db.execute(
            select(TrainingContent.topic_id)
            .where(TrainingContent.topic_id.in_(ids), TrainingContent.content_type == "test")
        )
        test_topic_ids = set(test_topics_result.scalars().all())

        test_result_rows = await db.execute(
            select(TopicTestResult.topic_id, TopicTestResult.passed)
            .where(TopicTestResult.user_id == user.id, TopicTestResult.topic_id.in_(ids))
        )
        test_passed_map = {t_id: bool(passed) for t_id, passed in test_result_rows.all()}

        unlocked_set = set()
        prev_unlocked = True
        for t in ordered_topics:
            topic_unlocked = prev_unlocked
            if topic_unlocked:
                unlocked_set.add(t.id)

            has_task = t.task is not None
            has_test = t.id in test_topic_ids

            task_ok = True
            if has_task and topic_unlocked:
                sub_result = await db.execute(
                    select(TrainingSubmission).where(
                        TrainingSubmission.task_id == t.task.id,
                        TrainingSubmission.user_id == user.id,
                        TrainingSubmission.status == SubmissionStatus.APPROVED,
                    )
                )
                task_ok = sub_result.scalars().first() is not None

            test_ok = True
            if has_test:
                test_ok = bool(test_passed_map.get(t.id, False))

            if not has_task and not has_test:
                topic_completed = progress_map.get(t.id, "not_started") == "completed"
            else:
                topic_completed = task_ok and test_ok

            prev_unlocked = topic_unlocked and topic_completed

        if topic.id not in unlocked_set:
            raise HTTPException(403, "Сначала пройдите тест и требования предыдущей подтемы")

    prog_result = await db.execute(
        select(TopicProgress).where(TopicProgress.topic_id == topic_id, TopicProgress.user_id == user.id)
    )
    prog = prog_result.scalar_one_or_none()
    user_progress = prog.status if prog else "not_started"

    return TopicDetailOut(
        id=topic.id, course_id=topic.course_id, title=topic.title,
        description=topic.description, order=topic.order,
        section_title=topic.section_title, difficulty=topic.difficulty,
        has_task=topic.task is not None, is_unlocked=True,
        progress=user_progress,
        hashtags=[HashtagOut.model_validate(h) for h in topic.hashtags],
        created_at=topic.created_at,
        content_blocks=[ContentBlockOut.model_validate(cb) for cb in topic.content_blocks],
        task=TaskBriefOut.model_validate(topic.task) if topic.task else None,
    )


@router.put("/topics/{topic_id}", response_model=TopicOut)
async def update_topic(topic_id: uuid.UUID, data: TopicUpdate, db: AsyncSession = Depends(get_db), user: User = Depends(require_training_editor)):
    result = await db.execute(select(TrainingTopic).options(selectinload(TrainingTopic.task), selectinload(TrainingTopic.hashtags)).where(TrainingTopic.id == topic_id))
    topic = result.scalar_one_or_none()
    if not topic:
        raise HTTPException(404, "Тема не найдена")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(topic, k, v)
    await db.commit()
    await db.refresh(topic)
    return TopicOut(id=topic.id, course_id=topic.course_id, title=topic.title,
                    description=topic.description, order=topic.order,
                    section_title=topic.section_title, difficulty=topic.difficulty,
                    has_task=topic.task is not None, is_unlocked=True,
                    hashtags=[HashtagOut.model_validate(h) for h in topic.hashtags],
                    created_at=topic.created_at)


@router.delete("/topics/{topic_id}")
async def delete_topic(topic_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(require_training_editor)):
    result = await db.execute(select(TrainingTopic).where(TrainingTopic.id == topic_id))
    topic = result.scalar_one_or_none()
    if not topic:
        raise HTTPException(404, "Тема не найдена")
    await db.delete(topic)
    await db.commit()
    return {"message": "Тема удалена"}


# ===================== PROGRESS =====================

@router.put("/topics/{topic_id}/progress", response_model=ProgressOut)
async def update_progress(topic_id: uuid.UUID, data: ProgressUpdate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Обновить прогресс по подтеме"""
    topic_res = await db.execute(select(TrainingTopic).where(TrainingTopic.id == topic_id))
    if not topic_res.scalar_one_or_none():
        raise HTTPException(404, "Тема не найдена")

    result = await db.execute(
        select(TopicProgress).where(TopicProgress.topic_id == topic_id, TopicProgress.user_id == user.id)
    )
    progress = result.scalar_one_or_none()
    if progress:
        progress.status = data.status
        progress.updated_at = datetime.utcnow()
    else:
        progress = TopicProgress(topic_id=topic_id, user_id=user.id, status=data.status)
        db.add(progress)

    if data.status == "completed":
        await grant_coin_once(
            db=db,
            user_id=user.id,
            amount=5,
            tx_type=CoinTransactionType.TOPIC_COMPLETE,
            reason="Завершение подтемы",
            reference_id=topic_id,
        )

    await db.commit()
    await db.refresh(progress)
    return ProgressOut(topic_id=progress.topic_id, user_id=progress.user_id, status=progress.status, updated_at=progress.updated_at)


# ===================== HASHTAGS =====================

@router.get("/hashtags", response_model=list[HashtagOut])
async def list_hashtags(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Hashtag).order_by(Hashtag.name))
    return [HashtagOut.model_validate(h) for h in result.scalars().all()]


@router.post("/hashtags", response_model=HashtagOut, status_code=201)
async def create_hashtag(data: HashtagCreate, db: AsyncSession = Depends(get_db), user: User = Depends(require_training_editor)):
    existing = await db.execute(select(Hashtag).where(Hashtag.name == data.name))
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Хэштег с таким именем уже существует")
    h = Hashtag(name=data.name, color=data.color or "#6366f1")
    db.add(h)
    await db.commit()
    await db.refresh(h)
    return HashtagOut.model_validate(h)


@router.delete("/hashtags/{hashtag_id}")
async def delete_hashtag(hashtag_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(require_training_editor)):
    result = await db.execute(select(Hashtag).where(Hashtag.id == hashtag_id))
    h = result.scalar_one_or_none()
    if not h:
        raise HTTPException(404, "Хэштег не найден")
    await db.delete(h)
    await db.commit()
    return {"message": "Хэштег удалён"}


@router.post("/topics/{topic_id}/hashtags/{hashtag_id}")
async def assign_hashtag(topic_id: uuid.UUID, hashtag_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(require_training_editor)):
    topic_res = await db.execute(select(TrainingTopic).options(selectinload(TrainingTopic.hashtags)).where(TrainingTopic.id == topic_id))
    topic = topic_res.scalar_one_or_none()
    if not topic:
        raise HTTPException(404, "Тема не найдена")
    hashtag_res = await db.execute(select(Hashtag).where(Hashtag.id == hashtag_id))
    hashtag = hashtag_res.scalar_one_or_none()
    if not hashtag:
        raise HTTPException(404, "Хэштег не найден")
    if hashtag not in topic.hashtags:
        topic.hashtags.append(hashtag)
        await db.commit()
    return {"message": "Хэштег назначен"}


@router.delete("/topics/{topic_id}/hashtags/{hashtag_id}")
async def remove_hashtag(topic_id: uuid.UUID, hashtag_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(require_training_editor)):
    topic_res = await db.execute(select(TrainingTopic).options(selectinload(TrainingTopic.hashtags)).where(TrainingTopic.id == topic_id))
    topic = topic_res.scalar_one_or_none()
    if not topic:
        raise HTTPException(404, "Тема не найдена")
    hashtag_res = await db.execute(select(Hashtag).where(Hashtag.id == hashtag_id))
    hashtag = hashtag_res.scalar_one_or_none()
    if not hashtag:
        raise HTTPException(404, "Хэштег не найден")
    if hashtag in topic.hashtags:
        topic.hashtags.remove(hashtag)
        await db.commit()
    return {"message": "Хэштег снят"}


# ===================== CONTENT BLOCKS =====================

@router.post("/topics/{topic_id}/content", response_model=ContentBlockOut, status_code=201)
async def create_content_block(topic_id: uuid.UUID, data: ContentCreate, db: AsyncSession = Depends(get_db), user: User = Depends(require_training_editor)):
    count = await db.execute(select(func.count(TrainingContent.id)).where(TrainingContent.topic_id == topic_id))
    order = data.order if data.order else (count.scalar() or 0)
    block = TrainingContent(topic_id=topic_id, title=data.title, body=data.body, content_type=data.content_type or "text", order=order)
    db.add(block)
    await db.commit()
    await db.refresh(block)
    return ContentBlockOut.model_validate(block)


@router.put("/content/{block_id}", response_model=ContentBlockOut)
async def update_content_block(block_id: uuid.UUID, data: ContentUpdate, db: AsyncSession = Depends(get_db), user: User = Depends(require_training_editor)):
    result = await db.execute(select(TrainingContent).where(TrainingContent.id == block_id))
    block = result.scalar_one_or_none()
    if not block:
        raise HTTPException(404, "Блок не найден")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(block, k, v)
    await db.commit()
    await db.refresh(block)
    return ContentBlockOut.model_validate(block)


@router.delete("/content/{block_id}")
async def delete_content_block(block_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(require_training_editor)):
    result = await db.execute(select(TrainingContent).where(TrainingContent.id == block_id))
    block = result.scalar_one_or_none()
    if not block:
        raise HTTPException(404, "Блок не найден")
    await db.delete(block)
    await db.commit()
    return {"message": "Блок удалён"}


# ===================== TASKS =====================

@router.get("/tasks/{task_id}", response_model=TaskOut)
async def get_task(task_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(TrainingTask).where(TrainingTask.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(404, "Задание не найдено")
    return TaskOut.model_validate(task)


@router.post("/topics/{topic_id}/task", response_model=TaskOut, status_code=201)
async def create_task(topic_id: uuid.UUID, data: TaskCreate, db: AsyncSession = Depends(get_db), user: User = Depends(require_training_editor)):
    existing = await db.execute(select(TrainingTask).where(TrainingTask.topic_id == topic_id))
    if existing.scalar_one_or_none():
        raise HTTPException(400, "У этой темы уже есть задание")
    task = TrainingTask(topic_id=topic_id, title=data.title, description=data.description)
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return TaskOut.model_validate(task)


@router.put("/tasks/{task_id}", response_model=TaskOut)
async def update_task(task_id: uuid.UUID, data: TaskUpdate, db: AsyncSession = Depends(get_db), user: User = Depends(require_training_editor)):
    result = await db.execute(select(TrainingTask).where(TrainingTask.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(404, "Задание не найдено")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(task, k, v)
    await db.commit()
    await db.refresh(task)
    return TaskOut.model_validate(task)


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(require_training_editor)):
    result = await db.execute(select(TrainingTask).where(TrainingTask.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(404, "Задание не найдено")
    await db.delete(task)
    await db.commit()
    return {"message": "Задание удалено"}


# ===================== SUBMISSIONS =====================

@router.post("/tasks/{task_id}/submit", response_model=SubmissionOut)
async def submit_answer(
    task_id: uuid.UUID,
    content: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Отправить ответ на задание (текст и/или файл)"""
    if not content and not file:
        raise HTTPException(400, "Нужно отправить текст или файл")

    is_editor = user.role == UserRole.ADMIN or getattr(user, 'training_role', None) == "training_editor"
    if not is_editor:
        task_res_check = await db.execute(
            select(TrainingTask).options(selectinload(TrainingTask.topic)).where(TrainingTask.id == task_id)
        )
        task_obj = task_res_check.scalar_one_or_none()
        if not task_obj:
            raise HTTPException(404, "Задание не найдено")
        assigned = await db.execute(
            select(CourseAssignment.id).where(
                CourseAssignment.course_id == task_obj.topic.course_id,
                CourseAssignment.user_id == user.id,
            )
        )
        if not assigned.scalar_one_or_none():
            raise HTTPException(403, "Курс не назначен")

    file_url = None
    if file:
        from app.services.s3 import upload_file_to_s3
        file_url = await upload_file_to_s3(file, prefix=f"training/{user.id}/{task_id}")

    sub = TrainingSubmission(
        task_id=task_id, user_id=user.id,
        content=content, file_url=file_url,
        status=SubmissionStatus.PENDING,
    )
    db.add(sub)
    await db.flush()

    task_res = await db.execute(select(TrainingTask.title).where(TrainingTask.id == task_id))
    task_title = task_res.scalar() or "Задание"

    editors_q = await db.execute(
        select(User.id).where(
            (User.training_role == "training_editor") | (User.role == UserRole.ADMIN)
        )
    )
    editor_ids_for_tg = []
    for (editor_id,) in editors_q.all():
        db.add(Notification(
            user_id=editor_id,
            title="Новый ответ на задание",
            message=f"{user.name} отправил ответ на задание '{task_title}'",
            type="training",
            link=f"/training",
        ))
        editor_ids_for_tg.append(editor_id)

    await db.commit()

    from app.services.telegram import send_telegram_message
    for eid in editor_ids_for_tg:
        editor_res = await db.execute(select(User).where(User.id == eid))
        editor = editor_res.scalar_one_or_none()
        if editor and editor.telegram_id and editor.notify_tasks:
            await send_telegram_message(
                editor.telegram_id,
                f"Новый ответ на задание\n{user.name} отправил ответ на '{task_title}'",
            )

    await db.refresh(sub)
    return SubmissionOut(
        id=sub.id, task_id=sub.task_id, user_id=sub.user_id, user_name=user.name,
        content=sub.content, file_url=sub.file_url, status=sub.status.value,
        created_at=sub.created_at,
    )


@router.get("/tasks/{task_id}/my-submission", response_model=Optional[SubmissionOut])
async def get_my_submission(task_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(
        select(TrainingSubmission)
        .where(TrainingSubmission.task_id == task_id, TrainingSubmission.user_id == user.id)
        .order_by(TrainingSubmission.created_at.desc())
    )
    sub = result.scalars().first()
    if not sub:
        return None
    return SubmissionOut(
        id=sub.id, task_id=sub.task_id, user_id=sub.user_id, user_name=user.name,
        content=sub.content, file_url=sub.file_url, status=sub.status.value,
        review_comment=sub.review_comment, reviewer_id=sub.reviewer_id,
        created_at=sub.created_at, reviewed_at=sub.reviewed_at,
    )


@router.get("/submissions/pending", response_model=list[SubmissionOut])
async def list_pending_submissions(db: AsyncSession = Depends(get_db), user: User = Depends(require_training_editor)):
    result = await db.execute(
        select(TrainingSubmission)
        .where(TrainingSubmission.status == SubmissionStatus.PENDING)
        .order_by(TrainingSubmission.created_at.asc())
    )
    subs = result.scalars().all()
    out = []
    for s in subs:
        user_res = await db.execute(select(User.name).where(User.id == s.user_id))
        name = user_res.scalar() or ""
        task_res = await db.execute(select(TrainingTask.title).where(TrainingTask.id == s.task_id))
        task_title = task_res.scalar() or ""
        out.append(SubmissionOut(
            id=s.id, task_id=s.task_id, user_id=s.user_id, user_name=name,
            task_title=task_title,
            content=s.content, file_url=s.file_url, status=s.status.value,
            review_comment=s.review_comment, reviewer_id=s.reviewer_id,
            created_at=s.created_at, reviewed_at=s.reviewed_at,
        ))
    return out


@router.post("/submissions/{submission_id}/review", response_model=SubmissionOut)
async def review_submission(submission_id: uuid.UUID, data: SubmissionReview, db: AsyncSession = Depends(get_db), user: User = Depends(require_training_editor)):
    result = await db.execute(select(TrainingSubmission).where(TrainingSubmission.id == submission_id))
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(404, "Ответ не найден")
    if data.status not in ("approved", "rejected"):
        raise HTTPException(400, "Статус должен быть approved или rejected")
    if sub.status != SubmissionStatus.PENDING:
        raise HTTPException(400, "Ответ уже проверен")
    sub.status = SubmissionStatus(data.status)
    sub.reviewer_id = user.id
    sub.review_comment = data.review_comment
    sub.reviewed_at = datetime.utcnow()

    status_text = "принят" if data.status == "approved" else "отклонен"
    task_res = await db.execute(select(TrainingTask.title).where(TrainingTask.id == sub.task_id))
    task_title = task_res.scalar() or "Задание"
    db.add(Notification(
        user_id=sub.user_id,
        title=f"Ответ {status_text}",
        message=f"Ваш ответ на задание '{task_title}' {status_text}" + (f". Комментарий: {data.review_comment}" if data.review_comment else ""),
        type="training",
        link=f"/training",
    ))

    if data.status == "approved":
        await grant_coin_once(
            db=db,
            user_id=sub.user_id,
            amount=15,
            tx_type=CoinTransactionType.TASK_APPROVED,
            reason=f"Принято задание: {task_title}",
            reference_id=sub.task_id,
        )

    await db.commit()

    from app.services.telegram import send_telegram_message
    intern_res = await db.execute(select(User).where(User.id == sub.user_id))
    intern_user = intern_res.scalar_one_or_none()
    if intern_user and intern_user.telegram_id and intern_user.notify_tasks:
        await send_telegram_message(
            intern_user.telegram_id,
            f"Ваш ответ на задание '{task_title}' {status_text}"
            + (f"\nКомментарий: {data.review_comment}" if data.review_comment else ""),
        )

    await db.refresh(sub)
    user_res = await db.execute(select(User.name).where(User.id == sub.user_id))
    name = user_res.scalar() or ""
    return SubmissionOut(
        id=sub.id, task_id=sub.task_id, user_id=sub.user_id, user_name=name,
        content=sub.content, file_url=sub.file_url, status=sub.status.value,
        review_comment=sub.review_comment, reviewer_id=sub.reviewer_id,
        created_at=sub.created_at, reviewed_at=sub.reviewed_at,
    )


# ===================== CODE EXECUTION =====================

@router.post("/code/run", response_model=CodeRunResult)
@limiter.limit("10/minute")
async def run_code(request: Request, data: CodeRunRequest, user: User = Depends(get_current_user)):
    """Выполнить код в песочнице (Python, JavaScript, Bash)"""
    lang = data.language.lower().strip()
    if lang not in ALLOWED_LANGUAGES:
        raise HTTPException(400, f"Язык '{lang}' не поддерживается. Доступные: {', '.join(ALLOWED_LANGUAGES.keys())}")

    lang_config = ALLOWED_LANGUAGES[lang]

    # HTML is returned as-is (no execution needed)
    if lang_config["cmd"] is None:
        return CodeRunResult(stdout=data.code, stderr="", exit_code=0)

    # Write code to a temp file and execute with timeout
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode='w', suffix=lang_config["ext"], delete=False, encoding='utf-8'
        ) as f:
            f.write(data.code)
            tmp_path = f.name

        cmd = lang_config["cmd"] + [tmp_path]
        timeout = lang_config["timeout"]

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, lambda: _execute_code(cmd, timeout))
        return result
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def _execute_code(cmd: list, timeout: int) -> CodeRunResult:
    """Execute code in a sandboxed subprocess"""
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={
                "PATH": os.environ.get("PATH", "/usr/bin:/usr/local/bin"),
                "HOME": "/tmp",
                "LANG": "en_US.UTF-8",
            },
            cwd="/tmp",
        )
        return CodeRunResult(
            stdout=proc.stdout[:10000] if proc.stdout else "",
            stderr=proc.stderr[:5000] if proc.stderr else "",
            exit_code=proc.returncode,
        )
    except subprocess.TimeoutExpired:
        return CodeRunResult(stdout="", stderr="Execution timed out", exit_code=124, timed_out=True)
    except Exception as e:
        return CodeRunResult(stdout="", stderr=str(e)[:2000], exit_code=1)


# ===================== COURSE ASSIGNMENTS =====================

@router.get("/interns", response_model=list[InternOut])
async def list_interns(db: AsyncSession = Depends(get_db), user: User = Depends(require_training_editor)):
    result = await db.execute(
        select(User).where(User.training_role == "intern").order_by(User.name)
    )
    return [InternOut(id=u.id, name=u.name, email=u.email, training_role=u.training_role) for u in result.scalars().all()]


@router.get("/courses/{course_id}/assignments", response_model=list[CourseAssignmentOut])
async def list_course_assignments(course_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(require_training_editor)):
    result = await db.execute(
        select(CourseAssignment).where(CourseAssignment.course_id == course_id).order_by(CourseAssignment.created_at)
    )
    assignments = result.scalars().all()
    out = []
    for a in assignments:
        u_res = await db.execute(select(User.name, User.email).where(User.id == a.user_id))
        u_row = u_res.first()
        assigner_res = await db.execute(select(User.name).where(User.id == a.assigned_by))
        assigner_name = assigner_res.scalar() or ""
        out.append(CourseAssignmentOut(
            id=a.id, course_id=a.course_id, user_id=a.user_id,
            user_name=u_row[0] if u_row else "", user_email=u_row[1] if u_row else "",
            assigned_by_name=assigner_name, created_at=a.created_at,
        ))
    return out


@router.post("/courses/{course_id}/assign", response_model=list[CourseAssignmentOut], status_code=201)
async def assign_course(course_id: uuid.UUID, data: CourseAssign, db: AsyncSession = Depends(get_db), user: User = Depends(require_training_editor)):
    course_res = await db.execute(select(TrainingCourse).where(TrainingCourse.id == course_id))
    course = course_res.scalar_one_or_none()
    if not course:
        raise HTTPException(404, "Курс не найден")

    created = []
    for uid in data.user_ids:
        existing = await db.execute(
            select(CourseAssignment).where(CourseAssignment.course_id == course_id, CourseAssignment.user_id == uid)
        )
        if existing.scalar_one_or_none():
            continue
        a = CourseAssignment(course_id=course_id, user_id=uid, assigned_by=user.id)
        db.add(a)
        created.append(a)

        db.add(Notification(
            user_id=uid,
            title="Назначен новый курс",
            message=f"Вам назначен курс '{course.title}'",
            type="training",
            link="/training",
        ))

    await db.commit()

    from app.services.telegram import send_telegram_message
    for a in created:
        intern_res = await db.execute(select(User).where(User.id == a.user_id))
        intern_user = intern_res.scalar_one_or_none()
        if intern_user and intern_user.telegram_id and intern_user.notify_tasks:
            await send_telegram_message(
                intern_user.telegram_id,
                f"Назначен новый курс\nВам назначен курс '{course.title}'",
            )

    return await list_course_assignments(course_id, db, user)


@router.delete("/courses/{course_id}/assign/{user_id}")
async def unassign_course(course_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(require_training_editor)):
    result = await db.execute(
        select(CourseAssignment).where(CourseAssignment.course_id == course_id, CourseAssignment.user_id == user_id)
    )
    assignment = result.scalar_one_or_none()
    if not assignment:
        raise HTTPException(404, "Назначение не найдено")
    await db.delete(assignment)
    await db.commit()
    return {"message": "Назначение снято"}
