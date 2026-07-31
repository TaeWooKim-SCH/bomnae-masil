from __future__ import annotations

from .common import clean_text, number, read_csv, require_columns, source_path, stable_id, valid_wgs84, write_csv

SOURCE = "소상공인시장진흥공단_상가(상권)정보_강원_202603.csv"


def run() -> dict[str, int]:
    rows = read_csv(source_path(SOURCE))
    require_columns(rows, {"상가업소번호", "상호명", "시군구명", "상권업종대분류명", "경도", "위도"}, SOURCE)
    cleaned: list[dict[str, object]] = []
    seen: set[str] = set()
    dropped = 0
    for row in rows:
        if clean_text(row.get("시군구명")) != "춘천시":
            continue
        source_id = clean_text(row.get("상가업소번호"))
        merchant_id = stable_id("merchant", source_id)
        name = clean_text(row.get("상호명"))
        category = clean_text(row.get("상권업종대분류명"))
        longitude, latitude = number(row.get("경도")), number(row.get("위도"))
        if not merchant_id or merchant_id in seen or not name or not category or not valid_wgs84(longitude, latitude):
            dropped += 1
            continue
        seen.add(merchant_id)
        cleaned.append({
            "merchant_id": merchant_id, "source_merchant_id": source_id, "name": name,
            "category": category, "category_detail": clean_text(row.get("상권업종중분류명")),
            "address": clean_text(row.get("도로명주소")) or clean_text(row.get("지번주소")),
            "zone_code": clean_text(row.get("행정동코드")), "zone_name": clean_text(row.get("행정동명")),
            "longitude": longitude, "latitude": latitude,
            # Visitor-stat matching is a later, explicit step. Absence is never "confirmed low inflow".
            "inflow_status": "추정후보",
        })
    written = write_csv("merchants.csv", [
        "merchant_id", "source_merchant_id", "name", "category", "category_detail", "address",
        "zone_code", "zone_name", "longitude", "latitude", "inflow_status",
    ], cleaned)
    return {"input": len(rows), "written": written, "dropped": dropped}
