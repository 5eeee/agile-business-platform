"""add task start_date for task periods"""
from alembic import op
import sqlalchemy as sa

revision = "0005_task_start_date"
down_revision = "0004_deadline_dt"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        sa.text(
            "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS start_date TIMESTAMP WITHOUT TIME ZONE"
        )
    )


def downgrade():
    op.execute(sa.text("ALTER TABLE tasks DROP COLUMN IF EXISTS start_date"))