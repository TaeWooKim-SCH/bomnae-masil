from __future__ import annotations

"""Seed fixed verification codes for the five approved R3-10 demo merchants."""

import csv
import io
import re
from pathlib import Path

from .load_source_data import database_url

SOURCE = Path(__file__).resolve().parents[1] / "seeds" / "demo_merchants.csv"


def load() -> int:
    try:
        import psycopg2
    except ImportError as error:
        raise RuntimeError("psycopg2-binary is required.") from error
    with SOURCE.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    codes = [row.get("verify_code", "") for row in rows]
    if len(rows) != 5 or len({row.get("merchant_id") for row in rows}) != 5 or len(set(codes)) != 5 or any(not re.fullmatch(r"\d{4}", code) for code in codes):
        raise ValueError("demo merchant seed requires five unique merchant IDs and four-digit codes")
    with psycopg2.connect(database_url()) as connection:
        with connection.cursor() as cursor:
            cursor.execute("CREATE TEMP TABLE demo_verify_stage (merchant_id text PRIMARY KEY, verify_code text NOT NULL) ON COMMIT DROP")
            buffer = io.StringIO()
            writer = csv.DictWriter(buffer, fieldnames=("merchant_id", "verify_code"))
            writer.writeheader(); writer.writerows(rows); buffer.seek(0)
            cursor.copy_expert("COPY demo_verify_stage (merchant_id, verify_code) FROM STDIN WITH (FORMAT CSV, HEADER TRUE)", buffer)
            cursor.execute("SELECT count(*) FROM merchants JOIN demo_verify_stage USING (merchant_id)")
            if cursor.fetchone()[0] != 5:
                raise RuntimeError("demo merchant seed contains an unknown merchant ID")
            cursor.execute("LOCK TABLE merchants IN SHARE ROW EXCLUSIVE MODE")
            cursor.execute("UPDATE merchants AS m SET verify_code = s.verify_code FROM demo_verify_stage AS s WHERE m.merchant_id = s.merchant_id")
    return len(rows)


if __name__ == "__main__":
    print({"updated": load()})
