"""Snapshot public Small Business Market commercial-area report pages.

The ``sang_gwon*.sg`` URLs are *read* endpoints: each has an ``analyNo``
created by a normal action in the portal.  This module only downloads those
public report URLs listed in a CSV; it does not sign in, create analyses, or
attempt to bypass portal controls.
"""

from __future__ import annotations

import argparse
import csv
import html
import re
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen


DEFAULT_DELAY_SECONDS = 0.7
REPORT_PATH = "/gis/bizonAnls/report/sg/sang_gwon1.sg"
BASE_URL = "https://bigdata.sbiz.or.kr"
PARAMETERS = ("analyNo", "upjongCd", "xcnts", "ydnts", "center_x", "center_y", "analyDate", "a", "b", "c")


@dataclass(frozen=True)
class ReportTarget:
    source_url: str
    region: str = "춘천시"

    @classmethod
    def from_row(cls, row: dict[str, str]) -> "ReportTarget":
        source_url = row.get("report_url", "").strip()
        if not source_url:
            params = {key: row.get(key, "").strip() for key in PARAMETERS}
            missing = [key for key in ("analyNo", "upjongCd", "xcnts", "ydnts", "analyDate") if not params[key]]
            if missing:
                raise ValueError("report_url or these columns are required: " + ", ".join(missing))
            source_url = f"{BASE_URL}{REPORT_PATH}?{urlencode(params)}"
        parsed = urlparse(source_url)
        if parsed.scheme != "https" or parsed.netloc != "bigdata.sbiz.or.kr":
            raise ValueError("report_url must be an https://bigdata.sbiz.or.kr URL")
        return cls(source_url=source_url, region=row.get("region", "춘천시").strip() or "춘천시")


def read_targets(path: Path) -> list[ReportTarget]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None:
            raise ValueError("targets CSV has no header")
        targets = [ReportTarget.from_row(row) for row in reader]
    if not targets:
        raise ValueError("targets CSV has no rows")
    return targets


def download_html(target: ReportTarget) -> str:
    request = Request(target.source_url, headers={"User-Agent": "bomnae-masil-data-collector/1.0"})
    try:
        with urlopen(request, timeout=30) as response:
            return response.read().decode("utf-8", errors="replace")
    except HTTPError as error:
        raise RuntimeError(f"HTTP {error.code} for {target.source_url}") from error
    except URLError as error:
        raise RuntimeError(f"network error for {target.source_url}: {error.reason}") from error


def plain(markup: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", markup))).strip()


def js_value(page: str, name: str) -> str:
    found = re.search(rf'var\s+{re.escape(name)}\s*=\s*"([^"]*)"', page)
    return found.group(1).strip() if found else ""


def metric_values(section: str) -> dict[str, str]:
    # Each visible metric is in its own ``dl.box``.  Matching from a generic
    # ``dt`` would instead see the surrounding nested definition lists.
    boxes = re.findall(r'<dl class="box">(.*?)</dl>', section, re.S)
    pairs = []
    for box in boxes:
        label = re.search(r"<dt[^>]*>(.*?)</dt>", box, re.S)
        value = re.search(r"<dd[^>]*>(.*?)</dd>", box, re.S)
        if label and value:
            pairs.append((plain(label.group(1)), plain(value.group(1))))
    stores = next((value for label, value in pairs if label.endswith("업소수")), "")
    changes = [value for label, value in pairs if label.endswith("전월대비 증감률")]
    sales = next((value for label, value in pairs if label.endswith("월평균 매출액")), "")
    return {
        "store_count": stores,
        "store_change_mom": changes[0] if changes else "",
        "monthly_sales": sales,
        "sales_change_mom": changes[1] if len(changes) > 1 else "",
    }


def parse_summary(page: str, target: ReportTarget, snapshot_date: str) -> dict[str, str]:
    titles = list(re.finditer(r'<dt class="blue_title">\s*(.*?)\s*</dt>', page, re.S))
    sections: list[tuple[str, str]] = []
    for index, match in enumerate(titles):
        end = titles[index + 1].start() if index + 1 < len(titles) else len(page)
        sections.append((plain(match.group(1)), page[match.end() : end]))

    selected = next((body for title, body in sections if title == "선택 영역"), "")
    hinterland_title, hinterland = next(((title, body) for title, body in sections if title.startswith("배후지")), ("", ""))
    query = parse_qs(urlparse(target.source_url).query)
    row = {
        "snapshot_date": snapshot_date,
        "source_url": target.source_url,
        "requested_region": target.region,
        "region": js_value(page, "aANm"),
        "administrative_code": js_value(page, "aACd"),
        "analy_no": js_value(page, "analyNo") or query.get("analyNo", [""])[0],
        "analy_date": js_value(page, "sgAnalyDate") or query.get("analyDate", [""])[0],
        "upjong_code": query.get("upjongCd", [""])[0],
        "hinterland_label": hinterland_title,
    }
    row.update({f"selected_{key}": value for key, value in metric_values(selected).items()})
    row.update({f"hinterland_{key}": value for key, value in metric_values(hinterland).items()})
    return row


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fields = sorted({field for row in rows for field in row})
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Snapshot public Chuncheon commercial-area reports.")
    parser.add_argument("--targets", type=Path, required=True, help="UTF-8/UTF-8-BOM CSV with report_url,region columns")
    parser.add_argument("--snapshot-date", required=True, help="fixed collection date, YYYY-MM-DD")
    parser.add_argument("--output-dir", type=Path, default=Path("snapshots/sbiz_bizon_analysis"))
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY_SECONDS, help="seconds between reports")
    args = parser.parse_args()

    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.snapshot_date):
        raise SystemExit("--snapshot-date must use YYYY-MM-DD")
    targets = read_targets(args.targets)
    raw_dir = args.output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str]] = []
    for index, target in enumerate(targets):
        page = download_html(target)
        analy_no = parse_qs(urlparse(target.source_url).query).get("analyNo", [str(index + 1)])[0]
        (raw_dir / f"{analy_no}.html").write_text(page, encoding="utf-8")
        rows.append(parse_summary(page, target, args.snapshot_date))
        if index < len(targets) - 1:
            time.sleep(max(args.delay, 0))
    write_csv(args.output_dir / "commercial_area_reports_chuncheon.csv", rows)
    print(f"Collected {len(rows)} report pages into {args.output_dir}")


if __name__ == "__main__":
    main()
