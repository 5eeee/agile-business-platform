"""Add idempotent source reference for website applications.

Revision ID: 0019_application_source_reference
Revises: 0018_conferences
"""

from alembic import op
import sqlalchemy as sa


revision = "0019_application_source_reference"
down_revision = "0018_conferences"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("applications")}
    if "external_reference" not in columns:
        op.add_column("applications", sa.Column("external_reference", sa.String(length=120), nullable=True))
    indexes = {index["name"] for index in inspector.get_indexes("applications")}
    if "ix_applications_external_reference" not in indexes:
        op.create_index("ix_applications_external_reference", "applications", ["external_reference"], unique=True)


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("applications")}
    indexes = {index["name"] for index in inspector.get_indexes("applications")}
    if "ix_applications_external_reference" in indexes:
        op.drop_index("ix_applications_external_reference", table_name="applications")
    if "external_reference" in columns:
        op.drop_column("applications", "external_reference")
