from __future__ import annotations

"""Conservatively match the 2021 visitor snapshot to current merchants."""

import csv
import math
from collections import defaultdict
from pathlib import Path

from .common import output_dir, write_csv

ROOT = Path(__file__).resolve().parents[2]
SOURCE = next((ROOT / "pipeline" / "snapshots").glob("*관광지 및 상권 정밀 위치기반 이용자 실태*.csv"))
EARTH_RADIUS_M = 6_371_000
OUTPUT = "merchant_inflow_matches.csv"
FIELDS = ["merchant_id", "source_dong", "visitor_average", "distance_m", "inflow_status"]


def _scoring():
    import sys
    backend = str(ROOT / "backend")
    if backend not in sys.path:
        sys.path.insert(0, backend)
    from app.services.scoring import classify_inflow_status, normalize_merchant_name
    return classify_inflow_status, normalize_merchant_name


def _distance_m(lon_a: float, lat_a: float, lon_b: float, lat_b: float) -> float:
    lat_a, lat_b = math.radians(lat_a), math.radians(lat_b)
    d_lat, d_lon = lat_b - lat_a, math.radians(lon_b - lon_a)
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(math.sin(d_lat / 2) ** 2 + math.cos(lat_a) * math.cos(lat_b) * math.sin(d_lon / 2) ** 2))


def _source_places() -> dict[tuple[str, float, float], tuple[str, float]]:
    _, normalise = _scoring()
    totals: dict[tuple[str, float, float, str], list[int]] = defaultdict(lambda: [0, 0])
    with SOURCE.open(encoding="cp949", newline="") as stream:
        for row in csv.DictReader(stream):
            try:
                key = (normalise(row["상호명"]), round(float(row["위도"]), 6), round(float(row["경도"]), 6), row["읍면동"])
                totals[key][0] += int(row["이용자수"])
                totals[key][1] += 1
            except (KeyError, ValueError):
                continue
    return {(name, lat, lon): (dong, total / count) for (name, lat, lon, dong), (total, count) in totals.items() if name}


def build_matches(merchants: list[dict[str, str]], places: dict[tuple[str, float, float], tuple[str, float]]) -> list[dict[str, object]]:
    classify, normalise = _scoring()
    index: dict[tuple[str, int, int], list[tuple[float, float, str, float]]] = defaultdict(list)
    for (name, lat, lon), (dong, average) in places.items():
        index[name, round(lat * 1000), round(lon * 1000)].append((lat, lon, dong, average))
    matched: list[tuple[dict[str, str], str, float, float]] = []
    for merchant in merchants:
        try:
            lat, lon = float(merchant["latitude"]), float(merchant["longitude"])
        except ValueError:
            continue
        name = normalise(merchant["name"])
        candidates = []
        for y in range(round(lat * 1000) - 1, round(lat * 1000) + 2):
            for x in range(round(lon * 1000) - 1, round(lon * 1000) + 2):
                for source_lat, source_lon, dong, average in index[name, y, x]:
                    distance = _distance_m(lon, lat, source_lon, source_lat)
                    if distance <= 30:
                        candidates.append((distance, dong, average))
        if candidates:
            distance, dong, average = min(candidates)
            matched.append((merchant, dong, average, distance))
    peer_values: dict[str, list[int]] = defaultdict(list)
    for _, dong, average, _ in matched:
        peer_values[dong].append(round(average))
    return [{"merchant_id": merchant["merchant_id"], "source_dong": dong, "visitor_average": round(average, 2), "distance_m": round(distance, 2), "inflow_status": classify(round(average), peer_values[dong])} for merchant, dong, average, distance in matched]


def run() -> dict[str, int]:
    with (output_dir() / "merchants.csv").open(encoding="utf-8-sig", newline="") as stream:
        merchants = list(csv.DictReader(stream))
    rows = build_matches(merchants, _source_places())
    written = write_csv(OUTPUT, FIELDS, rows)
    return {"merchants": len(merchants), "matched": written, "unmatched": len(merchants) - written}


if __name__ == "__main__":
    print(run())
