"""Collect monthly administrative-dong floating population for Chuncheon.

The portal exposes the official administrative-dong centre points and a public
commercial-area report.  A report must be generated once per centre before its
population tab can be read.  This module deliberately fixes the industry only
as a portal-required input; exported values come from the administrative-dong
series, which is independent of that industry selection.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BASE_URL = "https://bigdata.sbiz.or.kr"
CENTRES_PATH = "/gis/api/getCoordToAdmPoint.json"
CAPTURE_PATH = "/gis/com/report/capture.json"
POPULATION_PATH = "/gis/bizonAnls/report/sg/sang_gwon4.sg"
CHUNCHEON_PREFIX = "강원특별자치도 춘천시 "
DEFAULT_DELAY_SECONDS = 0.8


@dataclass(frozen=True)
class DongCentre:
    code: str
    name: str
    tm_x: int
    tm_y: int


def request_bytes(url: str, *, method: str = "GET", payload: dict[str, object] | None = None) -> bytes:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    headers = {"User-Agent": "bomnae-masil-data-collector/1.0"}
    if data is not None:
        headers["Content-Type"] = "application/json;charset=utf-8"
    request = Request(url, data=data, method=method, headers=headers)
    try:
        with urlopen(request, timeout=45) as response:
            return response.read()
    except HTTPError as error:
        raise RuntimeError(f"HTTP {error.code}: {url}") from error
    except URLError as error:
        raise RuntimeError(f"network error: {error.reason}") from error


def chuncheon_centres() -> list[DongCentre]:
    # This viewport encloses Chuncheon.  The API returns official map-centre TM
    # coordinates, then we keep only the city identified in its own response.
    query = urlencode({"minXAxis": 240000, "maxXAxis": 290000, "minYAxis": 450000, "maxYAxis": 510000, "mapLevel": 3})
    rows = json.loads(request_bytes(f"{BASE_URL}{CENTRES_PATH}?{query}").decode("utf-8"))
    centres = [
        DongCentre(str(row["dongCd"]), str(row["admdstCdNm"]), round(float(row["centerXCrdnt"])), round(float(row["centerYCrdnt"])))
        for row in rows
        if str(row.get("dongNm", "")).startswith(CHUNCHEON_PREFIX)
    ]
    if len(centres) != 25:
        raise RuntimeError(f"expected 25 Chuncheon administrative dongs, received {len(centres)}")
    return sorted(centres, key=lambda item: item.code)


def approximate_wgs84(tm_x: int, tm_y: int) -> tuple[float, float]:
    """Map-display coordinates; the portal uses the official TM pair for analysis."""
    latitude = 37.906 + (tm_y - 487337) / 111000
    longitude = 127.735 + (tm_x - 263924) / 88000
    return latitude, longitude


def create_report(centre: DongCentre, industry_code: str) -> dict[str, object]:
    latitude, longitude = approximate_wgs84(centre.tm_x, centre.tm_y)
    payload = {
        "type": "circleRadius", "analyType": "bizonAnls", "centerX": latitude, "centerY": longitude,
        "transformX": centre.tm_x, "transformY": centre.tm_y, "upjongCd": industry_code,
        "kakaoPathStr": "", "pathStr": "", "radius": 200, "mapLevelDecision": 200,
        "apiLogin": "N", "sprNo": 0,
    }
    result = json.loads(request_bytes(f"{BASE_URL}{CAPTURE_PATH}", method="POST", payload=payload).decode("utf-8"))
    if not result.get("analyNo"):
        raise RuntimeError(f"report creation failed for {centre.name}: {result}")
    return result


def fetch_population_html(centre: DongCentre, report: dict[str, object], industry_code: str) -> str:
    params = {
        "analyNo": report["analyNo"], "analyDate": report["analyDate"], "upjongCd": industry_code,
        "admiCd": centre.code, "admiNm": f"{CHUNCHEON_PREFIX}{centre.name}", "kmAnalyNo": "", "xtLoginId": "",
    }
    url = f"{BASE_URL}{POPULATION_PATH}?{urlencode(params)}"
    return request_bytes(url).decode("utf-8", errors="replace")


def extract_population_series(page: str, dong_name: str) -> dict[str, int]:
    months = re.findall(r'flowByMnth\.push\("(\d{2}\.\d{2})"\)', page)
    series = re.search(rf'flowPopCnt\.push\(\{{\s*name\s*:\s*"{re.escape(dong_name)}"\s*,\s*data\s*:\s*\[(.*?)\]', page, re.S)
    if not months or not series:
        raise RuntimeError(f"population series for {dong_name} not found")
    values = [int(value.replace(",", "")) for value in re.findall(r"\d[\d,]*", series.group(1))]
    if len(months) != len(values):
        raise RuntimeError(f"month/value count mismatch for {dong_name}: {len(months)}/{len(values)}")
    return dict(zip(months, values, strict=True))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fields = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect 25 Chuncheon administrative-dong floating-population series.")
    parser.add_argument("--snapshot-date", required=True, help="fixed collection date, YYYY-MM-DD")
    parser.add_argument("--output-dir", type=Path, default=Path("snapshots/sbiz_bizon_population"))
    parser.add_argument("--industry-code", default="I21201", help="portal-required category; population export remains dong-level")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY_SECONDS)
    args = parser.parse_args()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.snapshot_date):
        raise SystemExit("--snapshot-date must use YYYY-MM-DD")

    output_dir = args.output_dir
    raw_dir = output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    long_rows: list[dict[str, object]] = []
    report_rows: list[dict[str, object]] = []
    centres = chuncheon_centres()
    for index, centre in enumerate(centres):
        report = create_report(centre, args.industry_code)
        page = fetch_population_html(centre, report, args.industry_code)
        (raw_dir / f"{centre.code}_{report['analyNo']}.html").write_text(page, encoding="utf-8")
        series = extract_population_series(page, centre.name)
        report_rows.append({"snapshot_date": args.snapshot_date, "dong_code": centre.code, "dong_name": centre.name, "analy_no": report["analyNo"], "analy_date": report["analyDate"]})
        long_rows.extend({"snapshot_date": args.snapshot_date, "dong_code": centre.code, "dong_name": centre.name, "month": month, "daily_average_floating_population": value} for month, value in series.items())
        if index < len(centres) - 1:
            time.sleep(max(args.delay, 0))
    write_csv(output_dir / "chuncheon_dong_floating_population_202504_202604.csv", long_rows)
    write_csv(output_dir / "report_index.csv", report_rows)
    print(f"Collected {len(long_rows)} monthly rows for {len(centres)} Chuncheon administrative dongs.")


if __name__ == "__main__":
    main()
