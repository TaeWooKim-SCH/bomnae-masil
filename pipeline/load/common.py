from __future__ import annotations

import csv
import json
import os
import re
from pathlib import Path
from typing import Iterable, Mapping


PIPELINE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SNAPSHOT_DIR = PIPELINE_DIR / "snapshots"
LEGACY_DATASET_DIR = PIPELINE_DIR.parents[1] / "dataset"


def dataset_dir() -> Path:
    configured = os.environ.get("BOMNAE_DATASET_DIR")
    if configured:
        return Path(configured)
    if DEFAULT_SNAPSHOT_DIR.exists():
        return DEFAULT_SNAPSHOT_DIR
    return LEGACY_DATASET_DIR


def output_dir() -> Path:
    path = PIPELINE_DIR / "output"
    path.mkdir(parents=True, exist_ok=True)
    return path


def source_path(name: str) -> Path:
    """Return a snapshot input, with an actionable error when it is absent."""
    path = dataset_dir() / name
    if not path.is_file():
        raise FileNotFoundError(
            f"Snapshot not found: {path}. Copy the fixed team-drive snapshot to "
            "pipeline/snapshots or set BOMNAE_DATASET_DIR."
        )
    return path


def read_csv(path: Path) -> list[dict[str, str]]:
    """Read UTF-8 source files first, then fall back only for legacy public CSVs.

    The Small Enterprise Market Promotion Agency CSV is UTF-8 (code page 65001).
    Decoding it as CP949 corrupts Korean merchant names, so CP949 is deliberately
    a fallback rather than the default.
    """
    last_error: UnicodeDecodeError | None = None
    for encoding in ("utf-8-sig", "cp949"):
        try:
            with path.open("r", encoding=encoding, newline="") as stream:
                return list(csv.DictReader(stream))
        except UnicodeDecodeError as error:
            last_error = error
    raise last_error or RuntimeError(f"Cannot decode {path}")


def require_columns(rows: list[dict[str, str]], columns: set[str], source: str) -> None:
    """Fail before writing a partial output when a public-data schema changes."""
    actual = set(rows[0]) if rows else set()
    missing = sorted(columns - actual)
    if missing:
        raise ValueError(f"{source}: required columns missing: {', '.join(missing)}")


def write_csv(name: str, fieldnames: list[str], rows: Iterable[dict[str, object]]) -> int:
    target = output_dir() / name
    count = 0
    # UTF-8 with a BOM keeps Korean text legible when the CSV is opened directly
    # in Excel. Python readers still handle it through ``utf-8-sig`` above.
    with target.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
            count += 1
    return count


def clean_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def number(value: str | None) -> float | None:
    try:
        return float((value or "").replace(",", "").strip())
    except ValueError:
        return None


def valid_wgs84(longitude: float | None, latitude: float | None) -> bool:
    return (
        longitude is not None
        and latitude is not None
        and 124 <= longitude <= 132
        and 33 <= latitude <= 39
    )


def stable_id(prefix: str, value: str) -> str:
    """Make deterministic output IDs without exposing a source's formatting quirks."""
    normalised = re.sub(r"[^0-9A-Za-z가-힣_-]+", "-", clean_text(value)).strip("-")
    return f"{prefix}_{normalised}" if normalised else ""


def normalise_chuncheon_zone_code(value: str | None) -> str:
    """Use the 42110 administrative-district prefix used by the boundary GeoJSON.

    Some public population extracts still use Chuncheon's pre-2023 51110 prefix.
    The suffix identifies the same 읍·면·동, so only that prefix is translated.
    """
    code = clean_text(value)
    return f"421{code[3:]}" if code.startswith("51110") else code


def write_report(report: dict[str, object]) -> None:
    target = output_dir() / "quality_report.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
