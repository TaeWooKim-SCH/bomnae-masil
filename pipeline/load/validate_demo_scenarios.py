from __future__ import annotations

"""Validate R3-9 demo candidates against the already-loaded source tables."""

import argparse
import json
import math
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .load_source_data import database_url

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCENARIOS = ROOT / "pipeline" / "seeds" / "demo_scenarios.json"
DEFAULT_REPORT = ROOT / "pipeline" / "output" / "demo_scenario_validation.json"
CHUNCHEON_BOUNDS = (126.8, 128.0, 37.5, 38.1)
EARTH_RADIUS_M = 6_371_000


def distance_m(lon1: float, lat1: float, lon2: float, lat2: float) -> int:
    """Return the rounded great-circle distance for WGS84 longitude/latitude."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi, d_lambda = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    value = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return round(2 * EARTH_RADIUS_M * math.asin(math.sqrt(value)))


def _load_config(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload.get("scenarios"), list) or len(payload["scenarios"]) < 3:
        raise ValueError("demo scenario config requires at least three scenarios")
    datetime.fromisoformat(payload["demo_now"])
    return payload


def time_window_minutes(value: str) -> int:
    """Parse the frozen same-day ``HH:MM-HH:MM`` demo input window."""
    try:
        start, end = value.split("-", 1)
        start_minutes = int(start[:2]) * 60 + int(start[3:])
        end_minutes = int(end[:2]) * 60 + int(end[3:])
    except (ValueError, IndexError) as error:
        raise ValueError("time must use HH:MM-HH:MM") from error
    if not (0 <= start_minutes < end_minutes <= 24 * 60):
        raise ValueError("time must be an increasing same-day window")
    return end_minutes - start_minutes


def _active_candidates(cursor: Any, scenario: dict[str, Any], demo_day: date, available_minutes: int) -> list[dict[str, Any]]:
    west, east, south, north = CHUNCHEON_BOUNDS
    cursor.execute(
        """
        SELECT a.activity_id, a.name, a.type, a.start_date, a.end_date,
               a.price_krw, a.schedule_text, a.longitude, a.latitude
             , MIN(score.duration_min) AS shortest_duration_min
        FROM activities AS a
        JOIN accessibility_scores AS score ON score.activity_id = a.activity_id
        WHERE a.start_date <= %s AND a.end_date >= %s
          AND a.price_krw <= %s
          AND a.longitude BETWEEN %s AND %s AND a.latitude BETWEEN %s AND %s
          AND score.zone_code = %s AND score.no_transfer = TRUE
          AND EXISTS (
              SELECT 1 FROM unnest(string_to_array(COALESCE(a.interest_tags, ''), ';')) AS tag
              WHERE tag = ANY(%s)
          )
        GROUP BY a.activity_id, a.name, a.type, a.start_date, a.end_date,
                 a.price_krw, a.schedule_text, a.longitude, a.latitude
        HAVING MIN(score.duration_min) + 10 + 60 <= %s
        ORDER BY a.activity_id
        """,
        (demo_day, demo_day, scenario["budget_krw"], west, east, south, north, scenario["zone_code"], scenario["interests"], available_minutes),
    )
    columns = ("activity_id", "name", "type", "start_date", "end_date", "price_krw", "schedule_text", "longitude", "latitude", "shortest_duration_min")
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _merchant_summary(cursor: Any, activity: dict[str, Any], radius_m: int) -> dict[str, Any]:
    cursor.execute("SELECT merchant_id, longitude, latitude FROM merchants")
    distances = [
        (merchant_id, distance_m(activity["longitude"], activity["latitude"], longitude, latitude))
        for merchant_id, longitude, latitude in cursor.fetchall()
    ]
    nearby = sum(1 for _, meters in distances if meters <= radius_m)
    nearest_id, nearest_m = min(distances, key=lambda item: item[1]) if distances else (None, None)
    return {
        "nearby_count": nearby,
        "fallback_required": nearby == 0,
        "nearest_merchant_id": nearest_id if nearby == 0 else None,
        "nearest_merchant_distance_m": nearest_m if nearby == 0 else None,
    }


def _quality(cursor: Any, demo_day: date) -> dict[str, int]:
    west, east, south, north = CHUNCHEON_BOUNDS
    cursor.execute(
        "SELECT count(*) FROM activities WHERE longitude NOT BETWEEN %s AND %s OR latitude NOT BETWEEN %s AND %s",
        (west, east, south, north),
    )
    outside = cursor.fetchone()[0]
    cursor.execute("SELECT count(*) FROM activities WHERE end_date < %s", (demo_day,))
    past = cursor.fetchone()[0]
    cursor.execute("SELECT count(*) FROM activities WHERE COALESCE(BTRIM(name), '') = '' OR COALESCE(BTRIM(venue_name), '') = ''")
    missing_activity_fields = cursor.fetchone()[0]
    cursor.execute("SELECT count(*) FROM merchants WHERE COALESCE(BTRIM(name), '') = '' OR COALESCE(BTRIM(address), '') = ''")
    missing_merchant_fields = cursor.fetchone()[0]
    return {
        "activities_outside_chuncheon": outside,
        "activities_already_past": past,
        "activities_missing_name_or_venue": missing_activity_fields,
        "merchants_missing_name_or_address": missing_merchant_fields,
    }


def _application_decision(cursor: Any, demo_day: date) -> dict[str, Any]:
    cursor.execute(
        "SELECT count(*) FROM activities WHERE type = %s AND start_date BETWEEN %s AND %s",
        ("신청형", demo_day, date.fromordinal(demo_day.toordinal() + 14)),
    )
    count = cursor.fetchone()[0]
    return {
        "opening_within_d14": count,
        "decision": "include_application" if count else "day_only",
        "rule": "opening_date_d14; no enrollment-deadline field is available",
    }


def _low_inflow(cursor: Any) -> dict[str, Any]:
    cursor.execute("SELECT inflow_status, count(*) FROM merchants GROUP BY inflow_status ORDER BY inflow_status")
    by_status = {status: count for status, count in cursor.fetchall()}
    confirmed = by_status.get("확정저유입", 0)
    total = sum(by_status.values())
    return {
        "by_status": by_status,
        "confirmed_low_inflow_ratio": (confirmed / total) if total else 0,
        "target_50_percent_demonstrable": total > 0 and confirmed / total >= 0.5,
        "note": "Only the #26 frozen classifier may set 확정저유입; this validator does not relabel merchants.",
    }


def validate(config_path: Path = DEFAULT_SCENARIOS) -> dict[str, Any]:
    """Query the database once per scenario and return a JSON-serializable report."""
    config = _load_config(config_path)
    demo_day = datetime.fromisoformat(config["demo_now"]).date()
    radius_m = int(config.get("merchant_radius_m", 500))
    try:
        import psycopg2
    except ImportError as error:
        raise RuntimeError("psycopg2-binary is required; install pipeline requirements in the root .venv.") from error

    with psycopg2.connect(database_url()) as connection:
        with connection.cursor() as cursor:
            scenario_results = []
            for scenario in config["scenarios"]:
                available_minutes = time_window_minutes(scenario["time"])
                if available_minutes < 60:
                    raise ValueError(f"{scenario['id']}: time window must be at least 60 minutes")
                candidates = _active_candidates(cursor, scenario, demo_day, available_minutes)
                candidate_details = []
                for candidate in candidates:
                    candidate_details.append({
                        "activity_id": candidate["activity_id"],
                        "shortest_duration_min": candidate["shortest_duration_min"],
                        "required_minutes": candidate["shortest_duration_min"] + 10 + 60,
                        "merchant": _merchant_summary(cursor, candidate, radius_m),
                    })
                scenario_results.append({
                    "id": scenario["id"],
                    "input": scenario,
                    "active_candidate_count": len(candidates),
                    "has_direct_route": bool(candidates),
                    "time_filter": {
                        "available_minutes": available_minutes,
                        "rule": "shortest_duration_min + 10 minute buffer + 60 minute activity stay",
                        "venue_opening_hours": "not_machine_verifiable_from_schedule_text",
                    },
                    "candidates": candidate_details,
                    "passes_minimum_candidates": len(candidates) >= 3,
                })
            quality = _quality(cursor, demo_day)
            application = _application_decision(cursor, demo_day)
            low_inflow = _low_inflow(cursor)
    return {
        "demo_now": config["demo_now"],
        "merchant_radius_m": radius_m,
        "scenarios": scenario_results,
        "quality": quality,
        "application": application,
        "low_inflow": low_inflow,
        "all_scenarios_pass_minimum": all(item["passes_minimum_candidates"] and item["has_direct_route"] for item in scenario_results),
        "provisional_input_set": any(item["input"].get("provisional") for item in scenario_results),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate R3-9 demo inputs against the loaded database.")
    parser.add_argument("--scenarios", type=Path, default=DEFAULT_SCENARIOS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    report = validate(args.scenarios)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
