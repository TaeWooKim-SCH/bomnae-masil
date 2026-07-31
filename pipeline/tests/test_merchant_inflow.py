from pipeline.load import merchant_inflow


def test_build_matches_requires_normalized_name_and_30m(monkeypatch):
    def classify(value, peers):
        assert value in peers
        return "확정저유입"

    monkeypatch.setattr(merchant_inflow, "_scoring", lambda: (classify, lambda value: value.replace(" ", "").lower()))
    rows = merchant_inflow.build_matches(
        [
            {"merchant_id": "matched", "name": "Cafe One", "latitude": "37.80000", "longitude": "127.70000"},
            {"merchant_id": "too_far", "name": "Cafe One", "latitude": "37.80100", "longitude": "127.70000"},
        ],
        {("cafeone", 37.80005, 127.70000): ("석사동", 100.0)},
    )

    assert len(rows) == 1
    assert rows[0]["merchant_id"] == "matched"
    assert rows[0]["inflow_status"] == "확정저유입"
