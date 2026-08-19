"""Add customer satisfaction survey and KPI storage.

Revision ID: 0015_customer_satisfaction
Revises: 0014_manager_overtime_actions
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0015_customer_satisfaction"
down_revision = "0014_manager_overtime_actions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())

    if "customer_survey_tokens" not in existing:
        op.create_table(
            "customer_survey_tokens",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("application_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
            sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
            sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
            sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("used_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_customer_survey_tokens_application_id", "customer_survey_tokens", ["application_id"])
        op.create_index("ix_customer_survey_tokens_project_id", "customer_survey_tokens", ["project_id"])
        op.create_index("ix_customer_survey_tokens_token_hash", "customer_survey_tokens", ["token_hash"], unique=True)

    if "project_contributions" not in existing:
        op.create_table(
            "project_contributions",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("weight", sa.Numeric(6, 5), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("project_id", "user_id", name="uq_project_contribution_user"),
        )
        op.create_index("ix_project_contributions_project_id", "project_contributions", ["project_id"])
        op.create_index("ix_project_contributions_user_id", "project_contributions", ["user_id"])

    if "project_reviews" not in existing:
        op.create_table(
            "project_reviews",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
            sa.Column("application_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
            sa.Column("survey_token_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customer_survey_tokens.id", ondelete="RESTRICT"), nullable=False, unique=True),
            sa.Column("customer_name", sa.String(255), nullable=False),
            sa.Column("customer_email", sa.String(255), nullable=True),
            sa.Column("rating", sa.Integer(), nullable=False),
            sa.Column("comment", sa.Text(), nullable=False),
            sa.Column("submitted_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_project_reviews_project_id", "project_reviews", ["project_id"])
        op.create_index("ix_project_reviews_application_id", "project_reviews", ["application_id"])
        op.create_index("ix_project_reviews_submitted_at", "project_reviews", ["submitted_at"])

    if "promo_codes" not in existing:
        op.create_table(
            "promo_codes",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("review_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("project_reviews.id", ondelete="CASCADE"), nullable=False, unique=True),
            sa.Column("code", sa.String(32), nullable=False, unique=True),
            sa.Column("discount_percent", sa.Integer(), nullable=False),
            sa.Column("valid_until", sa.DateTime(), nullable=False),
            sa.Column("is_used", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_promo_codes_code", "promo_codes", ["code"], unique=True)

    if "kpi_satisfaction_history" not in existing:
        op.create_table(
            "kpi_satisfaction_history",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("employee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("period_start", sa.DateTime(), nullable=False),
            sa.Column("period_end", sa.DateTime(), nullable=False),
            sa.Column("value", sa.Numeric(5, 1), nullable=False),
            sa.Column("calculated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("employee_id", "period_start", "period_end", name="uq_kpi_satisfaction_period"),
        )
        op.create_index("ix_kpi_satisfaction_history_employee_id", "kpi_satisfaction_history", ["employee_id"])


def downgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    for table in ("kpi_satisfaction_history", "promo_codes", "project_reviews", "project_contributions", "customer_survey_tokens"):
        if table in existing:
            op.drop_table(table)
