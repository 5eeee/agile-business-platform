"""change task deadline from date to datetime"""
from alembic import op
# pyrefly: ignore [missing-import]
import sqlalchemy as sa

revision = "0004_deadline_dt"
down_revision = "0003_col_color"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # Уже DateTime после create_all() — повторный alter ломает миграцию
        op.execute(
            sa.text(
                """
                DO $$
                BEGIN
                  IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'tasks'
                      AND column_name = 'deadline' AND udt_name = 'date'
                  ) THEN
                    ALTER TABLE tasks
                      ALTER COLUMN deadline TYPE timestamp without time zone
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
            DO $$
            BEGIN
              IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'tasks'
                  AND column_name = 'deadline' AND udt_name = 'timestamp'
              ) THEN
                ALTER TABLE tasks
                  ALTER COLUMN deadline TYPE date
                  USING deadline::date;
              END IF;
            END $$;
            """
        )
    )
