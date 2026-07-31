from __future__ import annotations

import re
from pathlib import Path

from .common import clean_text, read_csv, require_columns, source_path, stable_id, write_csv

SOURCE = "춘천 문화 정보.csv"
DATE_RANGE = re.compile(r"^(\d{4}-\d{2}-\d{2})(?:\s*~\s*(\d{4}-\d{2}-\d{2}))?$")
ONLINE = re.compile(r"온라인|비대면|줌|화상|원격", re.IGNORECASE)
# Official Moabom listings occasionally omit their card's venue attribute.
# Keep only source-ID-specific corrections with a documented public source.
VENUE_OVERRIDES = {
    "12590": "조운동 도시재생현장지원센터",
    "12582": "화동2571",
    "12608": "춘천인형극장",
}
INTERESTS = ("운동·건강", "문화·공연", "공예·만들기", "사진·미디어", "요리·먹거리", "학습·어학", "자연·나들이")
MAPPING_SOURCE = Path(__file__).resolve().parents[1] / "seeds" / "activity_interest_mapping.csv"


def _mapping_rules() -> list[dict[str, str]]:
    rules = read_csv(MAPPING_SOURCE)
    require_columns(rules, {"match_type", "match_value", "interest_tags"}, MAPPING_SOURCE.name)
    for rule in rules:
        tags = {clean_text(tag) for tag in clean_text(rule.get("interest_tags")).split(";") if clean_text(tag)}
        if not tags or not tags.issubset(INTERESTS):
            raise ValueError(f"{MAPPING_SOURCE.name}: invalid interest tags in {rule!r}")
    return rules


def interest_tags_for(genre: str, title: str, rules: list[dict[str, str]]) -> list[str]:
    matched: set[str] = set()
    for rule in rules:
        match_type, value = clean_text(rule.get("match_type")), clean_text(rule.get("match_value"))
        applies = (match_type == "genre" and genre == value) or (match_type == "title_contains" and value in title)
        if applies:
            matched.update(clean_text(tag) for tag in clean_text(rule.get("interest_tags")).split(";") if clean_text(tag))
    return [interest for interest in INTERESTS if interest in matched]


def _price(price: str) -> tuple[int | None, bool]:
    value = clean_text(price)
    if "무료" in value:
        return 0, False
    return None, True


def run() -> dict[str, int]:
    rows = read_csv(source_path(SOURCE))
    require_columns(rows, {"source", "source_event_id", "title", "period", "category", "price"}, SOURCE)
    rules = _mapping_rules()
    cleaned: list[dict[str, object]] = []
    dropped = mapped = unmapped = 0
    seen: set[tuple[str, str, str]] = set()
    for event in rows:
        title, period = clean_text(event.get("title")), clean_text(event.get("period"))
        match = DATE_RANGE.match(period)
        source, source_id = clean_text(event.get("source")), clean_text(event.get("source_event_id"))
        key = (source, source_id, period)
        activity_text = " ".join((title, clean_text(event.get("address")), clean_text(event.get("category"))))
        if not title or match is None or not source_id or key in seen or ONLINE.search(activity_text):
            dropped += 1
            continue
        seen.add(key)
        price_krw, price_unknown = _price(clean_text(event.get("price")))
        tags = interest_tags_for(clean_text(event.get("category")), title, rules)
        mapped += int(bool(tags))
        unmapped += int(not tags)
        cleaned.append({
            "activity_id": stable_id(f"culture_{source}", source_id), "source_event_id": source_id,
            "name": title, "type": "당일형", "status": clean_text(event.get("status")),
            "genre": clean_text(event.get("category")), "start_date": match.group(1), "end_date": match.group(2) or match.group(1),
            "schedule_text": "", "runtime_text": "", "price_krw": price_krw, "price_unknown": price_unknown,
            "interest_tags": ";".join(tags),
            "audience_text": clean_text(event.get("target_age")), "venue_name": clean_text(event.get("address")) or VENUE_OVERRIDES.get(source_id, ""),
            "longitude": "", "latitude": "", "needs_geocode": True,
            "source_url": "https://cccf.or.kr/moa" if source == "moabom" else "https://www.cccf.or.kr/home",
            "poster_url": clean_text(event.get("image_url")),
        })
    written = write_csv("activities.csv", [
        "activity_id", "source_event_id", "name", "type", "status", "genre", "start_date", "end_date",
        "schedule_text", "runtime_text", "price_krw", "price_unknown", "interest_tags", "audience_text", "venue_name",
        "longitude", "latitude", "needs_geocode", "source_url", "poster_url",
    ], cleaned)
    return {"input": len(rows), "written": written, "dropped": dropped, "mapped": mapped, "unmapped": unmapped}
