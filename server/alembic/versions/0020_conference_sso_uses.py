"""one-time conference sso tokens

Revision ID: 0020_conference_sso_uses
Revises: 0019_application_source_reference
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0020_conference_sso_uses"
down_revision = "0019_application_source_reference"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conference_sso_uses",
        sa.Column("jti", sa.String(length=64), nullable=False),
        sa.Column("conference_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["conference_id"], ["conferences.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("jti"),
    )
    op.create_index("ix_conference_sso_uses_conference_id", "conference_sso_uses", ["conference_id"])
    op.create_index("ix_conference_sso_uses_user_id", "conference_sso_uses", ["user_id"])
    op.create_index("ix_conference_sso_uses_expires_at", "conference_sso_uses", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_conference_sso_uses_expires_at", table_name="conference_sso_uses")
    op.drop_index("ix_conference_sso_uses_user_id", table_name="conference_sso_uses")
    op.drop_index("ix_conference_sso_uses_conference_id", table_name="conference_sso_uses")
    op.drop_table("conference_sso_uses")
