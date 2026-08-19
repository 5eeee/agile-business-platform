from __future__ import annotations

from alembic import op
# pyrefly: ignore [missing-import]
import sqlalchemy as sa

revision = "0003_col_color"
down_revision = "0002_iter_sort"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            sa.text(
                """
                ALTER TABLE iteration_board_columns
                ADD COLUMN IF NOT EXISTS color VARCHAR(30)
                """
            )
        )


def downgrade() -> None:
    op.execute(sa.text("ALTER TABLE iteration_board_columns DROP COLUMN IF EXISTS color"))
