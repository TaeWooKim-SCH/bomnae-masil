from __future__ import annotations

from .common import clean_text, read_csv, require_columns, source_path, write_csv

SOURCE = "행정안전부_지역별(행정동) 성별 연령별 주민등록 인구수_20260630.csv"


def run() -> dict[str, int]:
    rows = read_csv(source_path(SOURCE))
    require_columns(rows, {"행정기관코드", "기준연월", "시군구명", "읍면동명", "계"}, SOURCE)
    cleaned: list[dict[str, object]] = []
    seen: set[str] = set()
    dropped = 0
    for row in rows:
        if clean_text(row.get("시군구명")) != "춘천시":
            continue
        code, name = clean_text(row.get("행정기관코드")), clean_text(row.get("읍면동명"))
        try:
            total = int(clean_text(row.get("계")).replace(",", ""))
        except ValueError:
            total = -1
        if not code or code in seen or not name or total < 0:
            dropped += 1
            continue
        seen.add(code)
        cleaned.append({"zone_code": code, "zone_name": name, "reference_date": clean_text(row.get("기준연월")), "resident_population": total})
    written = write_csv("resident_population.csv", ["zone_code", "zone_name", "reference_date", "resident_population"], cleaned)
    return {"input": len(rows), "written": written, "dropped": dropped}
