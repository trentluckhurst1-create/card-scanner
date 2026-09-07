from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from card_scanner.identity import parse_identity
from card_scanner.market_matching import assess_match
from card_scanner.models import MatchLevel
from card_scanner.risk import title_risk_flags


class MarketMatchingTests(unittest.TestCase):
    def test_same_card_different_serial_numerator_is_exact(self):
        source = parse_identity(
            "2025 Bowman Draft KYSON WITHERSPOON Chrome Prospect 1st Auto Gold Wave 38/50",
            "MLB",
        )
        candidate = parse_identity(
            "2025 Bowman Draft KYSON WITHERSPOON Chrome Prospect 1st Auto Gold Wave 7/50",
            "MLB",
        )

        self.assertEqual(assess_match(source, candidate).match_level, MatchLevel.EXACT)

    def test_different_serial_denominator_is_not_exact(self):
        source = parse_identity(
            "2025 Bowman Draft KYSON WITHERSPOON Chrome Prospect 1st Auto Gold Wave 38/50",
            "MLB",
        )
        candidate = parse_identity(
            "2025 Bowman Draft KYSON WITHERSPOON Chrome Prospect 1st Auto Purple 7/250",
            "MLB",
        )

        self.assertEqual(assess_match(source, candidate).match_level, MatchLevel.REJECT)

    def test_raw_versus_psa_is_rejected(self):
        source = parse_identity(
            "2020 Panini Prizm ZACK MOSS Rookie Disco 04/10 #343",
            "NFL",
        )
        candidate = parse_identity(
            "2020 Panini Prizm ZACK MOSS Rookie Disco 07/10 #343 PSA 10",
            "NFL",
        )

        self.assertEqual(assess_match(source, candidate).match_level, MatchLevel.REJECT)

    def test_different_parallel_is_rejected(self):
        source = parse_identity(
            "2023 Panini Prizm PATRICK MAHOMES II Purple 44/225 #2 SGC 9.5",
            "NFL",
        )
        candidate = parse_identity(
            "2023 Panini Prizm PATRICK MAHOMES II Gold 3/10 #2 SGC 9.5",
            "NFL",
        )

        self.assertEqual(assess_match(source, candidate).match_level, MatchLevel.REJECT)

    def test_different_player_is_rejected(self):
        source = parse_identity(
            "2025 Flawless Football BHAYSHUL TUTEN Rookie Frame Signatures Auto Ruby 1/15",
            "NFL",
        )
        candidate = parse_identity(
            "2025 Flawless Football ASHTON JEANTY Rookie Frame Signatures Auto Ruby 2/15",
            "NFL",
        )

        self.assertEqual(assess_match(source, candidate).match_level, MatchLevel.REJECT)

    def test_auto_versus_non_auto_is_rejected(self):
        source = parse_identity(
            "2025 Bowman Draft KYSON WITHERSPOON Chrome Prospect 1st Auto Gold Wave 38/50",
            "MLB",
        )
        candidate = parse_identity(
            "2025 Bowman Draft KYSON WITHERSPOON Chrome Prospect 1st Non Auto Gold Wave 7/50",
            "MLB",
        )

        self.assertEqual(assess_match(source, candidate).match_level, MatchLevel.REJECT)

    def test_multi_card_lot_is_rejected(self):
        source = parse_identity(
            "2025 Bowman Draft KYSON WITHERSPOON Chrome Prospect 1st Auto Gold Wave 38/50",
            "MLB",
        )
        candidate_title = (
            "2025 Bowman Draft KYSON WITHERSPOON Chrome Prospect 1st Auto Gold Wave 7/50 lot"
        )
        candidate = parse_identity(candidate_title, "MLB")

        self.assertEqual(
            assess_match(source, candidate, title_risk_flags(candidate_title)).match_level,
            MatchLevel.REJECT,
        )


if __name__ == "__main__":
    unittest.main()
