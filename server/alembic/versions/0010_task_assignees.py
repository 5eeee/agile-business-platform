"""task_assignees junction for multiple project task assignees

Revision ID: 0010_task_assignees
Revises: 0009_application_project_sync
Create Date: 2026-04-08

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0010_task_assignees"
down_revision = "0009_application_project_sync"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            sa.text(
                """
                CREATE TABLE IF NOT EXISTS task_assignees (
                    id UUID PRIMARY KEY,
                    task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (now() AT TIME ZONE 'utc')
                );
                CREATE INDEX IF NOT EXISTS ix_task_assignees_task_id ON task_assignees (task_id);
                CREATE INDEX IF NOT EXISTS ix_task_assignees_user_id ON task_assignees (user_id);
                DO $$
                BEGIN
                  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_task_assignee') THEN
                    ALTER TABLE task_assignees
                      ADD CONSTRAINT uq_task_assignee UNIQUE (task_id, user_id);
                  END IF;
                END $$;
                INSERT INTO task_assignees (id, task_id, user_id, created_at)
                SELECT gen_random_uuid(), t.id, t.assignee_id, COALESCE(t.updated_at, t.created_at)
                FROM tasks t
                WHERE t.assignee_id IS NOT NULL
                  AND NOT EXISTS (
                    SELECT 1 FROM task_assignees ta
                    WHERE ta.task_id = t.id AND ta.user_id = t.assignee_id
                  );
                """
            )
        )


def downgrade() -> None:
    op.drop_constraint("uq_task_assignee", "task_assignees", type_="unique")
    op.drop_index("ix_task_assignees_user_id", table_name="task_assignees")
    op.drop_index("ix_task_assignees_task_id", table_name="task_assignees")
    op.drop_table("task_assignees")
