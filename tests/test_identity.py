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

    def test_insert_suffix_trimmed_from_player(self):
        identity = parse_identity(
            "2024-25 One and One JA MORANT ISO Auto 36/49",
            "NBA",
        )

        self.assertEqual(identity.player, "Ja Morant")
        self.assertEqual(identity.brand, "Panini One and One")

    def test_audit_discovered_sets_parse(self):
        phoenix = parse_identity(
            "2022 Panini Phoenix KENNY PICKETT Rookie #101 PSA 9 (713)",
            "NFL",
        )
        fleer = parse_identity(
            "2012 Fleer Retro RUSSELL WILSON Rookie Sensations Auto #RS-23 PSA 9 (169)",
            "NFL",
        )

        self.assertEqual(phoenix.brand, "Panini Phoenix")
        self.assertEqual(fleer.brand, "Fleer Retro")
        self.assertEqual(phoenix.player, "Kenny Pickett")
        self.assertEqual(fleer.player, "Russell Wilson")

    def test_live_cherry_initials_and_insert_parallel(self):
        identity = parse_identity(
            "2025 Bowman Draft JD DIX Chrome Aqua Reptilian 93/125 #161",
            "MLB",
        )

        self.assertEqual(identity.player, "JD Dix")
        self.assertEqual(identity.parallel, "Aqua Reptilian")
        self.assertEqual(identity.serial_total, 125)

    def test_more_live_product_families(self):
        limited = parse_identity(
            "2012 Limited RUSSELL WILSON Rookie Phenom Jersey Auto 22/49 #225 PSA 7 (673)",
            "NFL",
        )
        sp = parse_identity(
            "2012 Sp Authentic RUSSELL WILSON Rookie Autograph Patch 567/885 #272 PSA 7 (170)",
            "NFL",
        )
        xfractor = parse_identity(
            "2025 Bowman Draft CADE CROSSLAND 1st Bowman Chrome X-Fractor #183",
            "MLB",
        )

        self.assertEqual(limited.brand, "Limited")
        self.assertEqual(sp.brand, "SP Authentic")
        self.assertEqual(xfractor.parallel, "X-Fractor")


    def test_live_ebay_mahomes_lazer_psa10(self):
        identity = parse_identity(
            "2020 Panini Prizm - PATRICK MAHOMES LAZER PRIZM PSA 10 GEM MT B-10",
            "NFL",
        )

        self.assertEqual(identity.player, "Patrick Mahomes")
        self.assertEqual(identity.year, "2020")
        self.assertEqual(identity.brand, "Panini Prizm")
        self.assertEqual(identity.set_name, "Panini Prizm")
        self.assertEqual(identity.parallel, "Lazer Prizm")
        self.assertEqual(identity.grader, "PSA")
        self.assertEqual(identity.grade, 10.0)

    def test_live_ebay_mahomes_pink_wave_denominator_only(self):
        identity = parse_identity(
            "Patrick Mahomes II 2025 Topps Chrome #148 Pink Wave /250",
            "NFL",
        )

        self.assertEqual(identity.player, "Patrick Mahomes II")
        self.assertEqual(identity.year, "2025")
        self.assertEqual(identity.brand, "Topps Chrome")
        self.assertEqual(identity.set_name, "Topps Chrome")
        self.assertEqual(identity.card_number, "148")
        self.assertEqual(identity.parallel, "Pink Wave")
        self.assertIsNone(identity.serial_current)
        self.assertEqual(identity.serial_total, 250)

    def test_live_ebay_ja_morant_stained_glass_psa8(self):
        identity = parse_identity(
            "2020-21 Panini Mosaic Stained Glass #6 JA MORANT PSA 8",
            "NBA",
        )

        self.assertEqual(identity.player, "Ja Morant")
        self.assertEqual(identity.year, "2020-21")
        self.assertEqual(identity.brand, "Panini Mosaic")
        self.assertEqual(identity.set_name, "Panini Mosaic")
        self.assertEqual(identity.card_number, "6")
        self.assertEqual(identity.parallel, "Stained Glass")
        self.assertEqual(identity.grader, "PSA")
        self.assertEqual(identity.grade, 8.0)

    def test_live_ebay_mixed_case_mahomes_at_front(self):
        identity = parse_identity(
            "Patrick Mahomes II Shadow Etch #SE-1 2025 Topps Chrome Football",
            "NFL",
        )

        self.assertEqual(identity.player, "Patrick Mahomes II")
        self.assertEqual(identity.year, "2025")
        self.assertEqual(identity.brand, "Topps Chrome")
        self.assertEqual(identity.card_number, "SE-1")

    def test_live_ebay_mixed_case_mahomes_after_set(self):
        identity = parse_identity(
            "2021 Panini Clearly Donruss Patrick Mahomes II Retro 1991 #91-12 Chiefs PSA 9",
            "NFL",
        )

        self.assertEqual(identity.player, "Patrick Mahomes II")
        self.assertEqual(identity.year, "2021")
        self.assertEqual(identity.card_number, "91-12")
        self.assertEqual(identity.grader, "PSA")
        self.assertEqual(identity.grade, 9.0)

    def test_denominator_only_serial_does_not_create_numerator(self):
        identity = parse_identity(
            "2025 Topps Chrome Patrick Mahomes II Pink Wave /250 #148",
            "NFL",
        )

        self.assertIsNone(identity.serial_current)
        self.assertEqual(identity.serial_total, 250)

    def test_gimko_expansion_identity_audit_titles(self):
        cases = [
            (
                "NBA",
                "2009 Panini Prestige Chris Bosh Prestigious Pros #36/50 Raptors",
                {
                    "brand": "Panini Prestige",
                    "player": "Chris Bosh",
                    "card_number": "36",
                },
            ),
            (
                "NBA",
                "2009 Upper Deck Draft Edition Dante Cunningham Auto #797/899 Spurs",
                {
                    "brand": "Upper Deck Draft Edition",
                    "player": "Dante Cunningham",
                    "card_number": "797",
                    "autograph": True,
                },
            ),
            (
                "NFL",
                "2015 Panini Playbook Duke Johnson Rookie Dual Jersey 189/199 Cleveland Browns",
                {
                    "brand": "Panini Playbook",
                    "player": "Duke Johnson",
                    "serial_current": 189,
                    "serial_total": 199,
                    "rookie": True,
                    "memorabilia": True,
                },
            ),
            (
                "NFL",
                "2014 Black Gold Demaryius Thomas shadowbox 157/199 Denver BRONCOS",
                {
                    "brand": "Black Gold",
                    "player": "Demaryius Thomas",
                    "parallel": None,
                    "serial_current": 157,
                    "serial_total": 199,
                },
            ),
            (
                "MLB",
                "2000 Bowman Chrome baseball Rocco Baldelli rookie card 91 - Tampa Bay Devil Rays",
                {
                    "brand": "Bowman Chrome",
                    "player": "Rocco Baldelli",
                    "card_number": "91",
                    "rookie": True,
                },
            ),
            (
                "MLB",
                "1998 Upper Deck A Piece of the Action 1 #3 Tony Gwynn Jersey",
                {
                    "brand": "Upper Deck",
                    "player": "Tony Gwynn",
                    "card_number": "3",
                    "memorabilia": True,
                },
            ),
        ]

        for sport, title, expected in cases:
            with self.subTest(title=title):
                identity = parse_identity(title, sport)
                self.assertEqual(identity.sport, sport)

                for field, value in expected.items():
                    self.assertEqual(getattr(identity, field), value)



if __name__ == "__main__":
    unittest.main()
