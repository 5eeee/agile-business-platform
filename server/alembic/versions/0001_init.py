from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from app.database import Base
import app.models  # noqa: F401

revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    # 1) Базовые таблицы/enum-ы из моделей
    Base.metadata.create_all(bind=bind)

    # 2) PostgreSQL: добавление новых enum значений (потребуется отдельный DO блок)
    op.execute(
        sa.text(
            """
            DO $$ BEGIN
              IF NOT EXISTS (
                SELECT 1 FROM pg_enum WHERE enumlabel = 'intern'
                AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'userrole')
              ) THEN
                ALTER TYPE userrole ADD VALUE 'intern';
              END IF;
            END $$;
            """
        )
    )

    # 3) CoinTransactionType enum
    op.execute(
        sa.text(
            """
            DO $$ BEGIN
              IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'cointransactiontype') THEN
                CREATE TYPE cointransactiontype AS ENUM
                  ('topic_complete','test_pass','task_approved','admin_grant','shop_purchase','daily_login');
              END IF;
            END $$;
            """
        )
    )

    # 4) DDL для добавления колонок/таблиц в уже существующей схеме
    migrations = [
        "ALTER TABLE training_topics ADD COLUMN IF NOT EXISTS section_title VARCHAR(500)",
        "ALTER TABLE training_topics ADD COLUMN IF NOT EXISTS difficulty VARCHAR(20)",
        "ALTER TABLE training_content ADD COLUMN IF NOT EXISTS content_type VARCHAR(20) DEFAULT 'text'",
        """
        CREATE TABLE IF NOT EXISTS iteration_board_columns (
            id UUID PRIMARY KEY,
            iteration_id UUID NOT NULL REFERENCES iterations(id) ON DELETE CASCADE,
            title VARCHAR(255) NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc')
        )
        """,
        "CREATE INDEX IF NOT EXISTS ix_board_column_iteration ON iteration_board_columns (iteration_id, sort_order)",
        "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS parent_id UUID REFERENCES tasks(id) ON DELETE CASCADE",
        "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS board_column_id UUID REFERENCES iteration_board_columns(id) ON DELETE SET NULL",
        "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS is_completed BOOLEAN NOT NULL DEFAULT false",
        # 2FA TOTP
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS totp_secret VARCHAR(64)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS totp_enabled BOOLEAN NOT NULL DEFAULT false",
    ]

    for sql in migrations:
        op.execute(sa.text(sql))


def downgrade() -> None:
    # Временный безопасный downgrade для initial ревизии.
    # Если понадобится rollback, обычно выполняют вручную.
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)

