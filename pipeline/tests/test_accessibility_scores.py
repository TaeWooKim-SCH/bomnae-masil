from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from pipeline.load.accessibility_scores import Activity, RouteStop, Stop, _route_options
from pipeline.load.bus_routes import normalise_route_no
from pipeline.load.load_accessibility_scores import REQUIRED_COLUMNS, validate_csv


class AccessibilityScoresTests(unittest.TestCase):
    def test_excel_date_route_label_is_restored(self) -> None:
        self.assertEqual(normalise_route_no("11월 01일"), "11-1")
        self.assertEqual(normalise_route_no("15"), "15")

    def test_only_forward_route_sequence_is_a_direct_trip(self) -> None:
        stops = {
            "stp_a": Stop("stp_a", 127.6900, 37.8700, "42110"),
            "stp_b": Stop("stp_b", 127.6960, 37.8700, "42110"),
            "stp_c": Stop("stp_c", 127.7020, 37.8700, "42110"),
        }
        route = [
            RouteStop("route_1", "1", "stp_a", 1, 127.6900, 37.8700),
            RouteStop("route_1", "1", "stp_b", 2, 127.6960, 37.8700),
            RouteStop("route_1", "1", "stp_c", 3, 127.7020, 37.8700),
        ]
        options = _route_options(Activity("activity_1", 127.7021, 37.8700), stops, {"route_1": route})
        self.assertIn("stp_a", options)
        self.assertEqual(options["stp_a"][0].stops_count, 2)
        self.assertNotIn("stp_c", options)

    def test_loader_rejects_duplicate_matrix_keys(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "scores.csv"
            header = ",".join(REQUIRED_COLUMNS)
            row = "a_1,z_1,stp_1,stp_2,50,True,r_1,1,1,1,1,2"
            path.write_text(f"{header}\n{row}\n{row}\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                validate_csv(path)


if __name__ == "__main__":
    unittest.main()
