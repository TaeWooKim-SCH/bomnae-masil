from __future__ import annotations

from collections import defaultdict

from .common import clean_text, read_csv, require_columns, source_path, write_csv

SOURCE = "강원특별자치도 춘천시_버스노선별 시간대별 승하차 인원_20251209.csv"


def _integer(value: str | None) -> int | None:
    try:
        return int(clean_text(value).replace(",", ""))
    except ValueError:
        return None


def run() -> dict[str, int]:
    rows = read_csv(source_path(SOURCE))
    require_columns(rows, {"수집일자", "노선번호", "이용시간대", "승차건수", "하차건수"}, SOURCE)
    totals: dict[tuple[str, str, str], list[int]] = defaultdict(lambda: [0, 0])
    dropped = 0
    for row in rows:
        date = clean_text(row.get("수집일자"))
        route_no, hour = clean_text(row.get("노선번호")), clean_text(row.get("이용시간대"))
        boardings, alightings = _integer(row.get("승차건수")), _integer(row.get("하차건수"))
        if not date or not route_no or not hour or boardings is None or alightings is None or boardings < 0 or alightings < 0:
            dropped += 1
            continue
        totals[(date, route_no, hour)][0] += boardings
        totals[(date, route_no, hour)][1] += alightings
    cleaned = [
        {"service_date": date, "route_no": route_no, "hour": hour, "boardings": values[0], "alightings": values[1]}
        for (date, route_no, hour), values in sorted(totals.items())
    ]
    written = write_csv("route_hourly.csv", ["service_date", "route_no", "hour", "boardings", "alightings"], cleaned)
    return {"input": len(rows), "written": written, "dropped": dropped}
