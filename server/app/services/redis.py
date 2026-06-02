# Redis-сервис: подключение, блэклист токенов
import logging

import redis.asyncio as redis
from app.config import settings

logger = logging.getLogger(__name__)

_redis_pool: redis.Redis | None = None

async def get_redis() -> redis.Redis:
    global _redis_pool
    if _redis_pool is None:
        # Чтобы не зависать при недоступном Redis (важно для e2e и dev).
        _redis_pool = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=0.5,
            socket_timeout=0.5,
        )
    return _redis_pool

async def blacklist_token(token: str, ttl: int = 900):
    """Добавить токен в чёрный список (по умолчанию 15 мин — время жизни access-токена)"""
    try:
        r = await get_redis()
        await r.setex(f"bl:{token}", ttl, "1")
    except Exception as e:
        logger.warning("Redis blacklist_token skipped: %s", e)

async def is_token_blacklisted(token: str) -> bool:
    """Проверить, заблокирован ли токен"""
    try:
        r = await get_redis()
        return await r.exists(f"bl:{token}") > 0
    except Exception as e:
        logger.warning("Redis is_token_blacklisted: assume not blacklisted (%s)", e)
        return False
