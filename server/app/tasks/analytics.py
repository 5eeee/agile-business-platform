"""Background analytics tasks"""
import json
from datetime import datetime, timedelta
from sqlalchemy import select, func, create_engine
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


@celery.task(name="app.tasks.analytics.generate_daily_report")
def generate_daily_report():
    """Generate daily analytics report (runs synchronously via Celery)"""
    from app.models.task import Task
    from app.models.user import User
    from app.models.project import Project
    from app.models.analytics import AnalyticsReport

    with Session(_get_engine()) as db:
        week_ago = datetime.utcnow() - timedelta(days=7)

        total = db.query(func.count(Task.id)).scalar() or 0
        completed = db.query(func.count(Task.id)).filter(
            Task.status == "Доставлено клиенту",
            Task.updated_at >= week_ago,
        ).scalar() or 0
        active = db.query(func.count(Task.id)).filter(
            Task.status.in_(["Готово к запуску", "Создаёт ценность"])
        ).scalar() or 0
        users_count = db.query(func.count(User.id)).filter(User.status == "active").scalar() or 0
        projects_count = db.query(func.count(Project.id)).filter(Project.is_deleted == False).scalar() or 0

        # Per-user workload analysis
        overloaded = []
        user_tasks = db.query(
            User.name, func.count(Task.id).label("cnt")
        ).join(Task, Task.assignee_id == User.id).filter(
            Task.status.in_(["Готово к запуску", "Создаёт ценность"])
        ).group_by(User.name).all()

        avg_tasks = sum(r.cnt for r in user_tasks) / max(len(user_tasks), 1) if user_tasks else 0
        for row in user_tasks:
            if row.cnt > avg_tasks * 1.4:
                overloaded.append(f"{row.name} имеет {row.cnt} активных задач — это на {int((row.cnt / max(avg_tasks, 1) - 1) * 100)}% больше среднего. Рекомендуется перераспределить нагрузку")

        data = {
            "total_tasks": total,
            "completed_week": completed,
            "active_tasks": active,
            "users_count": users_count,
            "projects_count": projects_count,
            "overloaded_users": overloaded,
            "generated_at": datetime.utcnow().isoformat(),
        }

        content = (
            f"Ежедневный отчёт ({datetime.utcnow().strftime('%d.%m.%Y')})\n"
            f"Пользователей: {users_count}\n"
            f"Проектов: {projects_count}\n"
            f"Всего задач: {total}\n"
            f"Завершено за неделю: {completed}\n"
            f"Активных задач: {active}\n"
        )
        if overloaded:
            content += "\nПерегруженные сотрудники:\n" + "\n".join(f"• {o}" for o in overloaded)

        report = AnalyticsReport(content=content, report_data=json.dumps(data))
        db.add(report)
        db.commit()

    return {"status": "ok", "generated_at": data["generated_at"]}
