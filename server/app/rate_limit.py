# Shared rate limiter instance (Redis-backed when REDIS_URL is available)
import logging
import os

from slowapi import Limiter
from starlette.requests import Request

from app.config import settings

logger = logging.getLogger(__name__)


def _get_real_ip(request: Request) -> str:
    """Extract real client IP from X-Forwarded-For (behind nginx proxy)."""
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    xri = request.headers.get("x-real-ip")
    if xri:
        return xri.strip()
    return request.client.host if request.client else "127.0.0.1"


def _rate_limit_storage_uri() -> str:
    """Без Redis slowapi падает с 500 на /auth/login — откатываемся на memory://."""
    uri = settings.REDIS_URL
    try:
        import redis as sync_redis

        r = sync_redis.from_url(uri, socket_connect_timeout=2.0)
        r.ping()
        r.close()
        return uri
    except Exception as e:
        logger.warning("Rate limiter: Redis недоступен (%s), используется memory://", e)
        return "memory://"


# Отдельный env-файл: иначе slowapi читает server/.env и включает RATELIMIT_HEADERS_ENABLED → 500 на /auth/login (ответ не Response).
_slowapi_cfg = os.path.join(os.path.dirname(__file__), "..", ".slowapi.env")

limiter = Limiter(
    key_func=_get_real_ip,
    default_limits=[settings.RATE_LIMIT_DEFAULT],
    storage_uri=_rate_limit_storage_uri(),
    headers_enabled=False,
    config_filename=_slowapi_cfg,
)

# Защитный костыль: в некоторых версиях slowapi/Starlette строковые значения
# из конфигов могут приводить к включению вставки заголовков (что ломается,
# когда endpoint возвращает Pydantic модели, а не starlette Response).
limiter._headers_enabled = False
