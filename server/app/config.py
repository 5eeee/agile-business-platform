# Конфигурация приложения
from pydantic_settings import BaseSettings
from pydantic import field_validator, ValidationInfo
from typing import Optional


class Settings(BaseSettings):
    # Приложение
    APP_NAME: str = "Agile Business"
    DEBUG: bool = False
    SECRET_KEY: str = ""
    DOMAIN: str = "localhost"
    
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
        return async_url.replace("postgresql+asyncpg://", "postgresql://") if async_url else v
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
    ]
    
    # Автоматическое создание admin-аккаунта (пустые = не создавать)
    ADMIN_SEED_EMAIL: str = ""
    ADMIN_SEED_PASSWORD: str = ""
    
    # Количество uvicorn workers (для Docker CMD)
    WORKERS: int = 1

    # Регистрация без модерации (сразу ACTIVE). В проде обычно false; при DEBUG=true вход сразу после регистрации включается автоматически (см. auth.register).
    REGISTRATION_AUTO_APPROVE: bool = False

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

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()

# Сферы деятельности
SPHERES = [
    "Управление и Стратегия",
    "Аналитика и Данные",
    "Финансовый консалтинг и учет",
    "Инвестиции и оценка",
    "ИТ и разработка",
    "Маркетинг",
    "Продажи и развитие клиентов",
    "Креатив дизайн",
    "Операции и Логистика",
    "Кадры и организации (HR)",
    "Юридическое Сопровождение",
]

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
