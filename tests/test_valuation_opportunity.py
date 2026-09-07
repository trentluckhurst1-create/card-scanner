from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from card_scanner.identity import parse_identity
from card_scanner.models import Listing, MatchLevel, SoldComp, SoldCompMatch
from card_scanner.opportunity import assess_opportunity
from card_scanner.risk import title_risk_details
from card_scanner.valuation import value_from_sold_comps


def comp(price: float, sold_date: str, sale_id: str = "S") -> tuple[SoldComp, SoldCompMatch]:
    return (
        SoldComp(
            source="manual",
            sale_id=sale_id,
            sold_date=sold_date,
            title="2025 Bowman Draft KYSON WITHERSPOON Chrome Prospect 1st Auto Gold Wave 7/50",
            sold_price=price,
            currency="AUD",
            sold_price_aud=price,
            identity=parse_identity(
                "2025 Bowman Draft KYSON WITHERSPOON Chrome Prospect 1st Auto Gold Wave 7/50",
                "MLB",
            ),
        ),
        SoldCompMatch(
            source_listing_external_id="C1",
            sold_source="manual",
            sale_id=sale_id,
            match_level=MatchLevel.EXACT,
            match_score=0.98,
            match_reasons=["same exact card"],
        ),
    )


class ValuationOpportunityTests(unittest.TestCase):
    def test_insufficient_sold_comps_has_no_fair_value(self):
        valuation = value_from_sold_comps("C1", [comp(120, "2026-09-01", "S1")], as_of=date(2026, 9, 8))

        self.assertEqual(valuation.status, "INSUFFICIENT_SOLD_COMPS")
        self.assertIsNone(valuation.fair_value_aud)

    def test_outlier_resistant_valuation_and_buy_gate(self):
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
        valuation = value_from_sold_comps(
            "C1",
            [
                comp(150, "2026-09-01", "S1"),
                comp(152, "2026-08-20", "S2"),
                comp(149, "2026-08-10", "S3"),
                comp(1000, "2026-08-01", "S4"),
            ],
            as_of=date(2026, 9, 8),
        )

        self.assertEqual(valuation.status, "VALUED")
        self.assertLess(valuation.fair_value_aud, 200)
        opportunity = assess_opportunity(listing, valuation, [])
        self.assertIn(opportunity.status, {"BUY", "STRONG_BUY"})

    def test_high_risk_blocks_buy(self):
        listing = Listing(
            source="cherry",
            external_id="C1",
            url="https://example.invalid/c1",
            title="2025 Bowman Draft KYSON WITHERSPOON Chrome Prospect 1st Auto Gold Wave 38/50 reprint",
            sport="MLB",
            price=100.0,
            currency="AUD",
            identity=parse_identity(
                "2025 Bowman Draft KYSON WITHERSPOON Chrome Prospect 1st Auto Gold Wave 38/50",
                "MLB",
            ),
        )
        valuation = value_from_sold_comps(
            "C1",
            [comp(180, "2026-09-01", "S1"), comp(181, "2026-08-01", "S2"), comp(179, "2026-07-01", "S3")],
            as_of=date(2026, 9, 8),
        )
        opportunity = assess_opportunity(listing, valuation, title_risk_details(listing.title))

        self.assertEqual(opportunity.status, "HIGH_RISK")


if __name__ == "__main__":
    unittest.main()
