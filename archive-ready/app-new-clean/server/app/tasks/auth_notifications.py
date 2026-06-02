"""Background auth notification tasks (Telegram/email).

Эти задачи вынесены из HTTP обработчиков, чтобы внешние сервисы
(Telegram SMTP) не могли тормозить или валить login/register.
"""

import asyncio

from app.celery_app import celery


@celery.task(name="app.tasks.auth.notify_new_registration")
def notify_new_registration_task(user_name: str, user_email: str) -> None:
    # Используем asyncio.run, т.к. сервисы отправки реализованы как async.
    from app.services.telegram import notify_new_registration

    asyncio.run(notify_new_registration(user_name, user_email))


@celery.task(name="app.tasks.auth.send_password_reset_email")
def send_password_reset_email_task(email: str, name: str, token: str) -> None:
    from app.services.email import send_password_reset_email

    asyncio.run(send_password_reset_email(email, name, token))

