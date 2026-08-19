"""add user manager and department fields and task KPI fields

Revision ID: 0012_add_user_manager_and_department
Revises: 0011_events_event_kind
Create Date: 2026-06-12
"""
from __future__ import annotations
import os
import sys

# Добавляем корневую папку сервера в path, чтобы IDE и python корректно импортировали app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from alembic import op
# pyrefly: ignore [missing-import]
import sqlalchemy as sa

revision = "0012_add_user_manager_and_department"
down_revision = "0011_events_event_kind"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # 1. Add manager_id and department_id columns if they do not exist in users
        op.execute(
            sa.text(
                """
                ALTER TABLE users ADD COLUMN IF NOT EXISTS manager_id UUID REFERENCES users(id) ON DELETE SET NULL;
                ALTER TABLE users ADD COLUMN IF NOT EXISTS department_id VARCHAR(100);
                """
            )
        )
        
        # 2. Add KPI tracking fields to tasks table
        op.execute(
            sa.text(
                """
                ALTER TABLE tasks ADD COLUMN IF NOT EXISTS first_submitted_at TIMESTAMP;
                ALTER TABLE tasks ADD COLUMN IF NOT EXISTS last_submitted_at TIMESTAMP;
                ALTER TABLE tasks ADD COLUMN IF NOT EXISTS kpi_status VARCHAR(50);
                ALTER TABLE tasks ADD COLUMN IF NOT EXISTS has_excuse BOOLEAN NOT NULL DEFAULT false;
                ALTER TABLE tasks ADD COLUMN IF NOT EXISTS excuse_reason VARCHAR(255);
                ALTER TABLE tasks ADD COLUMN IF NOT EXISTS is_discrepancy BOOLEAN NOT NULL DEFAULT false;
                ALTER TABLE tasks ADD COLUMN IF NOT EXISTS systematic_defect BOOLEAN NOT NULL DEFAULT false;
                ALTER TABLE tasks ADD COLUMN IF NOT EXISTS return_count INTEGER NOT NULL DEFAULT 0;
                ALTER TABLE tasks ADD COLUMN IF NOT EXISTS is_bonus_eligible BOOLEAN NOT NULL DEFAULT false;
                """
            )
        )

    # 3. Create all other newly introduced tables from metadata
    import app.models
    from app.database import Base
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    # Dropping columns from tasks
    op.execute(sa.text("ALTER TABLE tasks DROP COLUMN IF EXISTS is_bonus_eligible"))
    op.execute(sa.text("ALTER TABLE tasks DROP COLUMN IF EXISTS return_count"))
    op.execute(sa.text("ALTER TABLE tasks DROP COLUMN IF EXISTS systematic_defect"))
    op.execute(sa.text("ALTER TABLE tasks DROP COLUMN IF EXISTS is_discrepancy"))
    op.execute(sa.text("ALTER TABLE tasks DROP COLUMN IF EXISTS excuse_reason"))
    op.execute(sa.text("ALTER TABLE tasks DROP COLUMN IF EXISTS has_excuse"))
    op.execute(sa.text("ALTER TABLE tasks DROP COLUMN IF EXISTS kpi_status"))
    op.execute(sa.text("ALTER TABLE tasks DROP COLUMN IF EXISTS last_submitted_at"))
    op.execute(sa.text("ALTER TABLE tasks DROP COLUMN IF EXISTS first_submitted_at"))
    
    # Dropping columns from users
    op.execute(sa.text("ALTER TABLE users DROP COLUMN IF EXISTS department_id"))
    op.execute(sa.text("ALTER TABLE users DROP COLUMN IF EXISTS manager_id"))
