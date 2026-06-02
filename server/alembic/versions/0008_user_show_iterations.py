"""Add show_iterations preference to users

Revision ID: 0008_show_iterations
Revises: 0007_shop_decimal
Create Date: 2026-03-28
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0008_show_iterations"
down_revision = "0007_shop_decimal"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS show_iterations BOOLEAN NOT NULL DEFAULT false"
        )
    )


def downgrade() -> None:
    op.execute(sa.text("ALTER TABLE users DROP COLUMN IF EXISTS show_iterations"))
