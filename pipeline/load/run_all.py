from __future__ import annotations

from . import activities, bus_routes, bus_stops, floating_population, local_currency_merchants, merchants, resident_population, stop_hourly
from .common import dataset_dir, write_report


def main() -> None:
    report = {
        "dataset_dir": str(dataset_dir()),
        "bus_stops": bus_stops.run(),
        "stop_routes": bus_routes.run(),
        "activities": activities.run(),
        "merchants": merchants.run(),
        "local_currency_merchants": local_currency_merchants.run(),
        "floating_population": floating_population.run(),
        "resident_population": resident_population.run(),
        "route_hourly": stop_hourly.run(),
    }
    write_report(report)
    for name, result in report.items():
        if isinstance(result, dict):
            print(f"{name}: {result['written']} written, {result['dropped']} dropped")


if __name__ == "__main__":
    main()
