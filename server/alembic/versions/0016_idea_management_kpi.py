"""Extend employee ideas for manager KPI5 workflow.

Revision ID: 0016_idea_management_kpi
Revises: 0015_customer_satisfaction
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0016_idea_management_kpi"
down_revision = "0015_customer_satisfaction"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {item["name"] for item in inspector.get_columns("employee_ideas")}
    additions = (
        ("manager_id", sa.Column("manager_id", postgresql.UUID(as_uuid=True), nullable=True)),
        ("sphere", sa.Column("sphere", sa.String(100), nullable=True)),
        ("reviewed_at", sa.Column("reviewed_at", sa.DateTime(), nullable=True)),
        ("decision", sa.Column("decision", sa.String(30), nullable=True)),
        ("reaction_days", sa.Column("reaction_days", sa.Integer(), nullable=True)),
        ("reaction_percentage", sa.Column("reaction_percentage", sa.Numeric(5, 2), nullable=True)),
        ("is_counted_in_manager_kpi5", sa.Column("is_counted_in_manager_kpi5", sa.Boolean(), nullable=False, server_default=sa.false())),
    )
    for name, column in additions:
        if name not in columns:
            op.add_column("employee_ideas", column)
    foreign_key_rows = inspector.get_foreign_keys("employee_ideas")
    foreign_keys = {fk.get("name") for fk in foreign_key_rows}
    has_manager_fk = any(fk.get("constrained_columns") == ["manager_id"] for fk in foreign_key_rows)
    if not has_manager_fk:
        op.create_foreign_key("fk_employee_ideas_manager_id", "employee_ideas", "users", ["manager_id"], ["id"], ondelete="SET NULL")
    indexes = {idx["name"] for idx in inspector.get_indexes("employee_ideas")}
    if "ix_employee_ideas_manager_id" not in indexes:
        op.create_index("ix_employee_ideas_manager_id", "employee_ideas", ["manager_id"])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {item["name"] for item in inspector.get_columns("employee_ideas")}
    indexes = {idx["name"] for idx in inspector.get_indexes("employee_ideas")}
    if "ix_employee_ideas_manager_id" in indexes:
        op.drop_index("ix_employee_ideas_manager_id", table_name="employee_ideas")
    foreign_keys = {fk.get("name") for fk in inspector.get_foreign_keys("employee_ideas")}
    if "fk_employee_ideas_manager_id" in foreign_keys:
        op.drop_constraint("fk_employee_ideas_manager_id", "employee_ideas", type_="foreignkey")
    for name in ("is_counted_in_manager_kpi5", "reaction_percentage", "reaction_days", "decision", "reviewed_at", "sphere", "manager_id"):
        if name in columns:
            op.drop_column("employee_ideas", name)
