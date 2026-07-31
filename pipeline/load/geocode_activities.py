"""Geocode activity venues through Kakao Local, without storing credentials.

The command writes a reusable, ignored cache under ``pipeline/output``.  It is
deliberately separate from ``run_all`` so the repeatable offline normalization
run never makes a live network request.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .common import clean_text, output_dir, read_csv, valid_wgs84, write_csv

INPUT_NAME = "activities.csv"
CACHE_NAME = "activity_geocode_cache.csv"
OUTPUT_NAME = "activities_geocoded.csv"
KAKAO_URL = "https://dapi.kakao.com/v2/local/search/address.json"
BACKEND_ENV = Path(__file__).resolve().parents[2] / "backend" / ".env"


def load_backend_env() -> None:
    """Load local-only backend/.env without overwriting shell-provided secrets."""
    if not BACKEND_ENV.is_file():
        return
    for line in BACKEND_ENV.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator and key.strip() and not key.lstrip().startswith("#"):
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _documents(payload: bytes) -> list[dict[str, object]]:
    data = json.loads(payload.decode("utf-8"))
    documents = data.get("documents", [])
    return documents if isinstance(documents, list) else []


def geocode_address(address: str, api_key: str) -> tuple[float, float] | None:
    """Return ``(longitude, latitude)`` only for a valid Kakao address result."""
    request = Request(
        f"{KAKAO_URL}?{urlencode({'query': address})}",
        headers={"Authorization": f"KakaoAK {api_key}", "User-Agent": "bomnae-masil-geocoder/1.0"},
    )
    try:
        with urlopen(request, timeout=20) as response:
            documents = _documents(response.read())
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Kakao geocoding failed for {address!r}: {error}") from error
    if not documents:
        return None
    first = documents[0]
    try:
        longitude, latitude = float(first["x"]), float(first["y"])
    except (KeyError, TypeError, ValueError):
        return None
    return (longitude, latitude) if valid_wgs84(longitude, latitude) else None


def read_cache(path: Path) -> dict[str, tuple[float, float] | None]:
    if not path.is_file():
        return {}
    values: dict[str, tuple[float, float] | None] = {}
    for row in read_csv(path):
        address = clean_text(row.get("venue_name"))
        if not address:
            continue
        try:
            longitude, latitude = float(row.get("longitude", "")), float(row.get("latitude", ""))
            values[address] = (longitude, latitude) if valid_wgs84(longitude, latitude) else None
        except ValueError:
            values[address] = None
    return values


def run(input_path: Path, cache_path: Path, api_key: str) -> dict[str, int]:
    rows = read_csv(input_path)
    cache = read_cache(cache_path)
    cache_rows: list[dict[str, object]] = []
    output_rows: list[dict[str, object]] = []
    resolved = failed = reused = 0
    for row in rows:
        venue = clean_text(row.get("venue_name"))
        coordinate = cache.get(venue) if venue in cache else geocode_address(venue, api_key) if venue else None
        reused += int(venue in cache)
        if coordinate is None:
            failed += 1
            cache_rows.append({"venue_name": venue, "longitude": "", "latitude": "", "status": "not_found"})
            continue
        longitude, latitude = coordinate
        resolved += 1
        cache_rows.append({"venue_name": venue, "longitude": longitude, "latitude": latitude, "status": "ok"})
        output_rows.append({**row, "longitude": longitude, "latitude": latitude, "needs_geocode": False})
    write_csv(CACHE_NAME, ["venue_name", "longitude", "latitude", "status"], cache_rows)
    write_csv(OUTPUT_NAME, list(rows[0]) if rows else [], output_rows)
    return {"input": len(rows), "resolved": resolved, "failed": failed, "cache_reused": reused}


def main() -> None:
    parser = argparse.ArgumentParser(description="Geocode normalized activity venues with Kakao Local.")
    parser.add_argument("--input", type=Path, default=output_dir() / INPUT_NAME)
    parser.add_argument("--cache", type=Path, default=output_dir() / CACHE_NAME)
    args = parser.parse_args()
    load_backend_env()
    api_key = os.environ.get("KAKAO_REST_API_KEY")
    if not api_key:
        raise SystemExit("KAKAO_REST_API_KEY is required in the local environment; never commit it.")
    result = run(args.input, args.cache, api_key)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
