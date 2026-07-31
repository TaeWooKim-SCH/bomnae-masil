from __future__ import annotations

"""Build and load the two frozen dashboard GeoJSON collections from DB data."""

import json
from datetime import datetime

from .accessibility_scores import _load_zones
from .dashboard_geo import validate
from .load_source_data import database_url


def build() -> dict[str, dict]:
    import psycopg2
    zones = _load_zones()
    with psycopg2.connect(database_url()) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT zone_code, avg(score) FROM accessibility_scores WHERE no_transfer = TRUE GROUP BY zone_code")
            scores = {code: float(score) for code, score in cursor.fetchall()}
            cursor.execute("SELECT name, category, inflow_status, longitude, latitude FROM merchants")
            merchants = cursor.fetchall()
    ordered = sorted(scores, key=scores.get, reverse=True)
    quintile = {code: min(5, index * 5 // max(1, len(ordered)) + 1) for index, code in enumerate(ordered)}
    names = _zone_names()
    accessibility = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"zone_code": code, "name": names.get(code, code), "score": round(scores.get(code, 0), 2), "quintile": quintile.get(code, 5)}, "geometry": geometry}
        for code, geometry in zones
    ]}
    inflow = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"name": name, "category": category, "inflow_status": status}, "geometry": {"type": "Point", "coordinates": [float(lon), float(lat)]}}
        for name, category, status, lon, lat in merchants
    ]}
    validate(accessibility, "accessibility"); validate(inflow, "inflow")
    return {"accessibility": accessibility, "inflow": inflow}


def _zone_names() -> dict[str, str]:
    import json
    from .common import dataset_dir
    raw = json.loads(sorted(dataset_dir().glob("*.geojson"))[0].read_text(encoding="utf-8"))
    return {str(f["properties"].get("adm_cd2")): str(f["properties"].get("adm_nm") or f["properties"].get("name") or f["properties"].get("adm_cd2")) for f in raw["features"] if f["properties"].get("sgg") == "42110"}


def load() -> dict[str, int]:
    import psycopg2
    collections = build()
    with psycopg2.connect(database_url()) as connection:
        with connection.cursor() as cursor:
            for name, geojson in collections.items():
                cursor.execute("INSERT INTO dashboard_geo (name, geojson, created_at) VALUES (%s, %s::jsonb, %s) ON CONFLICT (name) DO UPDATE SET geojson=EXCLUDED.geojson, created_at=EXCLUDED.created_at", (name, json.dumps(geojson, ensure_ascii=False), datetime.now()))
    return {name: len(value["features"]) for name, value in collections.items()}


if __name__ == "__main__": print(load())
