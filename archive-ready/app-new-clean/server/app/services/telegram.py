# Сервис отправки уведомлений в Telegram
import logging
import httpx
from app.config import settings

logger = logging.getLogger("telegram")

TELEGRAM_API = "https://api.telegram.org"

_http_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=10)
    return _http_client


async def send_telegram_message(chat_id: str, text: str, parse_mode: str = "HTML") -> bool:
    """Отправить сообщение в Telegram через Bot API."""
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN не задан — уведомление не отправлено")
        return False

    url = f"{TELEGRAM_API}/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
    }

    try:
        client = _get_client()
        resp = await client.post(url, json=payload)
        if resp.status_code == 200:
            return True
        logger.error("Telegram API error %s: %s", resp.status_code, resp.text)
        return False
    except Exception as e:
        logger.error("Telegram send failed: %s", e)
        return False


async def notify_admin(text: str) -> bool:
    """Отправить уведомление администратору (TELEGRAM_ADMIN_CHAT_ID)."""
    chat_id = settings.TELEGRAM_ADMIN_CHAT_ID
    if not chat_id:
        return False
    return await send_telegram_message(chat_id, text)


# ——— Готовые шаблоны уведомлений ———

async def notify_new_registration(user_name: str, user_email: str):
    """Уведомление админу о новой регистрации."""
    text = (
        "🆕 <b>Новая регистрация</b>\n\n"
        f"👤 <b>{user_name}</b>\n"
        f"📧 {user_email}\n\n"
        "Ожидает модерации в админ-панели."
    )
    await notify_admin(text)


async def notify_user_approved(chat_id: str, user_name: str):
    """Уведомление пользователю об одобрении."""
    text = (
        f"✅ <b>{user_name}</b>, ваш аккаунт одобрен!\n\n"
        "Теперь вы можете войти в систему Agile Business."
    )
    await send_telegram_message(chat_id, text)


async def notify_user_rejected(chat_id: str, user_name: str):
    """Уведомление пользователю об отклонении."""
    text = (
        f"❌ <b>{user_name}</b>, ваша заявка отклонена.\n\n"
        "Обратитесь к администратору за подробностями."
    )
    await send_telegram_message(chat_id, text)


async def notify_user_fired(chat_id: str, user_name: str, fire_message: str):
    """Уведомление пользователю об увольнении."""
    text = (
        f"🔥 <b>{user_name}</b>, вы уволены.\n\n"
        f"Сообщение: {fire_message}"
    )
    await send_telegram_message(chat_id, text)


async def notify_task_assigned(chat_id: str, task_title: str, project_name: str):
    """Уведомление о назначении задачи."""
    text = (
        "📋 <b>Вам назначена задача</b>\n\n"
        f"Задача: <b>{task_title}</b>\n"
        f"Проект: {project_name}"
    )
    await send_telegram_message(chat_id, text)


async def notify_event_reminder(chat_id: str, event_title: str, minutes_before: int):
    """Напоминание о событии."""
    if minutes_before >= 60:
        time_str = f"{minutes_before // 60} ч."
    else:
        time_str = f"{minutes_before} мин."
    text = (
        f"⏰ <b>Напоминание:</b> событие <b>{event_title}</b> "
        f"начнётся через {time_str}"
    )
    await send_telegram_message(chat_id, text)


async def notify_new_message(chat_id: str, sender_name: str, iteration_name: str):
    """Уведомление о новом сообщении в чате."""
    text = (
        f"💬 Новое сообщение от <b>{sender_name}</b>\n"
        f"в чате итерации: {iteration_name}"
    )
    await send_telegram_message(chat_id, text)
