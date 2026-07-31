from __future__ import annotations

"""Apply only matched visitor-snapshot statuses without rewriting merchants."""

import csv

from .common import output_dir
from .load_source_data import database_url


def load() -> int:
    try:
        import psycopg2
    except ImportError as error:
        raise RuntimeError("psycopg2-binary is required.") from error
    with (output_dir() / "merchant_inflow_matches.csv").open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows or any(not row.get("merchant_id") for row in rows):
        raise ValueError("merchant_inflow_matches.csv must contain matched merchant IDs")
    with psycopg2.connect(database_url()) as connection:
        with connection.cursor() as cursor:
            cursor.execute("CREATE TEMP TABLE merchant_inflow_stage (merchant_id text PRIMARY KEY, inflow_status text NOT NULL) ON COMMIT DROP")
            cursor.copy_expert("COPY merchant_inflow_stage (merchant_id, inflow_status) FROM STDIN WITH (FORMAT CSV, HEADER TRUE)", _pairs(rows))
            cursor.execute("SELECT count(*) FROM merchants AS m JOIN merchant_inflow_stage AS s USING (merchant_id)")
            if cursor.fetchone()[0] != len(rows):
                raise RuntimeError("merchant inflow: staged merchant IDs are missing from merchants")
            cursor.execute("LOCK TABLE merchants IN SHARE ROW EXCLUSIVE MODE")
            cursor.execute("UPDATE merchants AS m SET inflow_status = s.inflow_status FROM merchant_inflow_stage AS s WHERE m.merchant_id = s.merchant_id")
    return len(rows)


def _pairs(rows: list[dict[str, str]]):
    import io
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=("merchant_id", "inflow_status"), extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    stream.seek(0)
    return stream


if __name__ == "__main__":
    print({"updated": load()})
