"""events: internal / external kind

Revision ID: 0011_events_event_kind
Revises: 0010_task_assignees
Create Date: 2026-04-20

"""
from __future__ import annotations

from alembic import op
# pyrefly: ignore [missing-import]
import sqlalchemy as sa

revision = "0011_events_event_kind"
down_revision = "0010_task_assignees"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            sa.text(
                """
                ALTER TABLE events ADD COLUMN IF NOT EXISTS event_kind VARCHAR(20) NOT NULL DEFAULT 'internal';
                """
            )
        )


def downgrade() -> None:
    op.execute(sa.text("ALTER TABLE events DROP COLUMN IF EXISTS event_kind"))
