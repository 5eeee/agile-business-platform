# Конфигурация приложения
import unicodedata
from pydantic_settings import BaseSettings
from pydantic import field_validator, ValidationInfo
from typing import Optional


class Settings(BaseSettings):
    # Приложение
    APP_NAME: str = "Agile Business"
    DEBUG: bool = False
    SECRET_KEY: str = ""
    DOMAIN: str = "localhost"
    COMPANY_TIMEZONE: str = "Europe/Moscow"
    
    # JWT
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    JWT_ALGORITHM: str = "HS256"
    
    # База данных
    DATABASE_URL: str = "postgresql+asyncpg://agile:agile_pass@localhost:5432/agile_db"
    DATABASE_URL_SYNC: str = ""
    SQL_ECHO: bool = False

    @field_validator("DATABASE_URL_SYNC", mode="before")
    @classmethod
    def _derive_sync_url(cls, v: str, info: ValidationInfo) -> str:
        if v:
            return v
        async_url = info.data.get("DATABASE_URL", "")
        if not async_url:
            return v
        sync_url = async_url.replace("postgresql+asyncpg://", "postgresql://")
        sync_url = sync_url.replace("sqlite+aiosqlite://", "sqlite://")
        return sync_url
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # S3-совместимое хранилище
    S3_ENDPOINT: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_BUCKET: str = "agile-files"
    S3_REGION: str = "us-east-1"
    # Отдельный секрет для AES-256-GCM. Если не задан, стабильно выводится из SECRET_KEY.
    FILE_ENCRYPTION_KEY: str = ""
    
    # Elasticsearch
    ELASTICSEARCH_URL: str = "http://localhost:9200"
    
    # Telegram Bot
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_ADMIN_CHAT_ID: Optional[str] = None
    
    # Email (SMTP)
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@agile.business"

    # Spotify API
    SPOTIFY_CLIENT_ID: str = ""
    SPOTIFY_CLIENT_SECRET: str = ""
    
    # Загрузка файлов
    MAX_FILE_SIZE: int = 100 * 1024 * 1024  # 100 МБ
    
    # Rate limiting
    LOGIN_MAX_ATTEMPTS: int = 5
    LOGIN_BLOCK_MINUTES: int = 15
    RATE_LIMIT_DEFAULT: str = "200/minute"
    RATE_LIMIT_LOGIN: str = "20/minute"
    
    # Sentry
    SENTRY_DSN: Optional[str] = None
    
    # Telegram webhook secret
    TELEGRAM_WEBHOOK_SECRET: Optional[str] = None

    # Секрет для POST /api/applications/webhook (заявки с визитки/сайта). Пустой = webhook отключён (403).
    WEBSITE_WEBHOOK_SECRET: Optional[str] = None
    
    # CORS / CSRF (в продакшне дополняется из env CORS_ORIGINS JSON-массивом)
    # Vite при занятом 5173 берёт 5174; учитываем 127.0.0.1 и preview-порт
    CORS_ORIGINS: list = [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:4173",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:4173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://agile-business-pro.com",
        "https://www.agile-business-pro.com",
        "https://app.agile-business-pro.com",
        "http://app.agile-business-pro.com",
    ]
    
    # Автоматическое создание admin-аккаунта (пустые = не создавать)
    ADMIN_SEED_EMAIL: str = ""
    ADMIN_SEED_PASSWORD: str = ""
    
    # Количество uvicorn workers (для Docker CMD)
    WORKERS: int = 1

    # Регистрация без модерации (сразу ACTIVE). В проде обычно false; при DEBUG=true вход сразу после регистрации включается автоматически (см. auth.register).
    REGISTRATION_AUTO_APPROVE: bool = False

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: object) -> object:
        # Из .env часто приходит строка; JSON-массив обязателен для pydantic-settings, иначе импорт падает.
        if v is None or isinstance(v, list):
            return v
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return []
            if s.startswith("["):
                import json
                try:
                    return json.loads(s)
                except json.JSONDecodeError:
                    pass
            parts = [x.strip().rstrip("/") for x in s.split(",") if x.strip()]
            return parts if len(parts) > 1 else ([parts[0]] if parts else [s.rstrip("/")])
        return v

    @field_validator("CORS_ORIGINS")
    @classmethod
    def normalize_cors_origins(cls, v: object) -> list:
        if not isinstance(v, list):
            return v
        out: list[str] = []
        for item in v:
            s = str(item).strip().rstrip("/")
            if s:
                out.append(s)

        for domain in (
            "https://app-agile-business-pro.vercel.app",
            "https://agile-control-center.vercel.app",
            "https://agile-control-center-agile8.vercel.app",
            "https://agile-business-pro.com",
            "https://www.agile-business-pro.com",
            "https://app.agile-business-pro.com",
            "http://app.agile-business-pro.com",
        ):
            if domain not in out:
                out.append(domain)
        return out

                

    @field_validator("SECRET_KEY")
    @classmethod
    def check_secret_key(cls, v: str, info: ValidationInfo) -> str:
        if v:
            return v
        # DEBUG уже разобран (поле выше SECRET_KEY в модели)
        if info.data.get("DEBUG"):
            # Фиксированный ключ: иначе при каждом перезапуске API «слетают» JWT и сессии
            return "dev-insecure-secret-min-32-chars-do-not-use-in-prod"
        raise ValueError("SECRET_KEY обязателен в продакшне. Задайте переменную окружения.")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()

# Сферы деятельности (роли в сферах в админке и заявках)
SPHERES = [
    "Управление и Стратегия",
    "Инвестиции и Оценка",
    "Креатив",
    "Аналитика и Данные",
    "ИТ и Разработка",
]

# Старые подписи (до унификации списка) → актуальное имя из SPHERES
SPHERE_LEGACY_ALIASES: dict[str, str] = {
    "ИТ и разработка": "ИТ и Разработка",
    "Инвестиции и оценка": "Инвестиции и Оценка",
    "Креатив дизайн": "Креатив",
}


def _norm_sphere_unicode(s: str) -> str:
    return unicodedata.normalize("NFC", (s or "").strip())


def _build_sphere_casefold_map() -> dict[str, str]:
    """casefold → каноническая строка из SPHERES (учёт разного регистра в «ИТ и Разработка» vs старый «ИТ и разработка»)."""
    m: dict[str, str] = {}
    for canonical in SPHERES:
        key = _norm_sphere_unicode(canonical).casefold()
        m[key] = canonical
    for old, new in SPHERE_LEGACY_ALIASES.items():
        m[_norm_sphere_unicode(old).casefold()] = new
    return m


_SPHERE_CASEFOLD_MAP = _build_sphere_casefold_map()


def normalize_sphere_name(raw: str) -> str:
    """Привести введённое/устаревшее имя сферы к значению из SPHERES."""
    s = _norm_sphere_unicode(raw)
    if s in SPHERES:
        return s
    if s in SPHERE_LEGACY_ALIASES:
        return SPHERE_LEGACY_ALIASES[s]
    resolved = _SPHERE_CASEFOLD_MAP.get(s.casefold())
    if resolved:
        return resolved
    return s


# Шаблоны ролей внутри сфер
SPHERE_ROLE_TEMPLATES = [
    "Рядовой сотрудник",
    "Старший сотрудник",
    "Руководитель отдела",
]

# Статусы задач
TASK_STATUSES = [
    "Готово к запуску",
    "Создаёт ценность",
    "Доставлено клиенту",
]

# Приоритеты задач
TASK_PRIORITIES = ["Низкий", "Средний", "Высокий"]

# Интервалы напоминаний о событиях (в минутах)
EVENT_REMINDER_INTERVALS = [1440, 360, 60, 45, 30, 15, 10, 5]
