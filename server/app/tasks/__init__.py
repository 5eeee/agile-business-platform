from app.tasks.analytics import generate_daily_report
from app.tasks.reminders import check_event_reminders, check_task_deadlines
from app.tasks.auth_notifications import (
    notify_new_registration_task,
    send_password_reset_email_task,
)
