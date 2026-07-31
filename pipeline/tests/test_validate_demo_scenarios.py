import json

import pytest

from pipeline.load.validate_demo_scenarios import _load_config, distance_m, time_window_minutes


def test_distance_m_is_zero_for_same_wgs84_point():
    assert distance_m(127.73, 37.88, 127.73, 37.88) == 0


def test_distance_m_is_symmetric():
    first = distance_m(127.73, 37.88, 127.74, 37.89)
    assert first == distance_m(127.74, 37.89, 127.73, 37.88)
    assert 1_000 < first < 2_000


def test_config_requires_three_scenarios(tmp_path):
    path = tmp_path / "scenarios.json"
    path.write_text(json.dumps({"demo_now": "2026-08-01T14:00:00+09:00", "scenarios": []}), encoding="utf-8")

    with pytest.raises(ValueError, match="at least three"):
        _load_config(path)


def test_time_window_minutes_requires_an_increasing_same_day_window():
    assert time_window_minutes("14:00-18:00") == 240

    with pytest.raises(ValueError):
        time_window_minutes("18:00-14:00")
