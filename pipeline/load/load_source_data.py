from __future__ import annotations

"""Load the remaining R3-2 source tables into the R2-owned database.

The public snapshot CSVs stay local.  This module validates their normalized
outputs, stages every table, and replaces all four tables in one transaction.
"""

import csv
import io
import os
from pathlib import Path

from .common import output_dir, valid_wgs84

ACTIVITY_COLUMNS = (
    "activity_id", "source_event_id", "name", "type", "status", "genre",
    "start_date", "end_date", "schedule_text", "runtime_text", "price_krw",
    "price_unknown", "audience_text", "venue_name", "longitude", "latitude",
    "needs_geocode", "source_url", "poster_url",
)
INTEREST_TAGS_COLUMN = "interest_tags"
INTERESTS = {"운동·건강", "문화·공연", "공예·만들기", "사진·미디어", "요리·먹거리", "학습·어학", "자연·나들이"}
MERCHANT_COLUMNS = (
    "merchant_id", "source_merchant_id", "name", "category", "category_detail",
    "address", "zone_code", "zone_name", "longitude", "latitude", "inflow_status",
)
STOP_ROUTE_COLUMNS = (
    "route_id", "route_no", "stop_id", "sequence", "stop_name", "longitude",
    "latitude", "source_date",
)
FLOATING_POPULATION_COLUMNS = (
    "zone_code", "zone_name", "month", "daily_average_floating_population",
)
ALLOWED_INFLOW_STATUS = {"확정저유입", "추정후보", "일반", "붐빔"}
DEMO_DATE = "2026-08-01"
SEED_SOURCE_URL = "https://www.chuncheon.go.kr/"


def database_url() -> str:
    """Read the local backend URL without ever writing its value to output."""
    env_path = Path(__file__).resolve().parents[2] / "backend" / ".env"
    if env_path.is_file():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if not line or line.lstrip().startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL is required in backend/.env or the current environment.")
    return url


def _read_rows(name: str, required: tuple[str, ...]) -> list[dict[str, str]]:
    path = output_dir() / name
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = set(reader.fieldnames or [])
        missing = sorted(set(required) - fields)
        if missing:
            raise ValueError(f"{name}: required columns missing: {', '.join(missing)}")
        rows = list(reader)
    if not rows:
        raise ValueError(f"{name}: no rows to load")
    return rows


def _bool(value: str, field: str) -> None:
    if value not in {"True", "False"}:
        raise ValueError(f"{field}: expected True or False")


def _coordinates(row: dict[str, str], context: str) -> None:
    try:
        longitude, latitude = float(row["longitude"]), float(row["latitude"])
    except (KeyError, ValueError) as error:
        raise ValueError(f"{context}: invalid coordinates") from error
    if not valid_wgs84(longitude, latitude):
        raise ValueError(f"{context}: coordinates must be WGS84")


def _interest_tags(value: str, context: str, *, required: bool = False) -> str:
    tags = [tag.strip() for tag in value.split(";") if tag.strip()]
    if (required and not tags) or not set(tags).issubset(INTERESTS):
        raise ValueError(f"{context}: invalid interest_tags")
    return ";".join(tags)


def _activity_rows() -> list[dict[str, str]]:
    culture = _read_rows("activities_geocoded.csv", ACTIVITY_COLUMNS)
    seeds = _read_rows(
        "always_open_activities.csv",
        ("activity_id", "name", "type", "place_name", "latitude", "longitude", "price_krw", "schedule_text", "source"),
    )
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in culture:
        _coordinates(row, row["activity_id"])
        _bool(row["price_unknown"], row["activity_id"])
        _bool(row["needs_geocode"], row["activity_id"])
        if row["needs_geocode"] != "False":
            raise ValueError(f"{row['activity_id']}: geocoded activity is still unresolved")
        converted = {column: row.get(column, "") for column in ACTIVITY_COLUMNS}
        converted[INTEREST_TAGS_COLUMN] = _interest_tags(row.get(INTEREST_TAGS_COLUMN, ""), row["activity_id"])
        rows.append(converted)
        seen.add(row["activity_id"])
    for seed in seeds:
        activity_id = seed["activity_id"]
        if not activity_id or activity_id in seen or seed["type"] != "상시형":
            raise ValueError(f"{activity_id or 'always_open'}: duplicate or invalid always-open activity")
        converted = {
            "activity_id": activity_id,
            "source_event_id": activity_id,
            "name": seed["name"],
            "type": "상시형",
            "status": "상시개방",
            "genre": "",
            "start_date": DEMO_DATE,
            "end_date": DEMO_DATE,
            "schedule_text": seed["schedule_text"],
            "runtime_text": "",
            "price_krw": seed["price_krw"],
            "price_unknown": "False",
            "audience_text": "",
            "venue_name": seed["place_name"],
            "longitude": seed["longitude"],
            "latitude": seed["latitude"],
            "needs_geocode": "False",
            "source_url": SEED_SOURCE_URL,
            "poster_url": "",
            INTEREST_TAGS_COLUMN: _interest_tags(seed.get(INTEREST_TAGS_COLUMN, ""), activity_id, required=True),
        }
        _coordinates(converted, activity_id)
        rows.append(converted)
        seen.add(activity_id)
    return rows


def _table_rows(include_interest_tags: bool = False) -> dict[str, tuple[tuple[str, ...], list[dict[str, str]]]]:
    merchants = _read_rows("merchants.csv", MERCHANT_COLUMNS)
    for row in merchants:
        _coordinates(row, row["merchant_id"])
        if row["inflow_status"] not in ALLOWED_INFLOW_STATUS:
            raise ValueError(f"{row['merchant_id']}: invalid inflow_status")
    routes = _read_rows("stop_routes.csv", STOP_ROUTE_COLUMNS)
    for row in routes:
        _coordinates(row, f"{row['route_id']}/{row['stop_id']}")
    floating = _read_rows("floating_population.csv", FLOATING_POPULATION_COLUMNS)
    for row in floating:
        # Accept a previously generated R3-2 output during the one-time
        # migration, then keep every future run on the date contract.
        if len(row["month"]) == 7:
            row["month"] = f"{row['month']}-01"
    return {
        "activities": (ACTIVITY_COLUMNS + ((INTEREST_TAGS_COLUMN,) if include_interest_tags else ()), _activity_rows()),
        "merchants": (MERCHANT_COLUMNS, merchants),
        "stop_routes": (STOP_ROUTE_COLUMNS, routes),
        "floating_population": (FLOATING_POPULATION_COLUMNS, floating),
    }


def _csv_stream(columns: tuple[str, ...], rows: list[dict[str, str]]) -> io.StringIO:
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    stream.seek(0)
    return stream


def _require_columns(cursor: object, table: str, columns: tuple[str, ...]) -> None:
    cursor.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = %s",
        (table,),
    )
    actual = {row[0] for row in cursor.fetchall()}
    missing = sorted(set(columns) - actual)
    if missing:
        raise RuntimeError(f"{table} is not ready; missing columns: {', '.join(missing)}")


def _has_column(cursor: object, table: str, column: str) -> bool:
    cursor.execute(
        "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = %s AND column_name = %s)",
        (table, column),
    )
    return bool(cursor.fetchone()[0])


def load() -> dict[str, int]:
    """Atomically replace R3-2's four remaining source tables."""
    try:
        import psycopg2
    except ImportError as error:
        raise RuntimeError("psycopg2-binary is required; install pipeline/requirements.txt in the root .venv.") from error

    with psycopg2.connect(database_url()) as connection:
        with connection.cursor() as cursor:
            tables = _table_rows(include_interest_tags=_has_column(cursor, "activities", INTEREST_TAGS_COLUMN))
            expected = {table: len(rows) for table, (_, rows) in tables.items()}
            for table, (columns, rows) in tables.items():
                _require_columns(cursor, table, columns)
                column_list = ", ".join(columns)
                cursor.execute(f"LOCK TABLE {table} IN SHARE ROW EXCLUSIVE MODE")
                cursor.execute(f"CREATE TEMP TABLE {table}_stage (LIKE {table} INCLUDING DEFAULTS) ON COMMIT DROP")
                cursor.copy_expert(
                    f"COPY {table}_stage ({column_list}) FROM STDIN WITH (FORMAT CSV, HEADER TRUE, NULL '')",
                    _csv_stream(columns, rows),
                )
                cursor.execute(f"SELECT count(*) FROM {table}_stage")
                if cursor.fetchone()[0] != expected[table]:
                    raise RuntimeError(f"{table}: staged row count mismatch")
            cursor.execute(
                "SELECT count(*) FROM stop_routes_stage AS routes "
                "LEFT JOIN bus_stops AS stops ON stops.stop_id = routes.stop_id "
                "WHERE stops.stop_id IS NULL"
            )
            if cursor.fetchone()[0]:
                raise RuntimeError("stop_routes: contains stop IDs absent from bus_stops")
            for table, (columns, _) in tables.items():
                column_list = ", ".join(columns)
                cursor.execute(f"DELETE FROM {table}")
                cursor.execute(f"INSERT INTO {table} ({column_list}) SELECT {column_list} FROM {table}_stage")
                cursor.execute(f"SELECT count(*) FROM {table}")
                if cursor.fetchone()[0] != expected[table]:
                    raise RuntimeError(f"{table}: loaded row count mismatch")
    return expected


if __name__ == "__main__":
    print(load())
