from __future__ import annotations

from pathlib import Path

from .common import clean_text, number, read_csv, stable_id, valid_wgs84, write_csv

SOURCE = Path(__file__).resolve().parents[1] / "seeds" / "always_open_activities.csv"
INTERESTS = {"운동·건강", "문화·공연", "공예·만들기", "사진·미디어", "요리·먹거리", "학습·어학", "자연·나들이"}


def run() -> dict[str, int]:
    rows = read_csv(SOURCE)
    cleaned: list[dict[str, object]] = []
    dropped = 0
    for row in rows:
        title, place = clean_text(row.get("title")), clean_text(row.get("place_name"))
        tags = [clean_text(tag) for tag in clean_text(row.get("interest_tags")).split(";")]
        longitude, latitude = number(row.get("lng")), number(row.get("lat"))
        try:
            price = int(clean_text(row.get("price_krw")))
        except ValueError:
            price = -1
        if (not title or not place or clean_text(row.get("type")) != "상시형" or not tags
                or not set(tags).issubset(INTERESTS) or price < 0 or not valid_wgs84(longitude, latitude)):
            dropped += 1
            continue
        cleaned.append({
            "activity_id": stable_id("always_open", place), "name": title, "type": "상시형",
            "place_name": place, "latitude": latitude, "longitude": longitude,
            "interest_tags": ";".join(tags), "price_krw": price,
            "open_time": clean_text(row.get("open_time")), "close_time": clean_text(row.get("close_time")),
            "closed_days": clean_text(row.get("closed_days")), "schedule_text": clean_text(row.get("schedule_text")),
            "org": clean_text(row.get("org")), "source": clean_text(row.get("source")),
        })
    written = write_csv("always_open_activities.csv", [
        "activity_id", "name", "type", "place_name", "latitude", "longitude", "interest_tags", "price_krw",
        "open_time", "close_time", "closed_days", "schedule_text", "org", "source",
    ], cleaned)
    return {"input": len(rows), "written": written, "dropped": dropped}
