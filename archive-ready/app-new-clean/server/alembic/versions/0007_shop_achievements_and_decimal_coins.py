"""Decimal coins and advanced shop metadata/equipment

Revision ID: 0007_shop_decimal
Revises: 0006_user_profile_fields
Create Date: 2026-03-28
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0007_shop_decimal"
down_revision = "0006_user_profile_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    migrations = [
        "ALTER TABLE coin_transactions ALTER COLUMN amount TYPE NUMERIC(12,2) USING amount::numeric",
        "ALTER TABLE shop_items ADD COLUMN IF NOT EXISTS rarity VARCHAR(20) NOT NULL DEFAULT 'common'",
        "ALTER TABLE shop_items ADD COLUMN IF NOT EXISTS level_required INTEGER NOT NULL DEFAULT 1",
        "ALTER TABLE shop_items ADD COLUMN IF NOT EXISTS is_featured BOOLEAN NOT NULL DEFAULT false",
        """
        CREATE TABLE IF NOT EXISTS user_shop_equips (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            purchase_id UUID NOT NULL REFERENCES shop_purchases(id) ON DELETE CASCADE,
            category VARCHAR(50) NOT NULL,
            equipped_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc')
        )
        """,
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_user_shop_category_equip ON user_shop_equips (user_id, category)",
        "CREATE INDEX IF NOT EXISTS ix_user_shop_equips_user_id ON user_shop_equips (user_id)",
    ]
    for sql in migrations:
        op.execute(sa.text(sql))


def downgrade() -> None:
    migrations = [
        "DROP INDEX IF EXISTS ix_user_shop_equips_user_id",
        "DROP INDEX IF EXISTS uq_user_shop_category_equip",
        "DROP TABLE IF EXISTS user_shop_equips",
        "ALTER TABLE shop_items DROP COLUMN IF EXISTS is_featured",
        "ALTER TABLE shop_items DROP COLUMN IF EXISTS level_required",
        "ALTER TABLE shop_items DROP COLUMN IF EXISTS rarity",
        "ALTER TABLE coin_transactions ALTER COLUMN amount TYPE INTEGER USING ROUND(amount)::integer",
    ]
    for sql in migrations:
        op.execute(sa.text(sql))
