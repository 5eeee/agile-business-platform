"""Add generic manager overtime actions for KPI6.

Revision ID: 0014_manager_overtime_actions
Revises: 0013_task_kpi_workflow
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0014_manager_overtime_actions"
down_revision = "0013_task_kpi_workflow"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "manager_overtime_actions" in inspector.get_table_names():
        return
    op.create_table(
        "manager_overtime_actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("manager_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("month", sa.DateTime(), nullable=False),
        sa.Column("action_type", sa.String(length=50), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("percent_awarded", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("awarded_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["manager_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("manager_id", "action_type", "source_id", name="uq_manager_overtime_action_source"),
    )
    op.create_index("ix_manager_overtime_actions_manager_id", "manager_overtime_actions", ["manager_id"])
    op.create_index("ix_manager_overtime_actions_month", "manager_overtime_actions", ["month"])


def downgrade() -> None:
    bind = op.get_bind()
    if "manager_overtime_actions" not in sa.inspect(bind).get_table_names():
        return
    op.drop_index("ix_manager_overtime_actions_month", table_name="manager_overtime_actions")
    op.drop_index("ix_manager_overtime_actions_manager_id", table_name="manager_overtime_actions")
    op.drop_table("manager_overtime_actions")
