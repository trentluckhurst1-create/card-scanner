from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import card_scanner.db as db
from card_scanner.cherry_collector import CherryCollector
from card_scanner.identity import parse_identity
from card_scanner.models import Listing


class FakeCherrySource:
    name = "cherry"

    def __init__(self, pages):
        self.pages = pages

    def _fetch_page(self, sport: str, page: int, page_size: int):
        return self.pages[page - 1] if page - 1 < len(self.pages) else []

    def product_to_listing(self, product: dict, sport: str) -> Listing:
        title = product["title"]
        return Listing(
            source="cherry",
            external_id=str(product["id"]),
            url=f"https://example.invalid/{product['id']}",
            title=title,
            sport=sport,
            price=float(product["price"]),
            currency="AUD",
            shipping=0.0,
            identity=parse_identity(title, sport),
        )


class CherryCollectorTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_settings = db.settings
        db.settings = SimpleNamespace(db_path=str(Path(self.temp_dir.name) / "scanner.sqlite3"))
        db.init_db()

    def tearDown(self):
        db.settings = self.original_settings
        self.temp_dir.cleanup()

    def test_new_listing_and_price_drop_history(self):
        first_source = FakeCherrySource(
            [[
                {
                    "id": "1",
                    "title": "2025 Bowman Draft KYSON WITHERSPOON Chrome Prospect 1st Auto Gold Wave 38/50",
                    "price": "100",
                }
            ]]
        )
        summary = CherryCollector(
            source=first_source,
            page_size=1,
            max_products_per_sport=10,
            cache_minutes=0,
            missing_scan_threshold=3,
        ).scan_sport("MLB")
        self.assertEqual(summary.new, 1)

        second_source = FakeCherrySource(
            [[
                {
                    "id": "1",
                    "title": "2025 Bowman Draft KYSON WITHERSPOON Chrome Prospect 1st Auto Gold Wave 7/50",
                    "price": "80",
                }
            ]]
        )
        summary = CherryCollector(
            source=second_source,
            page_size=1,
            max_products_per_sport=10,
            cache_minutes=0,
            missing_scan_threshold=3,
        ).scan_sport("MLB")
        self.assertEqual(summary.price_drops, 1)

        conn = sqlite3.connect(db.settings.db_path)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM listing_snapshots").fetchone()[0], 2)
        self.assertEqual(
            conn.execute("SELECT event_type FROM listing_events ORDER BY id DESC LIMIT 1").fetchone()[0],
            "PRICE_DROP",
        )
        conn.close()

    def test_missing_scan_threshold_marks_inactive_only_after_threshold(self):
        source = FakeCherrySource(
            [[
                {
                    "id": "1",
                    "title": "2020 Panini Prizm ZACK MOSS Rookie Disco 04/10 #343",
                    "price": "90",
                }
            ]]
        )
        collector = CherryCollector(source=source, page_size=1, cache_minutes=0, missing_scan_threshold=2)
        collector.scan_sport("NFL")

        empty = CherryCollector(source=FakeCherrySource([[]]), page_size=1, cache_minutes=0, missing_scan_threshold=2)
        first_missing = empty.scan_sport("NFL")
        self.assertEqual(first_missing.missing, 1)
        self.assertEqual(first_missing.inactive, 0)

        second_missing = empty.scan_sport("NFL")
        self.assertEqual(second_missing.missing, 1)
        self.assertEqual(second_missing.inactive, 1)

        conn = sqlite3.connect(db.settings.db_path)
        self.assertEqual(conn.execute("SELECT active FROM listings WHERE external_id='1'").fetchone()[0], 0)
        conn.close()


if __name__ == "__main__":
    unittest.main()
