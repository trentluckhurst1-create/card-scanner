from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import card_scanner.db as db
from card_scanner.identity import parse_identity
from card_scanner.landed_cost import cherry_landed_cost, market_landed_cost
from card_scanner.market_engine import MarketEngine
from card_scanner.models import Listing, MarketListing


class FailingMarketSource:
    def search_market(self, sport: str, query: str, limit: int = 50):
        raise RuntimeError("provider unavailable")


class ProviderLandedTests(unittest.TestCase):
    def test_provider_not_called_for_insufficient_identity(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            original_settings = db.settings
            db.settings = SimpleNamespace(db_path=str(Path(temp_dir) / "scanner.sqlite3"))
            try:
                db.init_db()
                listing = Listing(
                    source="cherry",
                    external_id="LOW",
                    url="https://example.invalid/low",
                    title="Mystery Card",
                    sport="MLB",
                    price=10.0,
                    currency="AUD",
                    identity=parse_identity("Mystery Card", "MLB"),
                )

                result = MarketEngine(market_source=FailingMarketSource()).scan_listing(listing)

                self.assertEqual(result.metrics.status, "INSUFFICIENT_IDENTITY")
            finally:
                db.settings = original_settings

    def test_cherry_landed_cost_uses_aud_without_fx_guess(self):
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

        self.assertEqual(cherry_landed_cost(listing).landed_cost_aud, 100.0)

    def test_market_landed_cost_requires_shipping_and_fx(self):
        listing = MarketListing(
            source="ebay",
            external_id="E1",
            title="2025 Bowman Draft KYSON WITHERSPOON Chrome Prospect 1st Auto Gold Wave 7/50",
            url="https://example.invalid/e1",
            price=100.0,
            currency="USD",
            shipping=None,
            identity=parse_identity(
                "2025 Bowman Draft KYSON WITHERSPOON Chrome Prospect 1st Auto Gold Wave 7/50",
                "MLB",
            ),
        )

        cost = market_landed_cost(listing)

        self.assertIsNone(cost.landed_cost_aud)
        self.assertEqual(cost.fx_status, "SHIPPING_UNKNOWN")


if __name__ == "__main__":
    unittest.main()
