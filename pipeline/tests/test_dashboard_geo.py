from pipeline.load.dashboard_geo import validate


def test_accessibility_contract_accepts_polygon_and_frozen_properties():
    payload = {"type": "FeatureCollection", "features": [{
        "type": "Feature",
        "properties": {"zone_code": "4211056000", "name": "석사동", "score": 72.4, "quintile": 2},
        "geometry": {"type": "Polygon", "coordinates": [[[127.7, 37.8], [127.71, 37.8], [127.71, 37.81], [127.7, 37.8]]]},
    }]}

    assert validate(payload, "accessibility") == 1


def test_inflow_contract_rejects_non_contract_status():
    payload = {"type": "FeatureCollection", "features": [{
        "type": "Feature",
        "properties": {"name": "가게", "category": "카페", "inflow_status": "미정"},
        "geometry": {"type": "Point", "coordinates": [127.7, 37.8]},
    }]}

    try:
        validate(payload, "inflow")
    except ValueError as error:
        assert "inflow_status" in str(error)
    else:
        raise AssertionError("invalid inflow status must fail validation")
