"""Add last_name, patronymic, no_patronymic, section_access to users"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0006_user_profile_fields"
down_revision = "0005_task_start_date"
branch_labels = None
depends_on = None


def upgrade() -> None:
    migrations = [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_name VARCHAR(255)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS patronymic VARCHAR(255)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS no_patronymic BOOLEAN NOT NULL DEFAULT false",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS section_access JSON",
    ]
    for sql in migrations:
        op.execute(sa.text(sql))


def downgrade() -> None:
    for col in ("last_name", "patronymic", "no_patronymic", "section_access"):
        op.execute(sa.text(f"ALTER TABLE users DROP COLUMN IF EXISTS {col}"))
