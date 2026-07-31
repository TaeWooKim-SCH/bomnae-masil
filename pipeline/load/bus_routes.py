from __future__ import annotations

from .common import clean_text, number, read_csv, require_columns, source_path, valid_wgs84, write_csv

SOURCE = "강원특별자치도 춘천시_버스정류장 노선정보_20260326.csv"


def run() -> dict[str, int]:
    rows = read_csv(source_path(SOURCE))
    require_columns(rows, {"노선", "정류장", "정류장순서", "경도", "위도"}, SOURCE)
    seen: set[tuple[str, str, str]] = set()
    cleaned: list[dict[str, object]] = []
    dropped = 0
    for row in rows:
        route_id = clean_text(row.get("노선"))
        stop_id = clean_text(row.get("정류장"))
        sequence = clean_text(row.get("정류장순서"))
        key = (route_id, stop_id, sequence)
        longitude, latitude = number(row.get("경도")), number(row.get("위도"))
        if not all(key) or key in seen or not valid_wgs84(longitude, latitude):
            dropped += 1
            continue
        seen.add(key)
        cleaned.append(
            {
                "route_id": route_id,
                "route_no": clean_text(row.get("노선번호")),
                "stop_id": f"stp_{stop_id}",
                "sequence": sequence,
                "stop_name": clean_text(row.get("정류장명")),
                "longitude": longitude,
                "latitude": latitude,
                "source_date": clean_text(row.get("데이터기준일")),
            }
        )
    written = write_csv(
        "stop_routes.csv",
        ["route_id", "route_no", "stop_id", "sequence", "stop_name", "longitude", "latitude", "source_date"],
        cleaned,
    )
    return {"input": len(rows), "written": written, "dropped": dropped}
