from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import card_scanner.db as db
from card_scanner.identity import parse_identity
from card_scanner.models import Listing
from card_scanner.sold_comps import import_sold_comp_csv


class SoldCompImportTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_settings = db.settings
        db.settings = SimpleNamespace(db_path=str(Path(self.temp_dir.name) / "scanner.sqlite3"))
        db.init_db()
        listing = Listing(
            source="cherry",
            external_id="C1",
            url="https://example.invalid/c1",
            title="2025 Bowman Draft KYSON WITHERSPOON Chrome Prospect 1st Auto Gold Wave 38/50",
            sport="MLB",
            price=100.0,
            currency="AUD",
            identity=parse_identity(
                "2025 Bowman Draft KYSON WITHERSPOON Chrome Prospect 1st Auto Gold Wave 38/50",
                "MLB",
            ),
        )
        db.upsert_listing(listing)

    def tearDown(self):
        db.settings = self.original_settings
        self.temp_dir.cleanup()

    def test_import_validation_and_matching(self):
        csv_path = Path(self.temp_dir.name) / "sold.csv"
        csv_path.write_text(
            "\n".join(
                [
                    "source,sale_id,sold_date,title,sold_price,currency,shipping,sold_price_aud,url,notes",
                    "manual,S1,2026-09-01,2025 Bowman Draft KYSON WITHERSPOON Chrome Prospect 1st Auto Gold Wave 7/50,120,AUD,5,,https://example.invalid/s1,ok",
                    "manual,S1,2026-09-01,duplicate,120,AUD,,,,duplicate",
                    "manual,S2,bad-date,bad,20,AUD,,,,bad",
                    "manual,S3,2026-09-01,foreign,20,USD,,,,fx missing",
                ]
            ),
            encoding="utf-8",
        )

        result = import_sold_comp_csv(csv_path, "MLB")

        self.assertEqual(result.imported, 2)
        self.assertEqual(result.duplicates_in_file, 1)
        self.assertEqual(result.invalid_dates, 1)
        self.assertEqual(result.missing_aud_conversion, 1)
        self.assertEqual(result.matches_saved, 1)

        conn = sqlite3.connect(db.settings.db_path)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM sold_comps").fetchone()[0], 2)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM sold_comp_matches").fetchone()[0], 1)
        conn.close()


if __name__ == "__main__":
    unittest.main()
