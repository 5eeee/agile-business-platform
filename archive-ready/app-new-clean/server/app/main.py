# Точка входа FastAPI
import json
import re
import uuid
import logging
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.database import init_db, get_db, async_session
from app.models.user import User, UserRole, UserStatus
from app.models.project import ProjectMember
from app.models.iteration import Iteration
from app.models.chat import ChatMessage
from app.models.notification import Notification
from app.api.auth import hash_password
from app.api import auth, users, admin, projects, iterations, tasks, chat, events, retrospectives, notifications
from app.api import places, music, documents, analytics, export
from app.api import training as training_api
from app.api import telegram as telegram_api
from app.api import gamification as gamification_api
from app.websocket import manager
from app.middleware.auth import decode_token
from app.middleware.csrf import CSRFMiddleware
from app.services.s3 import ensure_bucket
from app.services.search import ensure_index
from app.services.telegram import notify_new_message

# --- Structured JSON Logging ---
from pythonjsonlogger import jsonlogger

log_handler = logging.StreamHandler(sys.stdout)
formatter = jsonlogger.JsonFormatter(
    fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log_handler.setFormatter(formatter)
logging.basicConfig(level=logging.INFO, handlers=[log_handler])
logger = logging.getLogger("agile")

# --- Sentry ---
if settings.SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        integrations=[FastApiIntegration(), SqlalchemyIntegration()],
        traces_sample_rate=0.2,
        environment="production" if not settings.DEBUG else "development",
    )
    logger.info("Sentry initialized")

# --- Rate Limiter ---
from app.rate_limit import limiter


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Инициализация БД при старте
    try:
        await init_db()
    except Exception as e:
        logger.error(
            "PostgreSQL недоступен, API не запущен: %s",
            e,
            exc_info=settings.DEBUG,
        )
        logger.error(
            "Проверьте: 1) Служба PostgreSQL запущена (Windows: services.msc → postgresql). "
            "2) В server/.env корректный DATABASE_URL (хост, порт 5432, пользователь, пароль, имя БД). "
            "3) База и пользователь созданы — см. README.md (раздел «PostgreSQL»). "
            "Redis опционален для лимитов/чёрного списка токенов; без него часть функций ослаблена."
        )
        raise
    # S3: создаём бакет и ставим публичную политику чтения
    try:
        ensure_bucket()
    except Exception as e:
        logger.warning("MinIO/S3 unavailable, file uploads will not work: %s", e)
    # Elasticsearch: создаём индекс для поиска по чату
    try:
        await ensure_index()
    except Exception as e:
        logger.warning("Elasticsearch unavailable, chat search will not work: %s", e)
    # Создание администратора (только если ADMIN_SEED_EMAIL задан)
    if settings.ADMIN_SEED_EMAIL and settings.ADMIN_SEED_PASSWORD:
        seed_email = settings.ADMIN_SEED_EMAIL.strip().lower()
        async with async_session() as db:
            result = await db.execute(select(User).where(func.lower(User.email) == seed_email))
            if not result.scalar_one_or_none():
                admin_user = User(
                    name="Администратор",
                    email=seed_email,
                    password_hash=hash_password(settings.ADMIN_SEED_PASSWORD),
                    role=UserRole.ADMIN,
                    status=UserStatus.ACTIVE,
                    email_confirmed=True,
                )
                db.add(admin_user)
                await db.commit()
                logger.info("Admin account seeded: %s", settings.ADMIN_SEED_EMAIL)
    yield
    # Shutdown: close Elasticsearch client
    from app.services.search import close_es
    await close_es()
    logger.info("Application shutdown complete")


app = FastAPI(
    title="Agile Business API",
    description="Платформа для управления проектами и командной работой",
    version="1.0.0",
    lifespan=lifespan,
    redirect_slashes=False,
)

# Rate limiter
app.state.limiter = limiter


async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Слишком много запросов. Подождите минуту."},
    )


app.add_exception_handler(RateLimitExceeded, rate_limit_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token", "Accept", "Origin"],
)


# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Cache-Control"] = "no-store"
    if not settings.DEBUG:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

# CSRF-защита (только в production)
if not settings.DEBUG:
    app.add_middleware(
        CSRFMiddleware,
        allowed_origins=settings.CORS_ORIGINS,
    )

# Подключение роутеров
app.include_router(auth.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(projects.router, prefix="/api")
app.include_router(iterations.router, prefix="/api")
app.include_router(tasks.router, prefix="/api")
app.include_router(tasks.backlog_router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(events.router, prefix="/api")
app.include_router(retrospectives.router, prefix="/api")
app.include_router(notifications.router, prefix="/api")
app.include_router(places.router, prefix="/api")
app.include_router(music.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(export.router, prefix="/api")
app.include_router(training_api.router, prefix="/api")
app.include_router(telegram_api.router, prefix="/api")
app.include_router(gamification_api.router, prefix="/api")


# WebSocket для чата
@app.websocket("/ws/chat/{iteration_id}")
async def ws_chat(websocket: WebSocket, iteration_id: str):
    cookie_token = (getattr(websocket, "cookies", {}) or {}).get("access_token")
    if not cookie_token:
        try:
            from http.cookies import SimpleCookie
            cookie_header = websocket.headers.get("cookie")
            if cookie_header:
                c = SimpleCookie()
                c.load(cookie_header)
                morsel = c.get("access_token")
                cookie_token = morsel.value if morsel else None
        except Exception:
            cookie_token = None
    token = websocket.query_params.get("token") or cookie_token
    if not token:
        await websocket.close(code=4001)
        return
    
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            await websocket.close(code=4001)
            return
        user_id = payload.get("sub")
    except Exception:
        await websocket.close(code=4001)
        return
    
    # Verify project membership via iteration
    async with async_session() as db:
        iter_result = await db.execute(select(Iteration).where(Iteration.id == uuid.UUID(iteration_id)))
        iteration = iter_result.scalar_one_or_none()
        if not iteration:
            await websocket.close(code=4002)
            return
        user_result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
        ws_user = user_result.scalar_one_or_none()
        if not ws_user:
            await websocket.close(code=4001)
            return
        if ws_user.role != UserRole.ADMIN:
            member_result = await db.execute(
                select(ProjectMember).where(ProjectMember.project_id == iteration.project_id, ProjectMember.user_id == ws_user.id)
            )
            if not member_result.scalar_one_or_none():
                await websocket.close(code=4003)
                return
        # Cache user info for the lifetime of this connection
        cached_user_name = ws_user.name
        cached_user_avatar = ws_user.avatar_url
    
    await manager.connect(websocket, iteration_id, user_id)
    
    try:
        while True:
            data = await websocket.receive_text()
            if len(data) > 10000:
                continue
            msg_data = json.loads(data)
            
            # Typing indicator — use cached name, no DB query
            if msg_data.get("type") == "typing":
                await manager.broadcast_to_iteration(iteration_id, {
                    "type": "typing",
                    "user_id": user_id,
                    "user_name": cached_user_name,
                }, exclude_ws=websocket)
                continue
            
            # Сохраняем в БД
            async with async_session() as db:
                reply_to_id = msg_data.get("reply_to_id")
                msg = ChatMessage(
                    iteration_id=uuid.UUID(iteration_id),
                    user_id=uuid.UUID(user_id),
                    content=msg_data.get("content", ""),
                    reply_to_id=uuid.UUID(reply_to_id) if reply_to_id else None,
                )
                db.add(msg)
                await db.commit()
                await db.refresh(msg)
                
                # @mentions → создать уведомления
                mentions = re.findall(r'@([\w\-]+(?:\s[\w\-]+)*)', msg.content)
                if mentions:
                    mentioned_users = []
                    for mention_name in mentions:
                        mentioned = await db.execute(select(User).where(User.name == mention_name))
                        mentioned_user = mentioned.scalar_one_or_none()
                        if mentioned_user and mentioned_user.id != uuid.UUID(user_id):
                            mentioned_users.append(mentioned_user)
                            notif = Notification(
                                user_id=mentioned_user.id,
                                title="Упоминание в чате",
                                message=f"{cached_user_name} упомянул вас: {msg.content[:100]}",
                                type="mention",
                            )
                            db.add(notif)
                    await db.commit()
                    for mentioned_user in mentioned_users:
                        await manager.send_to_user(str(mentioned_user.id), {
                            "type": "notification",
                            "title": "Упоминание в чате",
                            "message": f"{cached_user_name} упомянул вас",
                        })
                        if mentioned_user.telegram_id and mentioned_user.notify_messages:
                            iter_res = await db.execute(select(Iteration).where(Iteration.id == uuid.UUID(iteration_id)))
                            it = iter_res.scalar_one_or_none()
                            await notify_new_message(mentioned_user.telegram_id, cached_user_name, it.name if it else "чат")
                
                reply_to_content = None
                reply_to_user_name = None
                if msg.reply_to_id:
                    reply_res = await db.execute(select(ChatMessage).where(ChatMessage.id == msg.reply_to_id))
                    reply_msg = reply_res.scalar_one_or_none()
                    if reply_msg:
                        reply_to_content = reply_msg.content[:100] if reply_msg.content else None
                        reply_user_res = await db.execute(select(User).where(User.id == reply_msg.user_id))
                        reply_user = reply_user_res.scalar_one_or_none()
                        reply_to_user_name = reply_user.name if reply_user else None

                broadcast_data = {
                    "type": "message",
                    "id": str(msg.id),
                    "user_id": user_id,
                    "user_name": cached_user_name,
                    "user_avatar": cached_user_avatar,
                    "content": msg.content,
                    "reply_to_id": str(msg.reply_to_id) if msg.reply_to_id else None,
                    "reply_to_content": reply_to_content,
                    "reply_to_user_name": reply_to_user_name,
                    "created_at": str(msg.created_at),
                }
            
            await manager.broadcast_to_iteration(iteration_id, broadcast_data)
    except WebSocketDisconnect:
        manager.disconnect(websocket, iteration_id, user_id)
        # Обновляем онлайн-статус
        async with async_session() as db:
            result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
            user = result.scalar_one_or_none()
            if user:
                user.is_online = False
                user.last_seen = datetime.utcnow()
                await db.commit()


# WebSocket для онлайн-статуса
@app.websocket("/ws/status")
async def ws_status(websocket: WebSocket):
    cookie_token = (getattr(websocket, "cookies", {}) or {}).get("access_token")
    if not cookie_token:
        try:
            from http.cookies import SimpleCookie
            cookie_header = websocket.headers.get("cookie")
            if cookie_header:
                c = SimpleCookie()
                c.load(cookie_header)
                morsel = c.get("access_token")
                cookie_token = morsel.value if morsel else None
        except Exception:
            cookie_token = None
    token = websocket.query_params.get("token") or cookie_token
    if not token:
        await websocket.close(code=4001)
        return
    
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            await websocket.close(code=4001)
            return
        user_id = payload.get("sub")
    except Exception:
        await websocket.close(code=4001)
        return
    
    await websocket.accept()
    manager.user_connections[user_id] = websocket
    
    # Обновляем онлайн-статус
    async with async_session() as db:
        result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
        user = result.scalar_one_or_none()
        if user:
            user.is_online = True
            user.last_seen = datetime.utcnow()
            await db.commit()
    
    try:
        while True:
            data = await websocket.receive_text()
            # Handle listening_to broadcasts
            try:
                msg = json.loads(data)
                if msg.get("type") == "listening":
                    track = msg.get("track", "")
                    # Update DB
                    async with async_session() as db:
                        result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
                        u = result.scalar_one_or_none()
                        if u:
                            u.listening_to = track or None
                            await db.commit()
                    # Broadcast to all connected users
                    await manager.broadcast_all({
                        "type": "listening",
                        "user_id": user_id,
                        "track": track,
                    }, exclude_user=user_id)
            except (json.JSONDecodeError, KeyError):
                pass
    except WebSocketDisconnect:
        manager.user_connections.pop(user_id, None)
        async with async_session() as db:
            result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
            user = result.scalar_one_or_none()
            if user:
                user.is_online = False
                user.last_seen = datetime.utcnow()
                await db.commit()


@app.get("/api/health")
async def health():
    """Liveness probe — всегда OK если процесс жив"""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.get("/api/readiness")
async def readiness():
    """Readiness probe — БД обязательна, Redis опционален"""
    checks = {}
    try:
        async with async_session() as db:
            await db.execute(select(1))
        checks["db"] = "ok"
    except Exception as e:
        checks["db"] = str(e)
        return JSONResponse(
            status_code=503,
            content={"status": "not ready", "checks": checks},
        )

    # Redis используется не везде (например, blacklisting/rate limit имеют fallback).
    try:
        from app.services.redis import get_redis
        r = await get_redis()
        await r.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = str(e)

    status_code = 200
    return JSONResponse(
        status_code=status_code,
        content={"status": "ready", "checks": checks},
    )
