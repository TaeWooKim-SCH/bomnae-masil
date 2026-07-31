from __future__ import annotations

"""Replace only R3-owned activity source rows.

This intentionally does not call the four-table R3-2 loader: correcting an
activity source must never rewrite merchants, stop routes, or population data.
"""

from .load_source_data import (
    ACTIVITY_COLUMNS,
    ACTIVITY_ZONE_COLUMN,
    INTEREST_TAGS_COLUMN,
    _activity_rows,
    _csv_stream,
    _has_column,
    _require_columns,
    database_url,
)


def load() -> int:
    """Atomically replace ``activities`` only, retaining the current schema."""
    try:
        import psycopg2
    except ImportError as error:
        raise RuntimeError("psycopg2-binary is required; install pipeline/requirements.txt in the root .venv.") from error

    with psycopg2.connect(database_url()) as connection:
        with connection.cursor() as cursor:
            columns = ACTIVITY_COLUMNS
            if _has_column(cursor, "activities", INTEREST_TAGS_COLUMN):
                columns += (INTEREST_TAGS_COLUMN,)
            if _has_column(cursor, "activities", ACTIVITY_ZONE_COLUMN):
                columns += (ACTIVITY_ZONE_COLUMN,)
            rows = _activity_rows()
            _require_columns(cursor, "activities", columns)
            cursor.execute("LOCK TABLE activities IN SHARE ROW EXCLUSIVE MODE")
            cursor.execute(
                "CREATE TEMP TABLE activities_source_stage "
                "(LIKE activities INCLUDING DEFAULTS) ON COMMIT DROP"
            )
            column_list = ", ".join(columns)
            cursor.copy_expert(
                f"COPY activities_source_stage ({column_list}) FROM STDIN "
                "WITH (FORMAT CSV, HEADER TRUE, NULL '')",
                _csv_stream(columns, rows),
            )
            cursor.execute("SELECT count(*) FROM activities_source_stage")
            if cursor.fetchone()[0] != len(rows):
                raise RuntimeError("activities: staged row count mismatch")
            cursor.execute("DELETE FROM activities")
            cursor.execute(
                f"INSERT INTO activities ({column_list}) "
                f"SELECT {column_list} FROM activities_source_stage"
            )
            cursor.execute("SELECT count(*) FROM activities")
            if cursor.fetchone()[0] != len(rows):
                raise RuntimeError("activities: loaded row count mismatch")
    return len(rows)


if __name__ == "__main__":
    print({"activities": load()})
