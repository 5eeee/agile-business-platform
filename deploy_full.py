"""
Альтернативный деплой на shared hosting (reg.ru) с MySQL.
Используйте deploy.ps1 для основного деплоя на VPS с PostgreSQL.

Credentials из env: DEPLOY_HOST, DEPLOY_SSH_USER, DEPLOY_SSH_PASSWORD
"""
import paramiko
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

HOST = os.environ.get("DEPLOY_HOST", "31.31.196.165")
USER = os.environ.get("DEPLOY_SSH_USER", "u3441682")
PASSWORD = os.environ.get("DEPLOY_SSH_PASSWORD", "")
REMOTE_BASE = "/var/www/u3441682/data/www"
SITE_DIR = "app.agile-business-pro.com"
REMOTE_SITE = f"{REMOTE_BASE}/{SITE_DIR}"
EXISTING_SITE = f"{REMOTE_BASE}/agile.workspace"

LOCAL_SERVER = os.path.join(os.path.dirname(__file__), "server")
LOCAL_DIST = os.path.join(os.path.dirname(__file__), "client-new", "dist")


def ssh_exec(client, cmd, timeout=120):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    return out.strip(), err.strip(), code


def sftp_mkdir_p(sftp, remote_dir):
    """Recursive mkdir on remote"""
    dirs_to_create = []
    d = remote_dir
    while d and d != "/":
        try:
            sftp.stat(d)
            break
        except FileNotFoundError:
            dirs_to_create.append(d)
            d = os.path.dirname(d)
    for d in reversed(dirs_to_create):
        try:
            sftp.mkdir(d)
        except Exception:
            pass


def upload_dir(sftp, local_dir, remote_dir, skip_dirs=None):
    """Recursively upload a directory"""
    skip_dirs = skip_dirs or set()
    sftp_mkdir_p(sftp, remote_dir)
    for item in os.listdir(local_dir):
        local_path = os.path.join(local_dir, item)
        remote_path = f"{remote_dir}/{item}"
        if item in skip_dirs or item.startswith('.') or item == '__pycache__' or item.endswith('.pyc'):
            continue
        if os.path.isdir(local_path):
            upload_dir(sftp, local_path, remote_path, skip_dirs)
        else:
            if os.path.getsize(local_path) > 50 * 1024 * 1024:
                continue
            sftp.put(local_path, remote_path)


def upload_text(sftp, remote_path, content):
    """Upload text content to a remote file"""
    import io
    f = io.BytesIO(content.encode("utf-8"))
    sftp.putfo(f, remote_path)


def main():
    if not PASSWORD:
        print("Задайте DEPLOY_SSH_PASSWORD в окружении")
        sys.exit(1)
    print(f"Connecting to {USER}@{HOST}...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, port=22, username=USER, password=PASSWORD, timeout=15)
    sftp = client.open_sftp()
    print("Connected!\n")

    # === 1. Create site directory structure ===
    print("=== 1. Creating site directory ===")
    ssh_exec(client, f"mkdir -p {REMOTE_SITE}/app/api {REMOTE_SITE}/app/models {REMOTE_SITE}/app/schemas {REMOTE_SITE}/app/middleware {REMOTE_SITE}/app/services {REMOTE_SITE}/public {REMOTE_SITE}/tmp")

    # === 2. Copy venv from existing deployment ===
    print("=== 2. Setting up venv ===")
    out, err, code = ssh_exec(client, f"test -d {REMOTE_SITE}/venv && echo EXISTS || echo MISSING")
    if "MISSING" in out:
        print("   Copying venv from existing deployment...")
        ssh_exec(client, f"cp -a {EXISTING_SITE}/venv {REMOTE_SITE}/venv", timeout=120)
        print("   [OK] venv copied")
    else:
        print("   [OK] venv already exists")

    # === 3. Upload backend code ===
    print("=== 3. Uploading backend code ===")
    server_app_dir = os.path.join(LOCAL_SERVER, "app")
    
    dirs_to_upload = ["api", "models", "schemas", "middleware"]
    for d in dirs_to_upload:
        local_d = os.path.join(server_app_dir, d)
        if os.path.isdir(local_d):
            print(f"   Uploading app/{d}/...")
            upload_dir(sftp, local_d, f"{REMOTE_SITE}/app/{d}")

    root_py_files = [f for f in os.listdir(server_app_dir) if f.endswith('.py') and os.path.isfile(os.path.join(server_app_dir, f))]
    for f in root_py_files:
        sftp.put(os.path.join(server_app_dir, f), f"{REMOTE_SITE}/app/{f}")
        print(f"   Uploaded app/{f}")

    # === 4. Create hosting-specific files ===
    print("=== 4. Creating hosting-specific files ===")
    
    # config_hosting.py
    config_hosting = '''import os
from pydantic_settings import BaseSettings
from typing import Optional, List

class Settings(BaseSettings):
    APP_NAME: str = "Agile Business"
    DEBUG: bool = False
    SECRET_KEY: str = os.getenv("SECRET_KEY", "agile-business-secret-key-production-2026")
    SQL_ECHO: bool = False
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 5
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    JWT_ALGORITHM: str = "HS256"
    DATABASE_URL: str = "mysql+aiomysql://u3441682_default:8ALbq3QXdiax8bC4@localhost/u3441682_default?charset=utf8mb4"
    DATABASE_URL_SYNC: str = "mysql+pymysql://u3441682_default:8ALbq3QXdiax8bC4@localhost/u3441682_default?charset=utf8mb4"
    REDIS_URL: str = ""
    S3_ENDPOINT: str = ""
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_BUCKET: str = ""
    S3_REGION: str = ""
    ELASTICSEARCH_URL: str = ""
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_ADMIN_CHAT_ID: Optional[str] = None
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@agile.workspace"
    MAX_FILE_SIZE: int = 100 * 1024 * 1024
    LOGIN_MAX_ATTEMPTS: int = 5
    LOGIN_LOCKOUT_MINUTES: int = 15
    ADMIN_SEED_EMAIL: str = "admin@agile.com"
    ADMIN_SEED_PASSWORD: str = "admin123"
    SENTRY_DSN: str = ""
    CORS_ORIGINS: List[str] = ["https://app.agile-business-pro.com", "http://app.agile-business-pro.com"]

settings = Settings()
'''
    upload_text(sftp, f"{REMOTE_SITE}/app/config_hosting.py", config_hosting)
    print("   [OK] config_hosting.py")

    # main_hosting.py (with training + gamification)
    # MySQL: patch UUID before models load (models use sqlalchemy.dialects.postgresql.UUID)
    main_hosting = '''import os, sys, uuid as _uuid_mod
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("AGILE_HOSTING", "1")

# MySQL compat: replace PostgreSQL UUID with String(36)-based type
import sqlalchemy.dialects.postgresql as _pg
from sqlalchemy import String, TypeDecorator
class _MySQLUUID(TypeDecorator):
    impl = String(36)
    cache_ok = True
    def process_bind_param(self, v, d): return str(v) if v else v
    def process_result_value(self, v, d): return _uuid_mod.UUID(v) if v else v
_pg.UUID = lambda as_uuid=True: _MySQLUUID()

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.config_hosting import settings
import app.config
app.config.settings = settings

from app.database import get_db, async_session, engine, Base

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
from app.models.user import User, UserRole, UserStatus
from app.api.auth import hash_password
from app.api import auth, users, admin, projects, iterations, tasks, chat, events, retrospectives, notifications
from app.api import places, music, documents, analytics, export
from app.api import training as training_api
from app.api import gamification as gamification_api
from app.middleware.csrf import CSRFMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    async with async_session() as db:
        result = await db.execute(select(User).where(User.email == "admin@agile.com"))
        if not result.scalar_one_or_none():
            admin_user = User(
                name="\\u0410\\u0434\\u043c\\u0438\\u043d\\u0438\\u0441\\u0442\\u0440\\u0430\\u0442\\u043e\\u0440",
                email="admin@agile.com",
                password_hash=hash_password("admin123"),
                role=UserRole.ADMIN,
                status=UserStatus.ACTIVE,
                email_confirmed=True,
            )
            db.add(admin_user)
            await db.commit()
    yield


app = FastAPI(title="Agile Business API", version="1.0.0", lifespan=lifespan, redirect_slashes=False)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    return response

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
app.include_router(gamification_api.router, prefix="/api")

@app.get("/api/health")
async def health():
    from datetime import datetime
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}
'''
    upload_text(sftp, f"{REMOTE_SITE}/app/main_hosting.py", main_hosting)
    print("   [OK] main_hosting.py")

    # rate_limit.py (stub for hosting without Redis)
    rate_limit = '''from slowapi import Limiter
from slowapi.util import get_remote_address
limiter = Limiter(key_func=get_remote_address, enabled=False)
'''
    upload_text(sftp, f"{REMOTE_SITE}/app/rate_limit.py", rate_limit)
    print("   [OK] rate_limit.py")

    # services/__init__.py
    upload_text(sftp, f"{REMOTE_SITE}/app/services/__init__.py", "")
    
    # services/telegram.py (stub)
    telegram_stub = '''async def send_telegram_message(chat_id, text):
    pass

async def notify_new_message(chat_id, user_name, iteration_name):
    pass
'''
    upload_text(sftp, f"{REMOTE_SITE}/app/services/telegram.py", telegram_stub)
    print("   [OK] services/telegram.py (stub)")

    # services/s3.py (stub - saves to local dir)
    s3_stub = '''import os
import uuid
import shutil

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

def ensure_bucket():
    pass

async def upload_file_to_s3(file, prefix="uploads"):
    ext = os.path.splitext(file.filename)[1] if file.filename else ""
    fname = f"{uuid.uuid4().hex}{ext}"
    dest = os.path.join(UPLOAD_DIR, fname)
    content = await file.read()
    with open(dest, "wb") as f:
        f.write(content)
    return f"/uploads/{fname}"
'''
    upload_text(sftp, f"{REMOTE_SITE}/app/services/s3.py", s3_stub)
    print("   [OK] services/s3.py (local storage)")

    # services/redis.py (stub)
    redis_stub = '''class FakeRedis:
    async def get(self, key): return None
    async def set(self, key, value, ex=None): pass
    async def setex(self, key, time, value): pass
    async def delete(self, key): pass
    async def ping(self): return True

_fake = FakeRedis()
async def get_redis(): return _fake
'''
    upload_text(sftp, f"{REMOTE_SITE}/app/services/redis.py", redis_stub)
    print("   [OK] services/redis.py (stub)")

    # services/search.py (stub)
    search_stub = '''async def ensure_index(): pass
async def close_es(): pass
async def index_message(*args, **kwargs): pass
async def search_messages(*args, **kwargs): return []
'''
    upload_text(sftp, f"{REMOTE_SITE}/app/services/search.py", search_stub)
    print("   [OK] services/search.py (stub)")

    # MySQL compat model (handles UUID differences)
    compat = '''import uuid
from sqlalchemy import String, TypeDecorator

class UUIDType(TypeDecorator):
    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            return str(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            return uuid.UUID(value)
        return value
'''
    upload_text(sftp, f"{REMOTE_SITE}/app/models/compat.py", compat)
    print("   [OK] models/compat.py")

    # passenger_wsgi.py
    passenger_wsgi = f'''import sys
import os

app_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, app_dir)

os.environ['AGILE_HOSTING'] = '1'

from app.config_hosting import settings
import app.config
app.config.settings = settings

from app.main_hosting import app as fastapi_app
from a2wsgi import ASGIMiddleware

application = ASGIMiddleware(fastapi_app)
'''
    upload_text(sftp, f"{REMOTE_SITE}/passenger_wsgi.py", passenger_wsgi)
    print("   [OK] passenger_wsgi.py")

    # .htaccess
    htaccess = f'''PassengerEnabled On
PassengerAppRoot {REMOTE_SITE}
PassengerAppType wsgi
PassengerStartupFile passenger_wsgi.py
PassengerPython {REMOTE_SITE}/venv/bin/python3.12
PassengerFriendlyErrorPages on

RewriteEngine On

# Serve uploaded files
RewriteCond %{{DOCUMENT_ROOT}}/uploads%{{REQUEST_URI}} -f
RewriteRule ^/uploads/(.+)$ /uploads/$1 [L]

# Serve static assets from public/
RewriteCond %{{DOCUMENT_ROOT}}/public%{{REQUEST_URI}} -f
RewriteRule ^(.+)$ /public/$1 [L]

# SPA routing: non-API, non-file -> index.html
RewriteCond %{{REQUEST_URI}} !^/api/
RewriteCond %{{REQUEST_URI}} !^/public/
RewriteCond %{{REQUEST_URI}} !^/uploads/
RewriteCond %{{DOCUMENT_ROOT}}/public%{{REQUEST_URI}} !-f
RewriteCond %{{REQUEST_URI}} !^/passenger
RewriteRule ^(.*)$ /public/index.html [L]

<IfModule mod_headers.c>
    Header always set X-Content-Type-Options nosniff
    Header always set X-Frame-Options SAMEORIGIN
</IfModule>

<IfModule mod_deflate.c>
    AddOutputFilterByType DEFLATE text/html text/css application/javascript application/json
</IfModule>
'''
    upload_text(sftp, f"{REMOTE_SITE}/.htaccess", htaccess)
    print("   [OK] .htaccess")

    # === 5. Upload frontend build ===
    print("=== 5. Uploading frontend build ===")
    if os.path.isdir(LOCAL_DIST):
        upload_dir(sftp, LOCAL_DIST, f"{REMOTE_SITE}/public")
        print(f"   [OK] Frontend uploaded to public/")
    else:
        print("   [WARN] No dist/ found, skipping frontend")

    # === 6. Install additional dependencies ===
    print("=== 6. Installing additional dependencies ===")
    deps = "aiomysql slowapi DOMPurify python-multipart aiofiles reportlab a2wsgi"
    out, err, code = ssh_exec(client, f"{REMOTE_SITE}/venv/bin/pip install {deps} 2>&1 | tail -5", timeout=120)
    print(f"   {out}")
    if err:
        print(f"   stderr: {err}")

    # === 7. Create uploads directory ===
    print("=== 7. Setting up uploads directory ===")
    ssh_exec(client, f"mkdir -p {REMOTE_SITE}/uploads && chmod 755 {REMOTE_SITE}/uploads")

    # === 8. Create tmp directory for Passenger restart ===
    print("=== 8. Restarting Passenger ===")
    ssh_exec(client, f"mkdir -p {REMOTE_SITE}/tmp && touch {REMOTE_SITE}/tmp/restart.txt")
    print("   [OK] Passenger restart triggered")

    # === 9. Verify ===
    print("\n=== 9. Verifying deployment ===")
    out, err, code = ssh_exec(client, f"ls -la {REMOTE_SITE}/public/index.html {REMOTE_SITE}/passenger_wsgi.py {REMOTE_SITE}/.htaccess {REMOTE_SITE}/app/main_hosting.py 2>&1")
    print(f"   {out}")

    out, err, code = ssh_exec(client, f"cd {REMOTE_SITE} && {REMOTE_SITE}/venv/bin/python3.12 -c 'from app.main_hosting import app; print(\"FastAPI app loaded OK\")' 2>&1")
    print(f"   Import test: {out}")
    if err:
        print(f"   Import errors: {err[:500]}")

    sftp.close()
    client.close()

    print("\n" + "=" * 50)
    print("DEPLOYMENT COMPLETE!")
    print("=" * 50)
    print(f"Site: https://app.agile-business-pro.com")
    print(f"Login: admin@agile.com / admin123")
    print("=" * 50)


if __name__ == "__main__":
    main()
