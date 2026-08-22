"""Add scheduled conferences.

Revision ID: 0018_conferences
Revises: 0017_financial_operations
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0018_conferences"
down_revision = "0017_financial_operations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "conferences" in inspector.get_table_names():
        return
    op.create_table(
        "conferences",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("room_code", sa.String(length=64), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("invited_user_ids", sa.JSON(), nullable=False),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("room_code"),
    )
    op.create_index("ix_conferences_room_code", "conferences", ["room_code"], unique=True)
    op.create_index("ix_conferences_starts_at", "conferences", ["starts_at"])
    op.create_index("ix_conferences_status", "conferences", ["status"])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "conferences" in inspector.get_table_names():
        op.drop_table("conferences")
