from pipeline.load.seed_kpi_demo import EXPECTED, SEED_END, SEED_START, calculate_kpi, seed_events


def test_seed_has_expected_frozen_kpis():
    events = seed_events()
    assert len(events) == 162
    assert calculate_kpi(events) == EXPECTED


def test_seed_has_no_personal_identifiers_and_uses_reserved_window():
    for event in seed_events():
        assert set(event).issubset({"event_type", "has_mission", "inflow_status", "no_transfer", "stamp_type", "amount_krw", "search_min", "seed", "occurred_at"})
        assert event["seed"] is True
        assert SEED_START <= event["occurred_at"] < SEED_END
