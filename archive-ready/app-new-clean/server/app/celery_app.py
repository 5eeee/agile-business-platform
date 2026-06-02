"""Celery application for background tasks"""
import os
from celery import Celery
from celery.schedules import crontab

_redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
_base = _redis_url.rsplit("/", 1)[0]  # strip db number

celery = Celery(
    "agile",
    broker=f"{_base}/1",
    backend=f"{_base}/2",
)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "daily-analytics": {
            "task": "app.tasks.analytics.generate_daily_report",
            "schedule": crontab(hour=2, minute=0),
        },
        "check-event-reminders": {
            "task": "app.tasks.reminders.check_event_reminders",
            "schedule": crontab(minute="*/5"),
        },
        "check-task-deadlines": {
            "task": "app.tasks.reminders.check_task_deadlines",
            "schedule": crontab(hour=9, minute=0),
        },
        "auto-archive-iterations": {
            "task": "app.tasks.reminders.auto_archive_completed_iterations",
            "schedule": crontab(hour=3, minute=0),
        },
        "check-system-reminders": {
            "task": "app.tasks.reminders.check_system_reminders",
            "schedule": crontab(hour=8, minute=0),
        },
        "auto-collect-chat-files": {
            "task": "app.tasks.reminders.auto_collect_chat_files",
            "schedule": crontab(hour=4, minute=0),
        },
    },
)

celery.autodiscover_tasks(["app.tasks"])
