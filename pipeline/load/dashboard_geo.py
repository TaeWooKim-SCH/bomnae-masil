from __future__ import annotations

"""Validate the frozen dashboard GeoJSON contract (#12).

The sample files live in R1's design area; this R3-owned validator keeps the
data shape, WGS84 coordinate order, and value ranges stable before real
dashboard_geo batches replace the mock values.
"""

import json
from pathlib import Path
from typing import Any

from .common import valid_wgs84

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = {
    "accessibility": ROOT / "design" / "samples" / "accessibility.sample.geojson",
    "inflow": ROOT / "design" / "samples" / "inflow.sample.geojson",
}
INFLOW_STATUS = {"확정저유입", "추정후보", "일반", "붐빔"}


def _valid_coordinates(value: Any) -> bool:
    if not isinstance(value, list) or not value:
        return False
    if len(value) == 2 and all(isinstance(item, (int, float)) for item in value):
        return valid_wgs84(float(value[0]), float(value[1]))
    return all(_valid_coordinates(item) for item in value)


def _feature_collection(payload: object, name: str) -> list[dict[str, Any]]:
    if not isinstance(payload, dict) or payload.get("type") != "FeatureCollection":
        raise ValueError(f"{name}: must be a GeoJSON FeatureCollection")
    features = payload.get("features")
    if not isinstance(features, list) or not features:
        raise ValueError(f"{name}: must contain at least one feature")
    return features


def validate(payload: object, name: str) -> int:
    """Validate one frozen dashboard collection and return its feature count."""
    features = _feature_collection(payload, name)
    if name not in SAMPLES:
        raise ValueError(f"unknown dashboard collection: {name}")
    for feature in features:
        if not isinstance(feature, dict) or feature.get("type") != "Feature":
            raise ValueError(f"{name}: every item must be a GeoJSON Feature")
        properties, geometry = feature.get("properties"), feature.get("geometry")
        if not isinstance(properties, dict) or not isinstance(geometry, dict):
            raise ValueError(f"{name}: feature requires properties and geometry")
        geometry_type, coordinates = geometry.get("type"), geometry.get("coordinates")
        if name == "accessibility":
            if geometry_type not in {"Polygon", "MultiPolygon"}:
                raise ValueError("accessibility: geometry must be Polygon or MultiPolygon")
            zone_code = properties.get("zone_code")
            score, quintile = properties.get("score"), properties.get("quintile")
            if not isinstance(zone_code, str) or not (zone_code.startswith("42110") and len(zone_code) == 10 and zone_code.isdigit()):
                raise ValueError("accessibility: zone_code must be a 10-digit Chuncheon code")
            if not isinstance(properties.get("name"), str) or not properties["name"].strip():
                raise ValueError("accessibility: name is required")
            if not isinstance(score, (int, float)) or not 0 <= score <= 100:
                raise ValueError("accessibility: score must be 0..100")
            if not isinstance(quintile, int) or not 1 <= quintile <= 5:
                raise ValueError("accessibility: quintile must be 1..5")
        else:
            if geometry_type != "Point":
                raise ValueError("inflow: geometry must be Point")
            if not all(isinstance(properties.get(key), str) and properties[key].strip() for key in ("name", "category")):
                raise ValueError("inflow: name and category are required")
            if properties.get("inflow_status") not in INFLOW_STATUS:
                raise ValueError("inflow: invalid inflow_status")
        if not _valid_coordinates(coordinates):
            raise ValueError(f"{name}: coordinates must be WGS84 [longitude, latitude]")
    return len(features)


def validate_samples() -> dict[str, int]:
    result: dict[str, int] = {}
    for name, path in SAMPLES.items():
        result[name] = validate(json.loads(path.read_text(encoding="utf-8")), name)
    return result


if __name__ == "__main__":
    print(validate_samples())
