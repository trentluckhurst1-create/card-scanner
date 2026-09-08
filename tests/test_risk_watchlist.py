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
from card_scanner.models import Listing, SoldValuation
from card_scanner.opportunity import assess_opportunity
from card_scanner.risk import title_risk_details, title_risk_flags
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

    def test_full_team_base_set_is_lot_or_bundle_risk(self):
        title = "Select Footy Stars 2018 - Adelaide Crows Full Team Base Set (w/ Adelaide AFLW)"

        self.assertIn("LOT_OR_BUNDLE", title_risk_flags(title))

    def test_plain_set_name_is_not_risk_by_itself(self):
        title = "2026 Select AFL Footy Stars JASON HORNE-FRANCIS Mercury Green 37/70 #64"

        self.assertNotIn("LOT_OR_BUNDLE", title_risk_flags(title))

    def test_full_team_base_set_cannot_be_buy(self):
        title = "Select Footy Stars 2018 - Adelaide Crows Full Team Base Set (w/ Adelaide AFLW)"
        listing = Listing(
            source="gimko",
            external_id="184230",
            url="https://www.gimko.com.au/item,name,184230,auction_id,auction_details",
            title=title,
            sport="AFL",
            price=2.0,
            currency="AUD",
            shipping=3.0,
            identity=parse_identity(title, "AFL"),
        )
        valuation = SoldValuation(
            source_listing_external_id="184230",
            sold_comp_count=3,
            exact_comp_count=3,
            fair_value_aud=50.0,
            quick_sale_value_aud=42.5,
            liquidity_score=0.7,
            comp_confidence=0.8,
            status="VALUED",
        )

        opportunity = assess_opportunity(
            listing,
            valuation,
            title_risk_details(title),
        )

        self.assertNotIn(opportunity.status, {"BUY", "STRONG_BUY"})
        self.assertIn("LOT_OR_BUNDLE", title_risk_flags(title))


if __name__ == "__main__":
    unittest.main()
