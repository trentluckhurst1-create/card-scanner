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
from card_scanner.models import MarketListing, MatchLevel, SoldComp


class DatabaseMigrationTests(unittest.TestCase):
    def test_market_schema_and_upserts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = str(Path(temp_dir) / "scanner.sqlite3")
            original_settings = db.settings
            db.settings = SimpleNamespace(db_path=db_path)

            try:
                db.init_db()
                market = MarketListing(
                    source="ebay",
                    external_id="v1|123",
                    title="2025 Bowman Draft KYSON WITHERSPOON Chrome Prospect 1st Auto Gold Wave 7/50",
                    url="https://www.ebay.com.au/itm/123",
                    price=100.0,
                    currency="AUD",
                    shipping=10.0,
                    marketplace="EBAY_AU",
                    identity=parse_identity(
                        "2025 Bowman Draft KYSON WITHERSPOON Chrome Prospect 1st Auto Gold Wave 7/50",
                        "MLB",
                    ),
                    landed_price_aud=110.0,
                    fx_status="CONVERTED",
                )
                db.upsert_market_listing(market)
                db.upsert_market_listing(market)

                comp = SoldComp(
                    source="manual",
                    sale_id="S1",
                    sold_date="2026-09-01",
                    title=market.title,
                    sold_price=95.0,
                    currency="AUD",
                    sold_price_aud=95.0,
                    identity=market.identity,
                )
                db.upsert_sold_comp(comp)

                conn = sqlite3.connect(db_path)
                self.assertEqual(
                    conn.execute("SELECT COUNT(*) FROM market_listings").fetchone()[0],
                    1,
                )
                self.assertEqual(
                    conn.execute("SELECT COUNT(*) FROM market_listing_snapshots").fetchone()[0],
                    2,
                )
                self.assertEqual(
                    conn.execute("SELECT COUNT(*) FROM sold_comps").fetchone()[0],
                    1,
                )
                self.assertEqual(MatchLevel.EXACT.value, "EXACT")
                conn.close()
            finally:
                db.settings = original_settings


if __name__ == "__main__":
    unittest.main()
