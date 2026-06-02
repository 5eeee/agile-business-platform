from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0002_iter_sort"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Колонка может уже существовать после 0001 (create_all по моделям).
    op.execute(
        sa.text(
            "ALTER TABLE iterations ADD COLUMN IF NOT EXISTS "
            "sort_order INTEGER NOT NULL DEFAULT 0"
        )
    )


def downgrade() -> None:
    op.drop_column("iterations", "sort_order")
