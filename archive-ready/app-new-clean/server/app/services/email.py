# Email-сервис (SMTP)
import asyncio
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.config import settings

logger = logging.getLogger(__name__)


def _send_email_sync(to: str, subject: str, html_body: str) -> bool:
    """Синхронная отправка email (вызывается через asyncio.to_thread)"""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        if settings.SMTP_PORT == 465:
            server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10)
        else:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10)
            server.starttls()
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_FROM, to, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        logger.error(f"Ошибка отправки email: {e}")
        return False


async def send_email(to: str, subject: str, html_body: str):
    """Отправка email через SMTP (не блокирует event loop)"""
    if not settings.SMTP_USER or not settings.SMTP_HOST:
        logger.warning(f"SMTP не настроен, письмо не отправлено: {subject} -> {to}")
        return False

    return await asyncio.to_thread(_send_email_sync, to, subject, html_body)


async def send_confirmation_email(email: str, name: str, token: str):
    """Письмо подтверждения email"""
    link = f"https://{settings.DOMAIN}/api/auth/confirm-email?token={token}"
    html = f"""
    <div style="font-family: Inter, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #E53935;">Agile Business</h2>
        <p>Здравствуйте, {name}!</p>
        <p>Подтвердите ваш email, нажав на кнопку ниже:</p>
        <a href="{link}" style="display: inline-block; padding: 12px 24px; background: #E53935; color: white; text-decoration: none; border-radius: 8px;">
            Подтвердить email
        </a>
        <p style="color: #888; font-size: 12px; margin-top: 20px;">Если вы не регистрировались, проигнорируйте это письмо.</p>
    </div>
    """
    return await send_email(email, "Подтверждение email — Agile Business", html)


async def send_password_reset_email(email: str, name: str, token: str):
    """Письмо сброса пароля"""
    link = f"https://{settings.DOMAIN}/reset-password?token={token}"
    html = f"""
    <div style="font-family: Inter, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #E53935;">Agile Business</h2>
        <p>Здравствуйте, {name}!</p>
        <p>Вы запросили сброс пароля. Нажмите кнопку ниже:</p>
        <a href="{link}" style="display: inline-block; padding: 12px 24px; background: #E53935; color: white; text-decoration: none; border-radius: 8px;">
            Сбросить пароль
        </a>
        <p style="color: #888; font-size: 12px; margin-top: 20px;">Ссылка действительна 1 час. Если вы не запрашивали сброс, проигнорируйте это письмо.</p>
    </div>
    """
    return await send_email(email, "Сброс пароля — Agile Business", html)


async def send_decision_email(email: str, name: str, approved: bool, message: str = ""):
    """Уведомление о решении по заявке"""
    if approved:
        subject = "Ваша заявка одобрена — Agile Business"
        text = "Ваша заявка на регистрацию одобрена! Вы можете войти в систему."
    else:
        subject = "Ваша заявка отклонена — Agile Business"
        text = f"К сожалению, ваша заявка была отклонена. {message}"

    html = f"""
    <div style="font-family: Inter, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #E53935;">Agile Business</h2>
        <p>Здравствуйте, {name}!</p>
        <p>{text}</p>
        {'<a href="https://' + settings.DOMAIN + '/login" style="display: inline-block; padding: 12px 24px; background: #E53935; color: white; text-decoration: none; border-radius: 8px;">Войти</a>' if approved else ''}
    </div>
    """
    return await send_email(email, subject, html)
