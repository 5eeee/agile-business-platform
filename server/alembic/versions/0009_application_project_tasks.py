"""application project sync, task parent/deadline, assignees, sphere deadlines

Revision ID: 0009_application_project_sync
Revises: 0008_user_show_iterations
Create Date: 2026-04-08

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0009_application_project_sync"
down_revision = "0008_show_iterations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # Колонки/таблицы могли быть созданы в 0001 через metadata.create_all()
        op.execute(
            sa.text(
                """
                ALTER TABLE applications ADD COLUMN IF NOT EXISTS project_name VARCHAR(500);
                ALTER TABLE applications ADD COLUMN IF NOT EXISTS project_id UUID;
                ALTER TABLE applications ADD COLUMN IF NOT EXISTS sphere_deadlines_json TEXT;
                """
            )
        )
        op.execute(
            sa.text(
                """
                DO $$
                BEGIN
                  IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'fk_applications_project_id'
                  ) THEN
                    ALTER TABLE applications
                      ADD CONSTRAINT fk_applications_project_id
                      FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL;
                  END IF;
                END $$;
                """
            )
        )
        op.execute(
            sa.text(
                """
                ALTER TABLE application_tasks ADD COLUMN IF NOT EXISTS parent_id UUID;
                ALTER TABLE application_tasks ADD COLUMN IF NOT EXISTS deadline TIMESTAMP WITHOUT TIME ZONE;
                """
            )
        )
        op.execute(
            sa.text(
                """
                DO $$
                BEGIN
                  IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'fk_application_tasks_parent_id'
                  ) THEN
                    ALTER TABLE application_tasks
                      ADD CONSTRAINT fk_application_tasks_parent_id
                      FOREIGN KEY (parent_id) REFERENCES application_tasks(id) ON DELETE CASCADE;
                  END IF;
                END $$;
                """
            )
        )
        op.execute(
            sa.text(
                """
                CREATE TABLE IF NOT EXISTS application_task_assignees (
                    id UUID PRIMARY KEY,
                    application_task_id UUID NOT NULL REFERENCES application_tasks(id) ON DELETE CASCADE,
                    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    CONSTRAINT uq_application_task_assignee UNIQUE (application_task_id, user_id)
                );
                CREATE INDEX IF NOT EXISTS ix_application_task_assignees_task
                  ON application_task_assignees (application_task_id);
                """
            )
        )


def downgrade() -> None:
    op.drop_index("ix_application_task_assignees_task", table_name="application_task_assignees")
    op.drop_table("application_task_assignees")
    op.drop_constraint("fk_application_tasks_parent_id", "application_tasks", type_="foreignkey")
    op.drop_column("application_tasks", "deadline")
    op.drop_column("application_tasks", "parent_id")
    op.drop_constraint("fk_applications_project_id", "applications", type_="foreignkey")
    op.drop_column("applications", "sphere_deadlines_json")
    op.drop_column("applications", "project_id")
    op.drop_column("applications", "project_name")
