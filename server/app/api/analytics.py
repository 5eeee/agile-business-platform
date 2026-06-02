# API маршруты для аналитики
import json
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.task import Task
from app.models.project import Project, ProjectMember
from app.models.iteration import Iteration
from app.models.analytics import AnalyticsReport
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/analytics", tags=["Аналитика"])


async def _get_cached(key: str, ttl: int = 30):
    """Get value from Redis cache, returns (hit, data)"""
    try:
        from app.services.redis import get_redis
        r = await get_redis()
        cached = await r.get(key)
        if cached:
            return True, json.loads(cached)
    except Exception:
        pass
    return False, None


async def _set_cached(key: str, data: dict, ttl: int = 30):
    """Set value in Redis cache"""
    try:
        from app.services.redis import get_redis
        r = await get_redis()
        await r.setex(key, ttl, json.dumps(data, default=str))
    except Exception:
        pass


@router.get("/dashboard")
async def dashboard_analytics(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Метрики для дашборда: задачи за неделю, активные задачи, прогресс"""
    # Per-user cache key (includes personal stats)
    cache_key = f"analytics:dashboard:{user.id}"
    hit, cached = await _get_cached(cache_key, 30)
    if hit:
        return cached

    week_ago = datetime.utcnow() - timedelta(days=7)

    # Задачи завершённые за неделю
    completed_result = await db.execute(
        select(func.count(Task.id)).where(
            Task.status == "Доставлено клиенту",
            Task.updated_at >= week_ago,
        )
    )
    completed_week = completed_result.scalar() or 0

    # Всего активных задач
    active_result = await db.execute(
        select(func.count(Task.id)).where(
            Task.status.in_(["Готово к запуску", "Создаёт ценность"])
        )
    )
    active_tasks = active_result.scalar() or 0

    # Всего задач
    total_result = await db.execute(select(func.count(Task.id)))
    total_tasks = total_result.scalar() or 0

    # Проекты пользователя
    projects_result = await db.execute(
        select(func.count(ProjectMember.id)).where(ProjectMember.user_id == user.id)
    )
    user_projects = projects_result.scalar() or 0

    # Задачи пользователя (назначенные)
    my_tasks_result = await db.execute(
        select(func.count(Task.id)).where(Task.assignee_id == user.id)
    )
    my_tasks = my_tasks_result.scalar() or 0

    # Мои завершённые за неделю
    my_completed_result = await db.execute(
        select(func.count(Task.id)).where(
            Task.assignee_id == user.id,
            Task.status == "Доставлено клиенту",
            Task.updated_at >= week_ago,
        )
    )
    my_completed = my_completed_result.scalar() or 0

    result = {
        "completed_week": completed_week,
        "active_tasks": active_tasks,
        "total_tasks": total_tasks,
        "user_projects": user_projects,
        "my_tasks": my_tasks,
        "my_completed_week": my_completed,
        "progress_percent": round(completed_week / max(total_tasks, 1) * 100, 1),
    }
    await _set_cached(cache_key, result, 30)
    return result


@router.get("/tips")
async def get_tips(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Советы на основе текущих метрик"""
    week_ago = datetime.utcnow() - timedelta(days=7)

    # Незавершённые задачи пользователя
    overdue_result = await db.execute(
        select(func.count(Task.id)).where(
            Task.assignee_id == user.id,
            Task.status != "Доставлено клиенту",
            Task.deadline != None,
            Task.deadline < datetime.utcnow(),
        )
    )
    overdue = overdue_result.scalar() or 0

    my_active_result = await db.execute(
        select(func.count(Task.id)).where(
            Task.assignee_id == user.id,
            Task.status.in_(["Готово к запуску", "Создаёт ценность"]),
        )
    )
    my_active = my_active_result.scalar() or 0

    tips = []
    if overdue > 0:
        tips.append(f"⚠️ У вас {overdue} просроченных задач. Обновите статус или сроки.")
    if my_active > 5:
        tips.append("📋 Много активных задач. Сфокусируйтесь на 2-3 приоритетных.")
    if my_active == 0:
        tips.append("✅ Нет активных задач. Проверьте бэклог проектов.")

    # Общие советы
    if not tips:
        tips = [
            "💡 Регулярно обновляйте статус задач для прозрачности команды.",
            "🗓 Планируйте задачи на неделю вперёд — это повышает продуктивность.",
            "🤝 Участвуйте в ретроспективах — это улучшает процессы.",
        ]

    return {"tips": tips}


@router.get("/budget")
async def get_budget(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Виджет бюджета — настраивается администратором (упрощённая реализация)"""
    return {
        "total": 0,
        "spent": 0,
        "items": [],
    }


@router.get("/reports")
async def list_reports(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Список аналитических отчётов"""
    result = await db.execute(
        select(AnalyticsReport).order_by(AnalyticsReport.created_at.desc()).limit(20)
    )
    reports = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "content": r.content,
            "report_data": json.loads(r.report_data) if r.report_data else None,
            "created_at": str(r.created_at),
        }
        for r in reports
    ]


@router.post("/reports/generate")
async def generate_report(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Генерация аналитического отчёта"""
    week_ago = datetime.utcnow() - timedelta(days=7)

    # Собираем метрики
    total_result = await db.execute(select(func.count(Task.id)))
    total = total_result.scalar() or 0

    completed_result = await db.execute(
        select(func.count(Task.id)).where(
            Task.status == "Доставлено клиенту",
            Task.updated_at >= week_ago,
        )
    )
    completed = completed_result.scalar() or 0

    active_result = await db.execute(
        select(func.count(Task.id)).where(Task.status.in_(["Готово к запуску", "Создаёт ценность"]))
    )
    active = active_result.scalar() or 0

    users_result = await db.execute(select(func.count(User.id)).where(User.status == "active"))
    users_count = users_result.scalar() or 0

    projects_result = await db.execute(select(func.count(Project.id)).where(Project.is_deleted == False))
    projects_count = projects_result.scalar() or 0

    data = {
        "total_tasks": total,
        "completed_week": completed,
        "active_tasks": active,
        "users_count": users_count,
        "projects_count": projects_count,
        "generated_at": datetime.utcnow().isoformat(),
    }

    content = (
        f"Еженедельный отчёт ({datetime.utcnow().strftime('%d.%m.%Y')})\n"
        f"Пользователей: {users_count}\n"
        f"Проектов: {projects_count}\n"
        f"Всего задач: {total}\n"
        f"Завершено за неделю: {completed}\n"
        f"Активных задач: {active}\n"
    )

    report = AnalyticsReport(content=content, report_data=json.dumps(data))
    db.add(report)
    await db.commit()
    await db.refresh(report)

    return {
        "id": str(report.id),
        "content": content,
        "report_data": data,
    }
