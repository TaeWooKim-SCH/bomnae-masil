"""Collect Chuncheon hot-place reports from the Small Business Market portal.

The portal's GIS screen requests one report at a time from the official
``/gis/hpAnls/report.json`` endpoint.  This collector deliberately does not
automate sign-in, bypass access controls, or scrape the rendered map.  Give it
only the report identifiers produced after a user selects ``춘천시`` in the
portal, and it will save the returned public reports as a reproducible local
snapshot plus analysis-friendly CSV files.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BASE_URL = "https://bigdata.sbiz.or.kr"
REPORT_PATH = "/gis/hpAnls/report.json"
DEFAULT_DELAY_SECONDS = 0.7


@dataclass(frozen=True)
class HotplaceTarget:
    theme: str
    mjr_bzznno: str
    anls_no: str
    anls_dt: str
    rptp_info_tpcd: str
    region: str = "춘천시"

    @classmethod
    def from_row(cls, row: dict[str, str]) -> "HotplaceTarget":
        aliases = {
            "theme": ("theme", "bizonTheme"),
            "mjr_bzznno": ("mjr_bzznno", "mjrBzznno"),
            "anls_no": ("anls_no", "anlsNo", "analyNo"),
            "anls_dt": ("anls_dt", "anlsDt", "analyDate"),
            "rptp_info_tpcd": ("rptp_info_tpcd", "rptpInfoTpcd"),
        }

        values: dict[str, str] = {}
        for name, candidates in aliases.items():
            values[name] = next((row.get(key, "").strip() for key in candidates if row.get(key)), "")
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise ValueError(f"target row missing required columns: {', '.join(missing)}")

        return cls(region=row.get("region", "춘천시").strip() or "춘천시", **values)


def read_targets(path: Path) -> list[HotplaceTarget]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = csv.DictReader(stream)
        if rows.fieldnames is None:
            raise ValueError("targets CSV has no header")
        targets = [HotplaceTarget.from_row(row) for row in rows]
    return [target for target in targets if "춘천" in target.region]


def request_json(target: HotplaceTarget, authorization: str | None) -> dict[str, Any]:
    params = {
        "bizonTheme": target.theme,
        "mjrBzznno": target.mjr_bzznno,
        "anlsNo": target.anls_no,
        "anlsDt": target.anls_dt,
        "rptpInfoTpcd": target.rptp_info_tpcd,
    }
    headers = {"User-Agent": "bomnae-masil-data-collector/1.0"}
    if authorization:
        headers["Authorization"] = authorization
    request = Request(f"{BASE_URL}{REPORT_PATH}?{urlencode(params)}", headers=headers)
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        message = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {error.code} for {target.mjr_bzznno}: {message[:300]}") from error
    except URLError as error:
        raise RuntimeError(f"network error for {target.mjr_bzznno}: {error.reason}") from error


def scalar_values(value: Any, prefix: str = "") -> dict[str, str]:
    """Flatten scalar report fields without inventing a schema for list metrics."""
    if isinstance(value, dict):
        flattened: dict[str, str] = {}
        for key, child in value.items():
            child_prefix = f"{prefix}_{key}" if prefix else key
            flattened.update(scalar_values(child, child_prefix))
        return flattened
    if isinstance(value, list):
        return {}
    return {prefix: "" if value is None else str(value)}


def report_row(target: HotplaceTarget, report: dict[str, Any]) -> dict[str, str]:
    basic = report.get("bizonBasicInfoMap", {})
    if isinstance(basic, dict):
        basic = basic.get("element", basic)
    if not isinstance(basic, dict):
        basic = {}
    return {
        "region": target.region,
        "theme": target.theme,
        "mjr_bzznno": target.mjr_bzznno,
        "anls_no": target.anls_no,
        "anls_dt": target.anls_dt,
        "rptp_info_tpcd": target.rptp_info_tpcd,
        **scalar_values(basic, "basic"),
    }


def metric_rows(target: HotplaceTarget, report: dict[str, Any]) -> Iterable[dict[str, str]]:
    for section, value in report.items():
        if section == "bizonBasicInfoMap":
            continue
        if isinstance(value, list):
            for index, item in enumerate(value):
                yield {
                    "region": target.region,
                    "theme": target.theme,
                    "mjr_bzznno": target.mjr_bzznno,
                    "anls_dt": target.anls_dt,
                    "section": section,
                    "row_index": str(index),
                    "values_json": json.dumps(item, ensure_ascii=False, separators=(",", ":")),
                }
        elif isinstance(value, dict) and section != "bizonBasicInfoMap":
            yield {
                "region": target.region,
                "theme": target.theme,
                "mjr_bzznno": target.mjr_bzznno,
                "anls_dt": target.anls_dt,
                "section": section,
                "row_index": "0",
                "values_json": json.dumps(value, ensure_ascii=False, separators=(",", ":")),
            }


def write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict[str, str]]) -> int:
    count = 0
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
            count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect selected Chuncheon hot-place reports.")
    parser.add_argument("--targets", type=Path, required=True, help="CSV exported from selected Chuncheon reports")
    parser.add_argument("--output-dir", type=Path, default=Path("snapshots/sbiz_hotplace"))
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY_SECONDS, help="seconds between requests")
    parser.add_argument(
        "--authorization-env",
        default="SBIZ_AUTHORIZATION",
        help="optional environment-variable name containing a normal portal Authorization value",
    )
    args = parser.parse_args()

    targets = read_targets(args.targets)
    if not targets:
        raise SystemExit("No targets whose region contains '춘천' were found.")

    output_dir = args.output_dir
    raw_dir = output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    authorization = os.environ.get(args.authorization_env) or None
    summaries: list[dict[str, str]] = []
    metrics: list[dict[str, str]] = []

    for index, target in enumerate(targets):
        report = request_json(target, authorization)
        raw_name = f"{target.theme}_{target.mjr_bzznno}_{target.anls_dt}.json"
        (raw_dir / raw_name).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        summaries.append(report_row(target, report))
        metrics.extend(metric_rows(target, report))
        if index < len(targets) - 1:
            time.sleep(max(args.delay, 0))

    summary_fields = sorted({field for row in summaries for field in row})
    write_csv(output_dir / "hotplace_reports_chuncheon.csv", summary_fields, summaries)
    write_csv(
        output_dir / "hotplace_metrics_chuncheon.csv",
        ["region", "theme", "mjr_bzznno", "anls_dt", "section", "row_index", "values_json"],
        metrics,
    )
    print(f"Collected {len(summaries)} Chuncheon reports into {output_dir}")


if __name__ == "__main__":
    main()
