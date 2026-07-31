from __future__ import annotations

from .common import clean_text, number, read_csv, require_columns, source_path, valid_wgs84, write_csv

SOURCE = "강원특별자치도 춘천시_버스정류장 위치정보_20260326.csv"


def run() -> dict[str, int]:
    rows = read_csv(source_path(SOURCE))
    require_columns(rows, {"관리번호", "정류장명", "경도", "위도"}, SOURCE)
    seen: set[str] = set()
    cleaned: list[dict[str, object]] = []
    dropped = 0
    for row in rows:
        source_id = clean_text(row.get("관리번호"))
        longitude, latitude = number(row.get("경도")), number(row.get("위도"))
        if not source_id or source_id in seen or not valid_wgs84(longitude, latitude):
            dropped += 1
            continue
        seen.add(source_id)
        cleaned.append(
            {
                "stop_id": f"stp_{source_id}",
                "source_stop_id": source_id,
                "name": clean_text(row.get("정류장명")),
                "name_en": clean_text(row.get("정류장명(영어)")),
                "longitude": longitude,
                "latitude": latitude,
                "source_date": clean_text(row.get("데이터기준일")),
            }
        )
    written = write_csv(
        "bus_stops.csv",
        ["stop_id", "source_stop_id", "name", "name_en", "longitude", "latitude", "source_date"],
        cleaned,
    )
    return {"input": len(rows), "written": written, "dropped": dropped}
