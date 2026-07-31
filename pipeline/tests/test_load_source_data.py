from pipeline.load import load_source_data


def test_always_open_seed_schedule_uses_machine_readable_hours_and_fixed_stay():
    schedule, runtime = load_source_data._seed_schedule(
        {"open_time": "09:00", "close_time": "18:00"}, "always_open_place"
    )

    assert schedule == "09:00-18:00"
    assert runtime.startswith("60")


def test_always_open_seed_is_converted_to_activity_contract(monkeypatch):
    culture = [{
        "activity_id": "culture_1", "source_event_id": "1", "name": "문화행사", "type": "당일형",
        "status": "진행중", "genre": "전시", "start_date": "2026-08-01", "end_date": "2026-08-01",
        "schedule_text": "", "runtime_text": "", "price_krw": "", "price_unknown": "True",
        "audience_text": "", "venue_name": "장소", "longitude": "127.7", "latitude": "37.8",
        "needs_geocode": "False", "source_url": "https://example.com", "poster_url": "",
    }]
    seeds = [{
        "activity_id": "always_open_place", "name": "상시 활동", "type": "상시형", "place_name": "장소",
        "latitude": "37.8", "longitude": "127.7", "interest_tags": "학습·어학", "price_krw": "0", "schedule_text": "자유 이용", "source": "수기씨드",
    }]

    monkeypatch.setattr(
        load_source_data,
        "_read_rows",
        lambda name, _: culture if name == "activities_geocoded.csv" else [
            {**seed, "open_time": "09:00", "close_time": "18:00"} for seed in seeds
        ],
    )

    rows = load_source_data._activity_rows()

    assert len(rows) == 2
    assert rows[1]["source_event_id"] == "always_open_place"
    assert rows[1]["start_date"] == "2026-08-01"
    assert rows[1]["needs_geocode"] == "False"
    assert rows[1]["schedule_text"] == "09:00-18:00"
    assert rows[1]["runtime_text"].startswith("60")
    assert rows[1]["interest_tags"] == "학습·어학"


def test_legacy_floating_month_is_normalized_to_first_day(monkeypatch):
    monkeypatch.setattr(load_source_data, "_activity_rows", lambda: [])
    monkeypatch.setattr(
        load_source_data,
        "_read_rows",
        lambda name, _: [{"merchant_id": "m", "longitude": "127.7", "latitude": "37.8", "inflow_status": "추정후보"}]
        if name == "merchants.csv"
        else ([{"route_id": "r", "stop_id": "s", "longitude": "127.7", "latitude": "37.8"}] if name == "stop_routes.csv" else [{"zone_code": "z", "zone_name": "동", "month": "2025-04", "daily_average_floating_population": "1"}]),
    )

    tables = load_source_data._table_rows()

    assert tables["floating_population"][1][0]["month"] == "2025-04-01"
