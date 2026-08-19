# CSRF-защита: проверка заголовков Origin/Referer для мутирующих запросов
import logging
from urllib.parse import urlparse

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

# Пути, которые не требуют CSRF-проверки (server-to-server вызовы)
CSRF_EXEMPT_PATHS = {
    "/api/telegram/webhook",
    "/api/applications/webhook",  # форма визитки → бэкенд без Origin
}


def _csrf_exempt_path(path: str) -> bool:
    """Нормализуем слэш в конце — иначе /api/.../webhook/ не попадёт в множество."""
    norm = path.rstrip("/") or "/"
    if norm in {p.rstrip("/") or "/" for p in CSRF_EXEMPT_PATHS}:
        return True
    # Доп. надёжность для server-to-server webhook
    if norm.startswith("/api/applications/webhook"):
        return True
    return False


class CSRFMiddleware(BaseHTTPMiddleware):
    """
    Для SPA + JWT API:
    Проверяем, что запросы POST/PUT/DELETE приходят с правильного Origin или Referer.
    Это предотвращает CSRF-атаки, так как браузер не может подделать заголовок Origin.
    """

    def __init__(self, app, allowed_origins: list[str] | None = None):
        super().__init__(app)
        self.allowed_origins = set(allowed_origins or [])

    async def dispatch(self, request: Request, call_next):
        # Пропускаем WebSocket-запросы (до проверки method, т.к. WebSocket scope не имеет method)
        if request.scope.get("type") == "websocket":
            return await call_next(request)

        if request.method in SAFE_METHODS:
            return await call_next(request)

        # Пропускаем server-to-server вызовы (Telegram webhook и т.д.)
        if _csrf_exempt_path(request.url.path):
            return await call_next(request)

        origin = request.headers.get("origin")
        referer = request.headers.get("referer")

        # Если есть Origin — проверяем
        if origin:
            if not self._is_allowed(origin):
                logger.warning("CSRF blocked: origin=%s not in allowed=%s", origin, self.allowed_origins)
                return JSONResponse(
                    status_code=403,
                    content={"detail": "CSRF: недопустимый origin"}
                )
            return await call_next(request)

        # Если нет Origin, проверяем Referer
        if referer:
            if not self._is_allowed(referer):
                return JSONResponse(
                    status_code=403,
                    content={"detail": "CSRF: недопустимый referer"}
                )
            return await call_next(request)

        # Запросы без Origin и Referer — блокируем (браузеры всегда отправляют Origin)
        return JSONResponse(
            status_code=403,
            content={"detail": "CSRF: отсутствует origin/referer"}
        )

    def _is_local_dev_origin(self, value: str) -> bool:
        """Origin/Referer с хостом localhost или 127.0.0.1 (любой порт и путь)."""
        try:
            p = urlparse(value.strip())
        except Exception:
            return False
        if p.scheme not in ("http", "https"):
            return False
        host = (p.hostname or "").lower()
        return host in ("localhost", "127.0.0.1")

    def _is_allowed(self, value: str) -> bool:
        if self._is_local_dev_origin(value):
            return True
        for allowed in self.allowed_origins:
            if value == allowed or value.startswith(allowed + "/"):
                return True
        return False
