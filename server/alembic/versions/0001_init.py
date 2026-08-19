from __future__ import annotations
import os
import sys

# Добавляем корневую папку сервера в path, чтобы IDE и python корректно импортировали app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

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

    # Alembic creates this column as VARCHAR(32) by default, while later
    # revision identifiers in this project are longer than 32 characters.
    # Widen it before Alembic attempts to record those revisions.
    if bind.dialect.name == "postgresql":
        op.execute(
            sa.text(
                "ALTER TABLE alembic_version "
                "ALTER COLUMN version_num TYPE VARCHAR(128)"
            )
        )

    # 1) Базовые таблицы/enum-ы из моделей
    Base.metadata.create_all(bind=bind)

    if bind.dialect.name == "postgresql":
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
                  IF NOT EXISTS (
                    SELECT 1 FROM pg_enum WHERE enumlabel = 'owner'
                    AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'userrole')
                  ) THEN
                    ALTER TYPE userrole ADD VALUE 'owner';
                  END IF;
                  IF NOT EXISTS (
                    SELECT 1 FROM pg_enum WHERE enumlabel = 'deputy_owner'
                    AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'userrole')
                  ) THEN
                    ALTER TYPE userrole ADD VALUE 'deputy_owner';
                  END IF;
                  IF NOT EXISTS (
                    SELECT 1 FROM pg_enum WHERE enumlabel = 'consultant'
                    AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'userrole')
                  ) THEN
                    ALTER TYPE userrole ADD VALUE 'consultant';
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

