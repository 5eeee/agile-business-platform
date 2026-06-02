"""Background reminder tasks"""
from datetime import datetime, timedelta
import httpx
from sqlalchemy import select, create_engine
from sqlalchemy.orm import Session
from app.celery_app import celery
from app.config import settings

_sync_engine = None


def _get_engine():
    global _sync_engine
    if _sync_engine is None:
        sync_url = settings.DATABASE_URL.replace("+asyncpg", "")
        _sync_engine = create_engine(sync_url, pool_pre_ping=True)
    return _sync_engine


@celery.task(name="app.tasks.reminders.check_event_reminders")
def check_event_reminders():
    """Check upcoming events and send reminders via Telegram"""
    from app.models.event import Event, EventParticipant, EventReminder
    from app.models.user import User

    reminder_minutes = [1440, 360, 60, 45, 30, 15, 10, 5]
    now = datetime.utcnow()

    with Session(_get_engine()) as db:
        for mins in reminder_minutes:
            target_time = now + timedelta(minutes=mins)
            window_start = target_time - timedelta(minutes=3)
            window_end = target_time + timedelta(minutes=3)

            events = db.query(Event).filter(
                Event.event_date >= window_start,
                Event.event_date <= window_end,
            ).all()

            for event in events:
                existing = db.query(EventReminder).filter(
                    EventReminder.event_id == event.id,
                    EventReminder.minutes_before == mins,
                    EventReminder.sent == True,
                ).first()

                if existing:
                    continue

                participants = db.query(EventParticipant).filter(
                    EventParticipant.event_id == event.id,
                    EventParticipant.status == "attending",
                ).all()

                for p in participants:
                    user = db.query(User).filter(User.id == p.user_id).first()
                    if user and user.telegram_id and user.notify_events:
                        try:
                            _send_telegram(
                                settings.TELEGRAM_BOT_TOKEN,
                                user.telegram_id,
                                f"⏰ Напоминание: событие \"{event.title}\" через {_format_minutes(mins)}!\n📍 {event.location or ''}",
                            )
                        except Exception:
                            pass

                reminder = EventReminder(
                    event_id=event.id,
                    minutes_before=mins,
                    sent=True,
                )
                db.add(reminder)

        db.commit()

    return {"status": "ok", "checked_at": now.isoformat()}


@celery.task(name="app.tasks.reminders.check_task_deadlines")
def check_task_deadlines():
    """Notify users about upcoming/overdue task deadlines + in-app notifications"""
    from app.models.task import Task
    from app.models.user import User
    from app.models.notification import Notification

    now = datetime.utcnow()
    today = now.date()
    tomorrow = (now + timedelta(days=1)).date()

    with Session(_get_engine()) as db:
        tasks = db.query(Task).filter(
            Task.status.in_(["Готово к запуску", "Создаёт ценность"]),
            Task.deadline != None,
            Task.is_completed == False,
        ).all()

        for task in tasks:
            deadline_date = task.deadline if isinstance(task.deadline, type(today)) else datetime.fromisoformat(str(task.deadline)).date()

            # Overdue — deadline passed
            if deadline_date < today and task.assignee_id:
                user = db.query(User).filter(User.id == task.assignee_id).first()
                if not user:
                    continue
                # Check if we already notified today about this overdue task
                existing = db.query(Notification).filter(
                    Notification.user_id == user.id,
                    Notification.type == "deadline_overdue",
                    Notification.link == f"/project/{task.iteration_id}",
                    Notification.created_at >= datetime.combine(today, datetime.min.time()),
                ).first()
                if existing:
                    continue
                notif = Notification(
                    user_id=user.id,
                    title="Дедлайн просрочен!",
                    message=f'Задача "{task.title}" — дедлайн был {deadline_date.strftime("%d.%m.%Y")}',
                    type="deadline_overdue",
                    link=f"/project/{task.iteration_id}" if task.iteration_id else None,
                )
                db.add(notif)
                if user.telegram_id and user.notify_tasks:
                    try:
                        _send_telegram(settings.TELEGRAM_BOT_TOKEN, user.telegram_id,
                                       f"🔴 Дедлайн просрочен! Задача \"{task.title}\" — срок был {deadline_date.strftime('%d.%m.%Y')}")
                    except Exception:
                        pass

            # Due tomorrow
            elif deadline_date == tomorrow and task.assignee_id:
                user = db.query(User).filter(User.id == task.assignee_id).first()
                if not user:
                    continue
                existing = db.query(Notification).filter(
                    Notification.user_id == user.id,
                    Notification.type == "deadline_soon",
                    Notification.link == f"/project/{task.iteration_id}",
                    Notification.created_at >= datetime.combine(today, datetime.min.time()),
                ).first()
                if existing:
                    continue
                notif = Notification(
                    user_id=user.id,
                    title="Дедлайн завтра!",
                    message=f'Задача "{task.title}" — дедлайн завтра',
                    type="deadline_soon",
                    link=f"/project/{task.iteration_id}" if task.iteration_id else None,
                )
                db.add(notif)
                if user.telegram_id and user.notify_tasks:
                    try:
                        _send_telegram(settings.TELEGRAM_BOT_TOKEN, user.telegram_id,
                                       f"⏰ Дедлайн задачи \"{task.title}\" — завтра!")
                    except Exception:
                        pass

            # Due today
            elif deadline_date == today and task.assignee_id:
                user = db.query(User).filter(User.id == task.assignee_id).first()
                if not user:
                    continue
                existing = db.query(Notification).filter(
                    Notification.user_id == user.id,
                    Notification.type == "deadline_today",
                    Notification.created_at >= datetime.combine(today, datetime.min.time()),
                ).first()
                if existing:
                    continue
                notif = Notification(
                    user_id=user.id,
                    title="Дедлайн сегодня!",
                    message=f'Задача "{task.title}" — дедлайн сегодня',
                    type="deadline_today",
                    link=f"/project/{task.iteration_id}" if task.iteration_id else None,
                )
                db.add(notif)
                if user.telegram_id and user.notify_tasks:
                    try:
                        _send_telegram(settings.TELEGRAM_BOT_TOKEN, user.telegram_id,
                                       f"⚠️ Дедлайн задачи \"{task.title}\" — СЕГОДНЯ!")
                    except Exception:
                        pass

        db.commit()

    return {"status": "ok"}


def _send_telegram(token: str, chat_id: str, text: str):
    """Send a Telegram message synchronously"""
    import httpx
    httpx.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text},
        timeout=10,
    )


def _format_minutes(mins: int) -> str:
    if mins >= 1440:
        return f"{mins // 1440} д."
    if mins >= 60:
        return f"{mins // 60} ч."
    return f"{mins} мин."


@celery.task(name="app.tasks.reminders.auto_archive_completed_iterations")
def auto_archive_completed_iterations():
    """Auto-archive iterations completed more than 7 days ago (ТЗ 3.5.5)"""
    from app.models.iteration import Iteration, IterationStatus

    cutoff = datetime.utcnow() - timedelta(days=7)

    with Session(_get_engine()) as db:
        iterations = db.query(Iteration).filter(
            Iteration.status == IterationStatus.COMPLETED,
            Iteration.updated_at <= cutoff,
        ).all()
        for it in iterations:
            it.status = IterationStatus.ARCHIVED
        db.commit()

    return {"archived": len(iterations)}


@celery.task(name="app.tasks.reminders.check_system_reminders")
def check_system_reminders():
    """Send admin-configured system reminders (ТЗ 3.20.4)"""
    from app.models.notification import Notification, SystemReminder
    from app.models.user import User, UserStatus

    now = datetime.utcnow()

    with Session(_get_engine()) as db:
        reminders = db.query(SystemReminder).filter(
            SystemReminder.is_active == True,
            SystemReminder.send_date <= now,
            SystemReminder.sent == False,
        ).all()

        active_users = db.query(User).filter(User.status == UserStatus.ACTIVE).all()

        for rem in reminders:
            for user in active_users:
                notif = Notification(
                    user_id=user.id,
                    title=rem.title,
                    message=rem.message,
                    type="system",
                )
                db.add(notif)
                if user.telegram_id and user.notify_tasks:
                    try:
                        _send_telegram(settings.TELEGRAM_BOT_TOKEN, user.telegram_id, f"📢 {rem.title}: {rem.message}")
                    except Exception:
                        pass
            rem.sent = True
        db.commit()

    return {"sent": len(reminders)}


@celery.task(name="app.tasks.reminders.auto_collect_chat_files")
def auto_collect_chat_files():
    """Auto-collect chat files into Documents (ТЗ 3.11.2)"""
    from app.models.chat import ChatMessage
    from app.models.document import Document, DocumentVersion
    from app.models.iteration import Iteration, IterationStatus

    with Session(_get_engine()) as db:
        active_iterations = db.query(Iteration).filter(
            Iteration.status == IterationStatus.ACTIVE,
        ).all()

        total = 0
        for it in active_iterations:
            messages = db.query(ChatMessage).filter(
                ChatMessage.iteration_id == it.id,
                ChatMessage.file_url.isnot(None),
                ChatMessage.is_deleted == False,
            ).all()

            for msg in messages:
                existing = db.query(Document).filter(
                    Document.iteration_id == it.id,
                    Document.filename == (msg.file_name or f"chat_file_{msg.id}"),
                ).first()
                if existing:
                    continue
                doc = Document(
                    iteration_id=it.id,
                    filename=msg.file_name or f"chat_file_{msg.id}",
                    description="Автоматически собрано из чата",
                    uploader_id=msg.user_id,
                    current_version=1,
                )
                db.add(doc)
                db.flush()
                ver = DocumentVersion(
                    document_id=doc.id,
                    version=1,
                    file_url=msg.file_url,
                    file_size=msg.file_size,
                    mime_type=msg.file_mime,
                    uploader_id=msg.user_id,
                )
                db.add(ver)
                total += 1
        db.commit()

    return {"collected": total}
