# API для Telegram-бота: webhook, привязка/отвязка аккаунта
import secrets
import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.middleware.auth import get_current_user
from app.services.redis import get_redis
from app.services.telegram import send_telegram_message

logger = logging.getLogger("telegram.webhook")

router = APIRouter(tags=["Telegram"])

LINK_CODE_TTL = 600  # 10 минут
LINK_CODE_PREFIX = "tg_link:"


# ——— Привязка аккаунта ———

@router.post("/users/telegram-link")
async def generate_telegram_link(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Генерирует код привязки Telegram. Пользователь отправляет /start CODE боту."""
    code = secrets.token_urlsafe(16)
    r = await get_redis()
    await r.setex(f"{LINK_CODE_PREFIX}{code}", LINK_CODE_TTL, str(user.id))

    bot_username = None
    if settings.TELEGRAM_BOT_TOKEN:
        # Получаем username бота через getMe (кэшируем в Redis на 1 час)
        cached = await r.get("tg_bot_username")
        if cached:
            bot_username = cached
        else:
            import httpx
            try:
                async with httpx.AsyncClient(timeout=5) as client:
                    resp = await client.get(
                        f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/getMe"
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        bot_username = data.get("result", {}).get("username")
                        if bot_username:
                            await r.setex("tg_bot_username", 3600, bot_username)
            except Exception:
                pass

    result = {"code": code}
    if bot_username:
        result["bot_url"] = f"https://t.me/{bot_username}?start={code}"
        result["bot_username"] = bot_username

    return result


@router.post("/users/telegram-confirm")
async def confirm_telegram_link(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Проверяет, привязан ли Telegram после отправки кода боту."""
    await db.refresh(user)
    if user.telegram_id:
        return {"linked": True, "telegram_username": user.telegram_username}
    return {"linked": False}


@router.delete("/users/telegram-link")
async def unlink_telegram(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Отвязать Telegram от аккаунта."""
    user.telegram_id = None
    user.telegram_username = None
    await db.commit()
    return {"message": "Telegram отвязан"}


# ——— Webhook для Telegram Bot API ———

class TelegramUpdate(BaseModel):
    """Минимальная схема Telegram Update."""
    update_id: int
    message: dict | None = None


@router.post("/telegram/webhook")
async def telegram_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Принимает обновления от Telegram Bot API.
    Обрабатывает команду /start CODE для привязки аккаунта.
    """
    # Проверка секрета webhook
    if settings.TELEGRAM_WEBHOOK_SECRET:
        header_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if header_secret != settings.TELEGRAM_WEBHOOK_SECRET:
            raise HTTPException(status_code=403, detail="Invalid webhook secret")

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    message = body.get("message")
    if not message:
        return {"ok": True}

    text = message.get("text", "")
    chat = message.get("chat", {})
    chat_id = str(chat.get("id", ""))
    from_user = message.get("from", {})
    tg_username = from_user.get("username", "")

    if not chat_id:
        return {"ok": True}

    # Обработка команды /start CODE
    if text.startswith("/start "):
        code = text[7:].strip()
        if not code:
            await send_telegram_message(chat_id, "❌ Код не указан. Получите код в профиле на сайте.")
            return {"ok": True}

        r = await get_redis()
        redis_key = f"{LINK_CODE_PREFIX}{code}"
        user_id = await r.get(redis_key)

        if not user_id:
            await send_telegram_message(chat_id, "❌ Код недействителен или истёк. Получите новый код в профиле.")
            return {"ok": True}

        # Привязываем telegram_id к пользователю
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            await send_telegram_message(chat_id, "❌ Пользователь не найден.")
            return {"ok": True}

        user.telegram_id = chat_id
        user.telegram_username = tg_username or None
        await db.commit()

        # Удаляем использованный код
        await r.delete(redis_key)

        await send_telegram_message(
            chat_id,
            f"✅ Аккаунт <b>{user.name}</b> успешно привязан!\n\n"
            "Теперь вы будете получать уведомления о задачах, событиях и сообщениях."
        )
        logger.info("Telegram linked: user=%s chat_id=%s", user.email, chat_id)
        return {"ok": True}

    # Команда /start без кода
    elif text == "/start":
        await send_telegram_message(
            chat_id,
            "👋 <b>Agile Business Bot</b>\n\n"
            "Для привязки аккаунта:\n"
            "1. Откройте профиль на сайте\n"
            "2. Нажмите «Получить код привязки»\n"
            "3. Отправьте боту: <code>/start КОД</code>"
        )
        return {"ok": True}

    # Команда /unlink
    elif text == "/unlink":
        result = await db.execute(select(User).where(User.telegram_id == chat_id))
        user = result.scalar_one_or_none()
        if user:
            user.telegram_id = None
            user.telegram_username = None
            await db.commit()
            await send_telegram_message(chat_id, "🔓 Аккаунт отвязан. Уведомления больше не будут приходить.")
        else:
            await send_telegram_message(chat_id, "Аккаунт не привязан.")
        return {"ok": True}

    # Команда /status
    elif text == "/status":
        result = await db.execute(select(User).where(User.telegram_id == chat_id))
        user = result.scalar_one_or_none()
        if user:
            flags = []
            if user.notify_tasks:
                flags.append("📋 Задачи")
            if user.notify_messages:
                flags.append("💬 Сообщения")
            if user.notify_events:
                flags.append("📅 События")
            await send_telegram_message(
                chat_id,
                f"✅ Привязан к <b>{user.name}</b>\n\n"
                f"Уведомления:\n" + "\n".join(flags) if flags else "Все уведомления выключены"
            )
        else:
            await send_telegram_message(chat_id, "❌ Аккаунт не привязан.")
        return {"ok": True}

    # Команда /help
    elif text == "/help":
        await send_telegram_message(
            chat_id,
            "📖 <b>Команды бота:</b>\n\n"
            "/start КОД — привязать аккаунт\n"
            "/status — статус привязки\n"
            "/unlink — отвязать аккаунт\n"
            "/help — список команд"
        )
        return {"ok": True}

    return {"ok": True}


# ——— Утилита: установка webhook (вызывается админом) ———

@router.post("/telegram/set-webhook")
async def set_webhook(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Установить webhook URL для Telegram бота. Только для администратора."""
    from app.models.user import UserRole
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Только администратор")

    if not settings.TELEGRAM_BOT_TOKEN:
        raise HTTPException(status_code=400, detail="TELEGRAM_BOT_TOKEN не настроен")

    body = await request.json()
    webhook_url = body.get("url")
    if not webhook_url:
        raise HTTPException(status_code=400, detail="Укажите url")

    import httpx
    params = {"url": webhook_url}
    if settings.TELEGRAM_WEBHOOK_SECRET:
        params["secret_token"] = settings.TELEGRAM_WEBHOOK_SECRET

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/setWebhook",
            json=params,
        )
        return resp.json()
