from __future__ import annotations

"""Build the stop-to-activity accessibility table used by recommendations.

This module is deliberately the only place that determines whether a bus trip
is direct.  Consumers select rows from the generated table; they must not
recalculate route direction, duration, or accessibility at request time.
"""

import json
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from .common import dataset_dir, in_chuncheon_bounds, number, output_dir, read_csv, valid_wgs84, write_csv

ACTIVITY_ALIGHT_RADIUS_M = 500
WALK_METERS_PER_MINUTE = 80  # 4.8 km/h
BUS_KM_PER_HOUR = 18
EARTH_RADIUS_M = 6_371_000
OUTPUT_NAME = "accessibility_scores.csv"

FIELDS = [
    "activity_id",
    "zone_code",
    "board_stop_id",
    "alight_stop_id",
    "score",
    "no_transfer",
    "best_route_id",
    "route_no",
    "stops_count",
    "ride_min",
    "walk_min",
    "duration_min",
]


@dataclass(frozen=True)
class Stop:
    stop_id: str
    longitude: float
    latitude: float
    zone_code: str


@dataclass(frozen=True)
class Activity:
    activity_id: str
    longitude: float
    latitude: float


@dataclass(frozen=True)
class RouteStop:
    route_id: str
    route_no: str
    stop_id: str
    sequence: int
    longitude: float
    latitude: float


@dataclass(frozen=True)
class RouteOption:
    route_id: str
    route_no: str
    alight_stop_id: str
    stops_count: int
    ride_min: int
    walk_min: int

    @property
    def duration_min(self) -> int:
        return self.ride_min + self.walk_min


def haversine_m(lon_a: float, lat_a: float, lon_b: float, lat_b: float) -> float:
    """Return EPSG:4326 point distance in metres."""
    lat_delta = math.radians(lat_b - lat_a)
    lon_delta = math.radians(lon_b - lon_a)
    lat_a_radians = math.radians(lat_a)
    lat_b_radians = math.radians(lat_b)
    value = (
        math.sin(lat_delta / 2) ** 2
        + math.cos(lat_a_radians) * math.cos(lat_b_radians) * math.sin(lon_delta / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(value))


def _point_in_ring(longitude: float, latitude: float, ring: list[list[float]]) -> bool:
    inside = False
    for index, current in enumerate(ring):
        previous = ring[index - 1]
        current_lon, current_lat = current
        previous_lon, previous_lat = previous
        crosses = (current_lat > latitude) != (previous_lat > latitude)
        if crosses:
            intersection = (previous_lon - current_lon) * (latitude - current_lat) / (previous_lat - current_lat) + current_lon
            if longitude < intersection:
                inside = not inside
    return inside


def _point_in_geometry(longitude: float, latitude: float, geometry: dict[str, object]) -> bool:
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates", [])
    polygons = coordinates if geometry_type == "MultiPolygon" else [coordinates]
    for polygon in polygons:
        if not polygon or not _point_in_ring(longitude, latitude, polygon[0]):
            continue
        if not any(_point_in_ring(longitude, latitude, hole) for hole in polygon[1:]):
            return True
    return False


def _load_zones() -> list[tuple[str, dict[str, object]]]:
    snapshots = sorted(dataset_dir().glob("*.geojson"))
    if not snapshots:
        raise FileNotFoundError("Administrative-dong GeoJSON snapshot is required for accessibility scores.")
    raw = json.loads(snapshots[0].read_text(encoding="utf-8"))
    zones: list[tuple[str, dict[str, object]]] = []
    for feature in raw.get("features", []):
        properties = feature.get("properties", {})
        if properties.get("sgg") != "42110":
            continue
        zone_code = str(properties.get("adm_cd2", "")).strip()
        geometry = feature.get("geometry")
        if zone_code and isinstance(geometry, dict):
            zones.append((zone_code, geometry))
    if not zones:
        raise ValueError("No Chuncheon administrative-dong polygons found in GeoJSON snapshot.")
    return zones


def _zone_for_stop(longitude: float, latitude: float, zones: list[tuple[str, dict[str, object]]]) -> str:
    for zone_code, geometry in zones:
        if _point_in_geometry(longitude, latitude, geometry):
            return zone_code
    return ""


def _load_stops() -> dict[str, Stop]:
    zones = _load_zones()
    stops: dict[str, Stop] = {}
    for row in read_csv(output_dir() / "bus_stops.csv"):
        longitude, latitude = number(row.get("longitude")), number(row.get("latitude"))
        stop_id = (row.get("stop_id") or "").strip()
        if not stop_id or not valid_wgs84(longitude, latitude):
            continue
        stops[stop_id] = Stop(stop_id, longitude, latitude, _zone_for_stop(longitude, latitude, zones))
    if not stops:
        raise ValueError("No valid bus stops found. Run pipeline.load.run_all first.")
    return stops


def _load_activities() -> list[Activity]:
    rows: list[dict[str, str]] = []
    geocoded_path = output_dir() / "activities_geocoded.csv"
    if not geocoded_path.is_file():
        raise FileNotFoundError("activities_geocoded.csv is required. Run pipeline.load.geocode_activities first.")
    rows.extend(read_csv(geocoded_path))
    rows.extend(read_csv(output_dir() / "always_open_activities.csv"))

    activities: list[Activity] = []
    seen: set[str] = set()
    for row in rows:
        activity_id = (row.get("activity_id") or "").strip()
        longitude, latitude = number(row.get("longitude")), number(row.get("latitude"))
        if activity_id and activity_id not in seen and in_chuncheon_bounds(longitude, latitude):
            seen.add(activity_id)
            activities.append(Activity(activity_id, longitude, latitude))
    if not activities:
        raise ValueError("No geocoded activities found.")
    return activities


def _load_routes() -> dict[str, list[RouteStop]]:
    routes: dict[str, list[RouteStop]] = defaultdict(list)
    for row in read_csv(output_dir() / "stop_routes.csv"):
        longitude, latitude = number(row.get("longitude")), number(row.get("latitude"))
        try:
            sequence = int(row.get("sequence") or "")
        except ValueError:
            continue
        route_id, route_no, stop_id = (row.get("route_id") or "").strip(), (row.get("route_no") or "").strip(), (row.get("stop_id") or "").strip()
        if not route_id or not route_no or not stop_id or not valid_wgs84(longitude, latitude):
            continue
        routes[route_id].append(RouteStop(route_id, route_no, stop_id, sequence, longitude, latitude))
    for stops in routes.values():
        stops.sort(key=lambda item: item.sequence)
    return routes


def _route_options(
    activity: Activity,
    stops: dict[str, Stop],
    routes: dict[str, list[RouteStop]],
) -> dict[str, list[RouteOption]]:
    nearby_walk_min = {
        stop.stop_id: max(1, math.ceil(haversine_m(stop.longitude, stop.latitude, activity.longitude, activity.latitude) / WALK_METERS_PER_MINUTE))
        for stop in stops.values()
        if haversine_m(stop.longitude, stop.latitude, activity.longitude, activity.latitude) <= ACTIVITY_ALIGHT_RADIUS_M
    }
    options: dict[str, list[RouteOption]] = defaultdict(list)
    if not nearby_walk_min:
        return options

    for route_id, route_stops in routes.items():
        segment_m = [0.0]
        for previous, current in zip(route_stops, route_stops[1:]):
            segment_m.append(segment_m[-1] + haversine_m(previous.longitude, previous.latitude, current.longitude, current.latitude))
        for alight_index, alight in enumerate(route_stops):
            walk_min = nearby_walk_min.get(alight.stop_id)
            if walk_min is None:
                continue
            for board_index, board in enumerate(route_stops[:alight_index]):
                board_stop = stops.get(board.stop_id)
                if board_stop is None:
                    continue
                ride_m = segment_m[alight_index] - segment_m[board_index]
                ride_min = max(1, math.ceil((ride_m / 1_000) / BUS_KM_PER_HOUR * 60))
                options[board.stop_id].append(
                    RouteOption(route_id, alight.route_no, alight.stop_id, alight_index - board_index, ride_min, walk_min)
                )
    return options


def _best_row(activity_id: str, stop: Stop, options: list[RouteOption]) -> dict[str, object]:
    if not options:
        return {
            "activity_id": activity_id, "zone_code": stop.zone_code, "board_stop_id": stop.stop_id,
            "alight_stop_id": "", "score": 0, "no_transfer": False, "best_route_id": "", "route_no": "",
            "stops_count": "", "ride_min": "", "walk_min": "", "duration_min": "",
        }
    best = min(options, key=lambda item: (item.duration_min, item.walk_min, item.stops_count, item.route_no, item.route_id))
    direct_route_count = len({option.route_no for option in options})
    walk_component = max(0.0, 1 - best.walk_min / 15)
    route_component = min(direct_route_count, 5) / 5
    score = round((walk_component * 0.7 + route_component * 0.3) * 100, 2)
    return {
        "activity_id": activity_id, "zone_code": stop.zone_code, "board_stop_id": stop.stop_id,
        "alight_stop_id": best.alight_stop_id, "score": score, "no_transfer": True,
        "best_route_id": best.route_id, "route_no": best.route_no, "stops_count": best.stops_count,
        "ride_min": best.ride_min, "walk_min": best.walk_min, "duration_min": best.duration_min,
    }


def run() -> dict[str, int | float]:
    stops = _load_stops()
    activities = _load_activities()
    routes = _load_routes()
    rows: list[dict[str, object]] = []
    reachable = 0
    for activity in activities:
        options_by_board_stop = _route_options(activity, stops, routes)
        for stop in stops.values():
            row = _best_row(activity.activity_id, stop, options_by_board_stop.get(stop.stop_id, []))
            reachable += int(bool(row["no_transfer"]))
            rows.append(row)
    written = write_csv(OUTPUT_NAME, FIELDS, rows)
    return {
        "stops": len(stops), "activities": len(activities), "written": written,
        "reachable": reachable, "coverage_pct": round(reachable / written * 100, 2) if written else 0.0,
    }


def main() -> None:
    print(json.dumps(run(), ensure_ascii=False))


if __name__ == "__main__":
    main()
