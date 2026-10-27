"""Create tables and the pieces SQLAlchemy models cannot express (triggers, RLS).

Run at startup; every statement is idempotent so it is safe to run repeatedly.
"""
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app import models  # noqa: F401  (registers tables on Base.metadata)
from app.db import Base

APPEND_ONLY_MSG = "shift_events is append-only: rows cannot be updated or deleted"

POSTGRES_STATEMENTS = [
    f"""
    CREATE OR REPLACE FUNCTION shift_events_append_only() RETURNS trigger AS $$
    BEGIN
        RAISE EXCEPTION '{APPEND_ONLY_MSG}';
    END;
    $$ LANGUAGE plpgsql
    """,
    "DROP TRIGGER IF EXISTS shift_events_no_change ON shift_events",
    """
    CREATE TRIGGER shift_events_no_change
        BEFORE UPDATE OR DELETE ON shift_events
        FOR EACH ROW EXECUTE FUNCTION shift_events_append_only()
    """,
    "DROP TRIGGER IF EXISTS shift_events_no_truncate ON shift_events",
    """
    CREATE TRIGGER shift_events_no_truncate
        BEFORE TRUNCATE ON shift_events
        FOR EACH STATEMENT EXECUTE FUNCTION shift_events_append_only()
    """,
]

SQLITE_STATEMENTS = [
    f"""
    CREATE TRIGGER IF NOT EXISTS shift_events_no_update
    BEFORE UPDATE ON shift_events
    BEGIN SELECT RAISE(ABORT, '{APPEND_ONLY_MSG}'); END
    """,
    f"""
    CREATE TRIGGER IF NOT EXISTS shift_events_no_delete
    BEFORE DELETE ON shift_events
    BEGIN SELECT RAISE(ABORT, '{APPEND_ONLY_MSG}'); END
    """,
]


def init_db(engine: Engine) -> None:
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        if engine.dialect.name == "postgresql":
            for stmt in POSTGRES_STATEMENTS:
                conn.execute(text(stmt))
            # Supabase exposes the public schema over its REST API. Turning row
            # level security on with no policies shuts that door; our backend
            # connects as the table owner, which is not subject to RLS.
            for table in Base.metadata.tables:
                conn.execute(text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
        elif engine.dialect.name == "sqlite":
            for stmt in SQLITE_STATEMENTS:
                conn.execute(text(stmt))
