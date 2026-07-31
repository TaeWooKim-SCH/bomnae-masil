from __future__ import annotations

"""Load the precomputed accessibility matrix into the R2-owned database table."""

import argparse
import csv
import os
from pathlib import Path

from . import accessibility_scores
from .common import output_dir

TABLE = "accessibility_scores"
REQUIRED_COLUMNS = tuple(accessibility_scores.FIELDS)


def load_backend_env() -> None:
    """Read local backend/.env without replacing explicitly supplied variables."""
    env_path = Path(__file__).resolve().parents[2] / "backend" / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if not line or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def database_url() -> str:
    load_backend_env()
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL is required in backend/.env or the current environment.")
    return url


def validate_csv(path: Path) -> int:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or []) != REQUIRED_COLUMNS:
            raise ValueError("accessibility_scores.csv columns do not match the frozen contract.")
        rows = list(reader)
    keys = [(row["activity_id"], row["board_stop_id"]) for row in rows]
    if not rows or len(keys) != len(set(keys)):
        raise ValueError("accessibility_scores.csv must contain non-empty unique activity/board-stop rows.")
    for row in rows:
        available = row["no_transfer"] == "True"
        if not available and (row["score"] != "0" or row["best_route_id"]):
            raise ValueError("unreachable rows must have score=0 and no route fields.")
    return len(rows)


def _require_table_columns(cursor: object) -> None:
    cursor.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = %s",
        (TABLE,),
    )
    actual = {row[0] for row in cursor.fetchall()}
    missing = sorted(set(REQUIRED_COLUMNS) - actual)
    if missing:
        raise RuntimeError(f"{TABLE} is not ready; missing columns: {', '.join(missing)}")


def load(path: Path | None = None, url: str | None = None) -> dict[str, int]:
    """Atomically replace the complete precomputed matrix after schema validation."""
    source = path or output_dir() / accessibility_scores.OUTPUT_NAME
    expected = validate_csv(source)
    try:
        import psycopg2
    except ImportError as error:
        raise RuntimeError("psycopg2-binary is required; install pipeline/requirements.txt in the root .venv.") from error

    with psycopg2.connect(url or database_url()) as connection:
        with connection.cursor() as cursor:
            _require_table_columns(cursor)
            cursor.execute(f"LOCK TABLE {TABLE} IN SHARE ROW EXCLUSIVE MODE")
            cursor.execute(f"CREATE TEMP TABLE {TABLE}_stage (LIKE {TABLE} INCLUDING DEFAULTS) ON COMMIT DROP")
            with source.open("r", encoding="utf-8-sig", newline="") as stream:
                columns = ", ".join(REQUIRED_COLUMNS)
                cursor.copy_expert(
                    f"COPY {TABLE}_stage ({columns}) FROM STDIN WITH (FORMAT CSV, HEADER TRUE, NULL '')",
                    stream,
                )
            cursor.execute(f"SELECT count(*) FROM {TABLE}_stage")
            staged = cursor.fetchone()[0]
            if staged != expected:
                raise RuntimeError(f"staged row count mismatch: expected {expected}, got {staged}")
            columns = ", ".join(REQUIRED_COLUMNS)
            cursor.execute(f"DELETE FROM {TABLE}")
            cursor.execute(f"INSERT INTO {TABLE} ({columns}) SELECT {columns} FROM {TABLE}_stage")
            cursor.execute(f"SELECT count(*) FROM {TABLE}")
            loaded = cursor.fetchone()[0]
            if loaded != expected:
                raise RuntimeError(f"loaded row count mismatch: expected {expected}, got {loaded}")
    return {"expected": expected, "loaded": loaded}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rebuild", action="store_true", help="Regenerate accessibility_scores.csv before loading.")
    args = parser.parse_args()
    if args.rebuild:
        print(accessibility_scores.run())
    print(load())


if __name__ == "__main__":
    main()
