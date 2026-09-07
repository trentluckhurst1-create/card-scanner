from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "src"),
)

from card_scanner.identity import parse_identity
from card_scanner.models import MatchLevel, SoldComp
from card_scanner.sold_comp_engine import (
    EphemeralSoldCompEngine,
    assess_strict_sold_comp,
)
from card_scanner.the_card_api import TheCardApiSoldCompProvider


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeHttpClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get(self, url, params=None, headers=None):
        self.calls.append(
            {
                "url": url,
                "params": dict(params or {}),
                "headers": dict(headers or {}),
            }
        )
        return FakeResponse(self.payload)


class QueryProvider:
    persistence_allowed = False

    def __init__(self, exact_results, broad_results=None):
        self.exact_results = exact_results
        self.broad_results = (
            exact_results
            if broad_results is None
            else broad_results
        )
        self.calls = []

    def sold_comps(self, sport, query, limit=50):
        self.calls.append((sport, query, limit))

        if len(self.calls) == 1:
            return list(self.exact_results)

        return list(self.broad_results)


def sold(
    sale_id,
    title,
    price=150.0,
    currency="AUD",
    sold_date="2026-09-08",
):
    return SoldComp(
        source="the_card_api_ebay",
        sale_id=sale_id,
        sold_date=sold_date,
        title=title,
        sold_price=price,
        currency=currency,
        shipping=0.0,
        sold_price_aud=price if currency == "AUD" else None,
        identity=parse_identity(title, "MLB"),
    )


class TheCardApiProviderTests(unittest.TestCase):
    def test_provider_is_explicitly_ephemeral(self):
        provider = TheCardApiSoldCompProvider(
            api_key="tca_test",
            client=FakeHttpClient({"data": []}),
        )

        self.assertFalse(provider.persistence_allowed)
        self.assertFalse(
            provider.raw_response_persistence_allowed
        )

    def test_provider_filters_unconfirmed_and_non_ebay(self):
        payload = {
            "data": [
                {
                    "id": "GOOD",
                    "platform": "ebay",
                    "price_confirmed": True,
                    "title": (
                        "2025 Bowman Draft KYSON WITHERSPOON "
                        "Chrome Prospect 1st Auto Gold Wave 7/50"
                    ),
                    "sale_date": "2026-09-08",
                    "price": 140.0,
                    "currency": "AUD",
                    "listing_type": "best_offer",
                },
                {
                    "id": "ESTIMATE",
                    "platform": "ebay",
                    "price_confirmed": False,
                    "title": "estimate",
                    "sale_date": "2026-09-08",
                    "price": 200.0,
                    "currency": "AUD",
                },
                {
                    "id": "OTHER",
                    "platform": "goldin",
                    "price_confirmed": True,
                    "title": "other platform",
                    "sale_date": "2026-09-08",
                    "price": 300.0,
                    "currency": "AUD",
                },
            ]
        }

        client = FakeHttpClient(payload)
        provider = TheCardApiSoldCompProvider(
            api_key="tca_test",
            client=client,
        )

        comps = provider.sold_comps(
            "MLB",
            "Kyson Witherspoon Bowman Draft Gold Wave",
            50,
        )

        self.assertEqual(len(comps), 1)
        self.assertEqual(comps[0].sale_id, "GOOD")
        self.assertEqual(comps[0].sold_price_aud, 140.0)

        call = client.calls[0]

        self.assertEqual(
            call["params"]["platform"],
            "ebay",
        )
        self.assertEqual(
            call["params"]["category"],
            "sports",
        )
        self.assertEqual(
            call["headers"]["x-market-api-key"],
            "tca_test",
        )
        self.assertIn(
            "-reprint",
            call["params"]["q"],
        )

    def test_foreign_currency_is_not_guessed_as_aud(self):
        payload = {
            "data": [
                {
                    "id": "USD1",
                    "platform": "ebay",
                    "price_confirmed": True,
                    "title": (
                        "2025 Bowman Draft KYSON WITHERSPOON "
                        "Chrome Prospect 1st Auto Gold Wave 7/50"
                    ),
                    "sale_date": "2026-09-08",
                    "price": 100.0,
                    "currency": "USD",
                }
            ]
        }

        provider = TheCardApiSoldCompProvider(
            api_key="tca_test",
            client=FakeHttpClient(payload),
        )

        comp = provider.sold_comps(
            "MLB",
            "Kyson Witherspoon",
            50,
        )[0]

        self.assertEqual(comp.currency, "USD")
        self.assertIsNone(comp.sold_price_aud)


class StrictSoldCompMatchingTests(unittest.TestCase):
    def setUp(self):
        self.source = parse_identity(
            "2025 Bowman Draft KYSON WITHERSPOON "
            "Chrome Prospect 1st Auto Gold Wave 38/50",
            "MLB",
        )

    def test_serial_numerator_does_not_define_identity(self):
        comp = sold(
            "S1",
            "2025 Bowman Draft KYSON WITHERSPOON "
            "Chrome Prospect 1st Auto Gold Wave 7/50",
        )

        match = assess_strict_sold_comp(
            "C1",
            self.source,
            comp,
        )

        self.assertIn(
            match.match_level,
            {MatchLevel.EXACT, MatchLevel.STRONG},
        )

    def test_wrong_print_run_rejected(self):
        comp = sold(
            "S2",
            "2025 Bowman Draft KYSON WITHERSPOON "
            "Chrome Prospect 1st Auto Purple 7/250",
        )

        match = assess_strict_sold_comp(
            "C1",
            self.source,
            comp,
        )

        self.assertEqual(
            match.match_level,
            MatchLevel.REJECT,
        )

    def test_wrong_set_rejected(self):
        comp = sold(
            "S3",
            "2025 Bowman Chrome KYSON WITHERSPOON "
            "Chrome Prospect 1st Auto Gold Wave 7/50",
        )

        match = assess_strict_sold_comp(
            "C1",
            self.source,
            comp,
        )

        self.assertEqual(
            match.match_level,
            MatchLevel.REJECT,
        )

    def test_lot_rejected(self):
        comp = sold(
            "S4",
            "2025 Bowman Draft KYSON WITHERSPOON "
            "Chrome Prospect 1st Auto Gold Wave 7/50 lot",
        )

        match = assess_strict_sold_comp(
            "C1",
            self.source,
            comp,
        )

        self.assertEqual(
            match.match_level,
            MatchLevel.REJECT,
        )


class EphemeralSoldCompEngineTests(unittest.TestCase):
    def setUp(self):
        self.identity = parse_identity(
            "2025 Bowman Draft KYSON WITHERSPOON "
            "Chrome Prospect 1st Auto Gold Wave 38/50",
            "MLB",
        )

    def test_three_recent_exact_comps_can_value(self):
        comps = [
            sold(
                "A",
                "2025 Bowman Draft KYSON WITHERSPOON "
                "Chrome Prospect 1st Auto Gold Wave 1/50",
                150,
            ),
            sold(
                "B",
                "2025 Bowman Draft KYSON WITHERSPOON "
                "Chrome Prospect 1st Auto Gold Wave 2/50",
                155,
            ),
            sold(
                "C",
                "2025 Bowman Draft KYSON WITHERSPOON "
                "Chrome Prospect 1st Auto Gold Wave 3/50",
                152,
            ),
        ]

        provider = QueryProvider(comps)

        result = EphemeralSoldCompEngine(
            provider=provider,
            results_per_query=100,
            recent_days=3,
        ).scan_identity(
            "C1",
            "MLB",
            self.identity,
            as_of=date(2026, 9, 8),
        )

        self.assertEqual(
            result.valuation.status,
            "VALUED",
        )
        self.assertEqual(
            result.accepted_count,
            3,
        )
        self.assertFalse(
            result.persistence_allowed,
        )

    def test_insufficient_depth_never_invents_value(self):
        provider = QueryProvider(
            [
                sold(
                    "A",
                    "2025 Bowman Draft KYSON WITHERSPOON "
                    "Chrome Prospect 1st Auto Gold Wave 1/50",
                    150,
                )
            ]
        )

        result = EphemeralSoldCompEngine(
            provider=provider,
            results_per_query=100,
            recent_days=3,
        ).scan_identity(
            "C1",
            "MLB",
            self.identity,
            as_of=date(2026, 9, 8),
        )

        self.assertEqual(
            result.valuation.status,
            "INSUFFICIENT_RECENT_COMPS",
        )
        self.assertIsNone(
            result.valuation.fair_value_aud,
        )

    def test_older_than_free_window_is_excluded(self):
        provider = QueryProvider(
            [
                sold(
                    "OLD",
                    "2025 Bowman Draft KYSON WITHERSPOON "
                    "Chrome Prospect 1st Auto Gold Wave 1/50",
                    150,
                    sold_date="2026-09-01",
                )
            ]
        )

        result = EphemeralSoldCompEngine(
            provider=provider,
            recent_days=3,
        ).scan_identity(
            "C1",
            "MLB",
            self.identity,
            as_of=date(2026, 9, 8),
        )

        self.assertEqual(
            result.accepted_count,
            0,
        )
        self.assertEqual(
            result.valuation.status,
            "INSUFFICIENT_RECENT_COMPS",
        )


if __name__ == "__main__":
    unittest.main()
