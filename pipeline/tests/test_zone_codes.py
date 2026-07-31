from __future__ import annotations

import unittest

from pipeline.load.common import normalise_chuncheon_zone_code


class ZoneCodeTests(unittest.TestCase):
    def test_old_chuncheon_prefix_matches_boundary_geojson_prefix(self) -> None:
        self.assertEqual(normalise_chuncheon_zone_code("5111056000"), "4211056000")
        self.assertEqual(normalise_chuncheon_zone_code("51110250"), "4211025000")
        self.assertEqual(normalise_chuncheon_zone_code("42110250"), "4211025000")
        self.assertEqual(normalise_chuncheon_zone_code("4211056000"), "4211056000")
