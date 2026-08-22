"""Add owner-entered financial operations.

Revision ID: 0017_financial_operations
Revises: 0016_idea_management_kpi
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0017_financial_operations"
down_revision = "0016_idea_management_kpi"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "financial_operations" in inspector.get_table_names():
        return
    op.create_table(
        "financial_operations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("operation_type", sa.String(length=10), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_financial_operation_amount_positive"),
        sa.CheckConstraint("operation_type IN ('income', 'expense')", name="ck_financial_operation_type"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_financial_operations_operation_type", "financial_operations", ["operation_type"])
    op.create_index("ix_financial_operations_category", "financial_operations", ["category"])
    op.create_index("ix_financial_operations_occurred_at", "financial_operations", ["occurred_at"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "financial_operations" in inspector.get_table_names():
        op.drop_table("financial_operations")
