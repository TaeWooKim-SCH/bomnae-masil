from __future__ import annotations

import re

from .common import clean_text, read_csv, require_columns, source_path, write_csv

SOURCE = "춘천 25개동 월별 유동인구.csv"
MONTH = re.compile(r"^(\d{2})\.(\d{2})$")


def run() -> dict[str, int]:
    rows = read_csv(source_path(SOURCE))
    require_columns(rows, {"dong_code", "dong_name", "month", "daily_average_floating_population"}, SOURCE)
    cleaned: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    dropped = 0
    for row in rows:
        match = MONTH.match(clean_text(row.get("month")))
        code, name = clean_text(row.get("dong_code")), clean_text(row.get("dong_name"))
        try:
            population = int(float(clean_text(row.get("daily_average_floating_population"))))
        except ValueError:
            population = -1
        if not match or not code or not name or population < 0:
            dropped += 1
            continue
        month = f"20{match.group(1)}-{match.group(2)}"
        key = (code, month)
        if key in seen:
            dropped += 1
            continue
        seen.add(key)
        cleaned.append({"zone_code": code, "zone_name": name, "month": month, "daily_average_floating_population": population})
    written = write_csv("floating_population.csv", ["zone_code", "zone_name", "month", "daily_average_floating_population"], cleaned)
    return {"input": len(rows), "written": written, "dropped": dropped}
