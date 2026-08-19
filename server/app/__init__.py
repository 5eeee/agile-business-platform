# Dynamic PostgreSQL UUID to standard SQLite-compatible UUID override
import sqlalchemy.dialects.postgresql
from sqlalchemy.types import UUID

class SQLiteCompatibleUUID(UUID):
    def __init__(self, *args, **kwargs):
        kwargs.pop("as_uuid", None)
        super().__init__(as_uuid=True, *args, **kwargs)

sqlalchemy.dialects.postgresql.UUID = SQLiteCompatibleUUID
