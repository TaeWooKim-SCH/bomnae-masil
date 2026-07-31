from __future__ import annotations

import re
from collections import defaultdict

from .common import clean_text, number, read_csv, require_columns, source_path, stable_id, valid_wgs84, write_csv

CURRENCY_SOURCE = "00_(보완 필요)춘천시_춘천사랑상품권 가맹점 정보_20251119-위도,경도 정보 추가 필요.csv"
SHOP_SOURCE = "소상공인시장진흥공단_상가(상권)정보_강원_202603.csv"


def _key(value: str | None) -> str:
    return re.sub(r"[^0-9a-z가-힣]", "", clean_text(value).lower())


def run() -> dict[str, int]:
    currency_rows = read_csv(source_path(CURRENCY_SOURCE))
    shop_rows = read_csv(source_path(SHOP_SOURCE))
    require_columns(currency_rows, {"상호명", "주소"}, CURRENCY_SOURCE)
    require_columns(shop_rows, {"상가업소번호", "상호명", "시군구명", "상권업종대분류명", "경도", "위도"}, SHOP_SOURCE)
    by_name: dict[str, list[dict[str, str]]] = defaultdict(list)
    for shop in shop_rows:
        if clean_text(shop.get("시군구명")) == "춘천시" and _key(shop.get("상호명")):
            by_name[_key(shop.get("상호명"))].append(shop)

    cleaned: list[dict[str, object]] = []
    seen: set[str] = set()
    dropped = 0
    for merchant in currency_rows:
        name, address = clean_text(merchant.get("상호명")), clean_text(merchant.get("주소"))
        candidates = by_name.get(_key(name), [])
        address_key = _key(address)
        address_matches = [row for row in candidates if _key(row.get("도로명주소")) in address_key or address_key in _key(row.get("도로명주소"))]
        candidate = address_matches[0] if len(address_matches) == 1 else (candidates[0] if len(candidates) == 1 else None)
        if candidate is None:
            dropped += 1
            continue
        source_id = clean_text(candidate.get("상가업소번호"))
        longitude, latitude = number(candidate.get("경도")), number(candidate.get("위도"))
        category = clean_text(candidate.get("상권업종대분류명"))
        merchant_id = stable_id("merchant", source_id)
        if not merchant_id or merchant_id in seen or not category or not valid_wgs84(longitude, latitude):
            dropped += 1
            continue
        seen.add(merchant_id)
        cleaned.append({
            "merchant_id": merchant_id, "name": name, "category": category, "address": address,
            "longitude": longitude, "latitude": latitude, "inflow_status": "추정후보",
        })
    written = write_csv("local_currency_merchants.csv", [
        "merchant_id", "name", "category", "address", "longitude", "latitude", "inflow_status",
    ], cleaned)
    return {"input": len(currency_rows), "written": written, "dropped": dropped}
