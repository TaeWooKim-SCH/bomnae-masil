from __future__ import annotations

"""Load the source tables required by the dashboard-zone lookup contract."""

import csv
from pathlib import Path

from .common import output_dir
from .load_accessibility_scores import database_url

SOURCES = {
    "bus_stops": ("bus_stops.csv", ("stop_id", "source_stop_id", "name", "name_en", "longitude", "latitude", "source_date")),
    "resident_population": ("resident_population.csv", ("zone_code", "zone_name", "reference_date", "resident_population")),
}


def _validate(path: Path, columns: tuple[str, ...]) -> int:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or []) != columns:
            raise ValueError(f"{path.name}: header does not match the database contract")
        return sum(1 for _ in reader)


def load() -> dict[str, int]:
    try:
        import psycopg2
    except ImportError as error:
        raise RuntimeError("psycopg2-binary is required; install pipeline/requirements.txt in the root .venv.") from error

    sources = {table: (output_dir() / filename, columns) for table, (filename, columns) in SOURCES.items()}
    expected = {table: _validate(path, columns) for table, (path, columns) in sources.items()}
    with psycopg2.connect(database_url()) as connection:
        with connection.cursor() as cursor:
            for table, (path, columns) in sources.items():
                cursor.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND table_name = %s",
                    (table,),
                )
                actual = {row[0] for row in cursor.fetchall()}
                missing = sorted(set(columns) - actual)
                if missing:
                    raise RuntimeError(f"{table} is not ready; missing columns: {', '.join(missing)}")
                column_list = ", ".join(columns)
                cursor.execute(f"LOCK TABLE {table} IN SHARE ROW EXCLUSIVE MODE")
                cursor.execute(f"CREATE TEMP TABLE {table}_stage (LIKE {table} INCLUDING DEFAULTS) ON COMMIT DROP")
                with path.open("r", encoding="utf-8-sig", newline="") as stream:
                    cursor.copy_expert(
                        f"COPY {table}_stage ({column_list}) FROM STDIN WITH (FORMAT CSV, HEADER TRUE, NULL '')",
                        stream,
                    )
                cursor.execute(f"SELECT count(*) FROM {table}_stage")
                staged = cursor.fetchone()[0]
                if staged != expected[table]:
                    raise RuntimeError(f"{table}: staged row count mismatch")
                cursor.execute(f"DELETE FROM {table}")
                cursor.execute(f"INSERT INTO {table} ({column_list}) SELECT {column_list} FROM {table}_stage")
                cursor.execute(f"SELECT count(*) FROM {table}")
                if cursor.fetchone()[0] != expected[table]:
                    raise RuntimeError(f"{table}: loaded row count mismatch")
    return expected


if __name__ == "__main__":
    print(load())
