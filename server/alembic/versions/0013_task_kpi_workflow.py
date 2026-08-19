"""Add return reason code for the task KPI workflow.

Revision ID: 0013_task_kpi_workflow
Revises: 0012_add_user_manager_and_department
"""

from alembic import op
import sqlalchemy as sa


revision = "0013_task_kpi_workflow"
down_revision = "0012_add_user_manager_and_department"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 0001 creates tables from the current SQLAlchemy metadata.  On a fresh
    # installation that means this column/index may already exist, while an
    # upgraded production database still needs them.  Keep the migration safe
    # for both paths.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("task_returns")}
    if "reason_code" not in columns:
        op.add_column(
            "task_returns",
            sa.Column("reason_code", sa.String(length=100), nullable=True),
        )

    inspector = sa.inspect(bind)
    indexes = {index["name"] for index in inspector.get_indexes("task_returns")}
    if "ix_task_returns_task_reason" not in indexes:
        op.create_index(
            "ix_task_returns_task_reason",
            "task_returns",
            ["task_id", "reason_code"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    indexes = {index["name"] for index in inspector.get_indexes("task_returns")}
    if "ix_task_returns_task_reason" in indexes:
        op.drop_index("ix_task_returns_task_reason", table_name="task_returns")

    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("task_returns")}
    if "reason_code" in columns:
        op.drop_column("task_returns", "reason_code")
