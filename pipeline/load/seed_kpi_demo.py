from __future__ import annotations

"""Seed anonymous, clearly labelled KPI demo events for R3-11."""

import argparse
from datetime import datetime, timedelta
from typing import Any

from .load_source_data import database_url

SEED_START = datetime(2026, 8, 1, 13, 0, 0)
SEED_END = datetime(2026, 8, 1, 13, 5, 0)
EXPECTED = {
    "conversion_pct": 44.0, "low_inflow_pct": 52.1, "median_search_min": 2.4,
    "feasibility_pct": 100.0, "spend_total_krw": 187_000, "seed_included": True,
}
REQUIRED_COLUMNS = {
    "event_type", "has_mission", "inflow_status", "no_transfer", "stamp_type",
    "amount_krw", "search_min", "seed", "occurred_at",
}


def _event(event_type: str, index: int, **values: Any) -> dict[str, Any]:
    return {"event_type": event_type, "seed": True, "occurred_at": SEED_START + timedelta(seconds=index), **values}


def seed_events() -> list[dict[str, Any]]:
    """Return deterministic events: no user, session, merchant, or receipt data."""
    events: list[dict[str, Any]] = []
    searches = [1.2, 1.4, 1.6, 1.7, 1.8, 1.9, 2.0, 2.1, 2.2, 2.2, 2.3, 2.3, 2.3, 2.4, 2.4,
                2.4, 2.4, 2.5, 2.5, 2.6, 2.7, 2.8, 2.9, 3.0, 3.1, 3.2, 3.4, 3.6, 3.8, 4.0]
    events.extend(_event("first_start", index, search_min=value) for index, value in enumerate(searches))
    statuses = (["확정저유입"] * 25 + ["추정후보"] * 10 + ["일반"] * 8 + ["붐빔"] * 5)
    events.extend(_event("card_exposed", 40 + index, has_mission=True, inflow_status=status, no_transfer=True)
                  for index, status in enumerate(statuses))
    events.extend(_event("card_exposed", 100 + index, has_mission=False, no_transfer=True) for index in range(12))
    events.extend(_event("quest_started", 120 + index, has_mission=True) for index in range(50))
    events.extend(_event("quest_stamped", 180 + index, stamp_type="visit") for index in range(17))
    events.extend(_event("quest_stamped", 197 + index, stamp_type="spend", amount_krw=amount)
                  for index, amount in enumerate([30_000, 35_000, 38_000, 40_000, 44_000]))
    if max(event["occurred_at"] for event in events) >= SEED_END:
        raise AssertionError("KPI seed events must stay inside the reserved seed window")
    return events


def calculate_kpi(events: list[dict[str, Any]]) -> dict[str, float | int | bool | None]:
    """Mirror the frozen dashboard formula without importing R2 modules."""
    started = sum(event["event_type"] == "quest_started" and event.get("has_mission") is True for event in events)
    stamped = sum(event["event_type"] == "quest_stamped" for event in events)
    mission = [event for event in events if event["event_type"] == "card_exposed" and event.get("has_mission") is True]
    exposed = [event for event in events if event["event_type"] == "card_exposed"]
    searches = sorted(float(event["search_min"]) for event in events if event["event_type"] == "first_start")
    middle = len(searches) // 2
    median = (searches[middle - 1] + searches[middle]) / 2 if len(searches) % 2 == 0 else searches[middle]
    return {
        "conversion_pct": round(stamped / started * 100, 1) if started else None,
        "low_inflow_pct": round(sum(event.get("inflow_status") == "확정저유입" for event in mission) / len(mission) * 100, 1) if mission else None,
        "median_search_min": round(median, 1) if searches else None,
        "feasibility_pct": round(sum(event.get("no_transfer") is True for event in exposed) / len(exposed) * 100, 1) if exposed else 100.0,
        "spend_total_krw": sum(int(event.get("amount_krw") or 0) for event in events if event.get("stamp_type") == "spend"),
        "seed_included": any(event.get("seed") is True for event in events),
    }


def _require_table(cursor: Any) -> None:
    cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'kpi_events'")
    missing = REQUIRED_COLUMNS - {row[0] for row in cursor.fetchall()}
    if missing:
        raise RuntimeError(f"kpi_events is not ready; missing columns: {', '.join(sorted(missing))}")


def load(*, apply: bool = False) -> dict[str, Any]:
    events = seed_events()
    expected = calculate_kpi(events)
    if expected != EXPECTED:
        raise AssertionError(f"seed formula changed: {expected}")
    result: dict[str, Any] = {"events": len(events), "expected": expected, "applied": apply}
    if not apply:
        return result
    try:
        import psycopg2
    except ImportError as error:
        raise RuntimeError("psycopg2-binary is required; install pipeline requirements in the root .venv.") from error
    columns = ("event_type", "has_mission", "inflow_status", "no_transfer", "stamp_type", "amount_krw", "search_min", "seed", "occurred_at")
    with psycopg2.connect(database_url()) as connection:
        with connection.cursor() as cursor:
            _require_table(cursor)
            cursor.execute("DELETE FROM kpi_events WHERE seed = TRUE AND occurred_at >= %s AND occurred_at < %s", (SEED_START, SEED_END))
            cursor.executemany(
                f"INSERT INTO kpi_events ({', '.join(columns)}) VALUES ({', '.join(['%s'] * len(columns))})",
                [tuple(event.get(column) for column in columns) for event in events],
            )
            cursor.execute("SELECT count(*) FROM kpi_events WHERE seed = TRUE AND occurred_at >= %s AND occurred_at < %s", (SEED_START, SEED_END))
            loaded = cursor.fetchone()[0]
            if loaded != len(events):
                raise RuntimeError(f"KPI seed row count mismatch: expected {len(events)}, got {loaded}")
    result["loaded"] = loaded
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare or apply the R3-11 anonymous KPI demo seed.")
    parser.add_argument("--apply", action="store_true", help="Write the fixed seed batch to kpi_events.")
    args = parser.parse_args()
    print(load(apply=args.apply))


if __name__ == "__main__":
    main()
