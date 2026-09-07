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
from card_scanner.risk import title_risk_details
from card_scanner.watchlist import add_watch, record_listing_watch_events


class RiskWatchlistTests(unittest.TestCase):
    def test_risk_flags_include_severity_and_reason(self):
        flags = title_risk_details("Patrick Mahomes reprint damaged player lot")
        codes = {flag.code for flag in flags}

        self.assertIn("REPRINT", codes)
        self.assertIn("DAMAGED", codes)
        self.assertIn("LOT_OR_BUNDLE", codes)
        self.assertTrue(all(flag.severity and flag.reason for flag in flags))

    def test_watchlist_records_matching_event(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            original_settings = db.settings
            db.settings = SimpleNamespace(db_path=str(Path(temp_dir) / "scanner.sqlite3"))
            try:
                db.init_db()
                watch_id = add_watch("player", "Kyson Witherspoon", "MLB")
                listing = Listing(
                    source="cherry",
                    external_id="C1",
                    url="https://example.invalid/c1",
                    title="2025 Bowman Draft KYSON WITHERSPOON Chrome Prospect 1st Auto Gold Wave 38/50",
                    sport="MLB",
                    price=100,
                    currency="AUD",
                    identity=parse_identity(
                        "2025 Bowman Draft KYSON WITHERSPOON Chrome Prospect 1st Auto Gold Wave 38/50",
                        "MLB",
                    ),
                )
                record_listing_watch_events(listing, "PRICE_DROP")
                conn = sqlite3.connect(db.settings.db_path)
                self.assertEqual(conn.execute("SELECT watch_item_id FROM watch_events").fetchone()[0], watch_id)
                conn.close()
            finally:
                db.settings = original_settings


if __name__ == "__main__":
    unittest.main()
