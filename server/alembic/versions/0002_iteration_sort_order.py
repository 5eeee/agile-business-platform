from __future__ import annotations

from alembic import op
# pyrefly: ignore [missing-import]
import sqlalchemy as sa

revision = "0002_iter_sort"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # create_all() в 0001 мог уже создать колонку из модели — повторный add_column даёт DuplicateColumn
        op.execute(
            sa.text(
                """
                ALTER TABLE iterations
                ADD COLUMN IF NOT EXISTS sort_order INTEGER NOT NULL DEFAULT 0
                """
            )
        )


def downgrade() -> None:
    op.execute(sa.text("ALTER TABLE iterations DROP COLUMN IF EXISTS sort_order"))
