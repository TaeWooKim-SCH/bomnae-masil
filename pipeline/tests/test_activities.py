from __future__ import annotations

import unittest

from pipeline.load.activities import interest_tags_for


class ActivityInterestMappingTests(unittest.TestCase):
    def test_keyword_mapping_uses_only_the_frozen_chip_enum(self) -> None:
        rules = [
            {"match_type": "genre", "match_value": "행사", "interest_tags": "문화·공연"},
            {"match_type": "title_contains", "match_value": "K-POP", "interest_tags": "운동·건강;문화·공연"},
        ]
        self.assertEqual(interest_tags_for("행사", "STEP UP! K-POP STAGE", rules), ["운동·건강", "문화·공연"])
