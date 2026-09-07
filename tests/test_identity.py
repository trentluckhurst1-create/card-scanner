from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from card_scanner.comp_key import identity_signature
from card_scanner.identity import parse_identity


class IdentityRegressionTests(unittest.TestCase):
    def test_kyson_witherspoon_gold_wave_first_auto(self):
        identity = parse_identity(
            "2025 Bowman Draft KYSON WITHERSPOON Chrome Prospect 1st Auto Gold Wave 38/50",
            "MLB",
        )

        self.assertEqual(identity.player, "Kyson Witherspoon")
        self.assertEqual(identity.parallel, "Gold Wave")
        self.assertEqual(identity.serial_current, 38)
        self.assertEqual(identity.serial_total, 50)
        self.assertTrue(identity.rookie)
        self.assertTrue(identity.autograph)

    def test_fernando_tatis_jr_fuchsia_bgs(self):
        identity = parse_identity(
            "2022 Bowman Chrome FERNANDO TATIS JR. Fuchsia 205/299 #83 BGS 9.5",
            "MLB",
        )

        self.assertEqual(identity.player, "Fernando Tatis Jr.")
        self.assertEqual(identity.parallel, "Fuchsia")
        self.assertEqual(identity.serial_total, 299)
        self.assertEqual(identity.card_number, "83")
        self.assertEqual(identity.grader, "BGS")
        self.assertEqual(identity.grade, 9.5)

    def test_jason_horne_francis_mercury_green(self):
        identity = parse_identity(
            "2026 Select AFL Footy Stars JASON HORNE-FRANCIS Mercury Green 37/70 #64",
            "AFL",
        )

        self.assertEqual(identity.player, "Jason Horne-Francis")
        self.assertEqual(identity.set_name, "Select AFL Footy Stars")
        self.assertEqual(identity.parallel, "Mercury Green")
        self.assertEqual(identity.serial_total, 70)

    def test_bhayshul_tuten_ruby_rookie_auto(self):
        identity = parse_identity(
            "2025 Flawless Football BHAYSHUL TUTEN Rookie Frame Signatures Auto Ruby 1/15",
            "NFL",
        )

        self.assertEqual(identity.player, "Bhayshul Tuten")
        self.assertEqual(identity.parallel, "Ruby")
        self.assertEqual(identity.serial_total, 15)
        self.assertTrue(identity.rookie)
        self.assertTrue(identity.autograph)

    def test_patrick_mahomes_ii_purple_sgc(self):
        identity = parse_identity(
            "2023 Panini Prizm PATRICK MAHOMES II Purple 44/225 #2 SGC 9.5",
            "NFL",
        )

        self.assertEqual(identity.player, "Patrick Mahomes II")
        self.assertEqual(identity.parallel, "Purple")
        self.assertEqual(identity.serial_total, 225)
        self.assertEqual(identity.grader, "SGC")
        self.assertEqual(identity.grade, 9.5)

    def test_zack_moss_disco_psa(self):
        identity = parse_identity(
            "2020 Panini Prizm ZACK MOSS Rookie Disco 04/10 #343 PSA 9",
            "NFL",
        )

        self.assertEqual(identity.player, "Zack Moss")
        self.assertEqual(identity.parallel, "Disco")
        self.assertEqual(identity.serial_total, 10)
        self.assertEqual(identity.grader, "PSA")
        self.assertEqual(identity.grade, 9.0)

    def test_nfl_prefix_removed_from_player(self):
        identity = parse_identity(
            "2025 Panini Prizm NFL ASHTON JEANTY Rookie Ruby 1/15",
            "NFL",
        )

        self.assertEqual(identity.player, "Ashton Jeanty")

    def test_nbl_prefix_removed_from_player(self):
        identity = parse_identity(
            "2024 NBL PEDRO BRADSHAW Prizm Sapphire 3/10",
            "NBA",
        )

        self.assertEqual(identity.player, "Pedro Bradshaw")
        self.assertEqual(identity.parallel, "Sapphire")

    def test_serial_numerator_not_in_identity_signature(self):
        first = parse_identity(
            "2025 Bowman Draft KYSON WITHERSPOON Chrome Prospect 1st Auto Gold Wave 38/50",
            "MLB",
        )
        second = parse_identity(
            "2025 Bowman Draft KYSON WITHERSPOON Chrome Prospect 1st Auto Gold Wave 7/50",
            "MLB",
        )

        self.assertEqual(identity_signature(first), identity_signature(second))


if __name__ == "__main__":
    unittest.main()
