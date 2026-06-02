"""change task deadline from date to datetime"""
from alembic import op
import sqlalchemy as sa

revision = "0004_deadline_dt"
down_revision = "0003_col_color"
branch_labels = None
depends_on = None


def upgrade():
    # После 0001 (create_all) колонка уже может быть TIMESTAMP — миграция только для старых БД с DATE.
    op.execute(
        sa.text(
            """
            DO $$ BEGIN
              IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'tasks'
                  AND column_name = 'deadline' AND data_type = 'date'
              ) THEN
                ALTER TABLE tasks ALTER COLUMN deadline TYPE TIMESTAMP WITHOUT TIME ZONE
                  USING deadline::timestamp;
              END IF;
            END $$;
            """
        )
    )


def downgrade():
    op.execute(
        sa.text(
            """
            DO $$ BEGIN
              IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'tasks'
                  AND column_name = 'deadline'
                  AND data_type = 'timestamp without time zone'
              ) THEN
                ALTER TABLE tasks ALTER COLUMN deadline TYPE DATE
                  USING deadline::date;
              END IF;
            END $$;
            """
        )
    )
