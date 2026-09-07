from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "src"),
)

from card_scanner.identity import parse_identity
from card_scanner.models import Listing, SoldComp
from card_scanner.opportunity_scanner import (
    scan_cherry_opportunities,
    scan_store_opportunities,
)


AS_OF = date(2026, 9, 8)


def listing(
    external_id: str,
    sport: str,
    title: str,
    price: float = 50.0,
) -> Listing:
    return Listing(
        source="cherry",
        external_id=external_id,
        url=f"https://example.invalid/{external_id}",
        title=title,
        sport=sport,
        price=price,
        currency="AUD",
        shipping=0.0,
        identity=parse_identity(title, sport),
    )


def sold(
    sale_id: str,
    sport: str,
    title: str,
    price: float,
) -> SoldComp:
    return SoldComp(
        source="the_card_api_ebay",
        sale_id=sale_id,
        sold_date="2026-09-07",
        title=title,
        sold_price=price,
        currency="AUD",
        sold_price_aud=price,
        identity=parse_identity(title, sport),
    )


class FakeCherry:
    def __init__(self, by_sport):
        self.by_sport = by_sport

    def search(self, sport, query="", limit=50):
        return list(self.by_sport.get(sport, []))[:limit]


class QueryProvider:
    persistence_allowed = False
    raw_response_persistence_allowed = False

    def __init__(self, rows_by_query=None):
        self.rows_by_query = rows_by_query or {}
        self.calls = []

    def sold_comps(self, sport, query, limit):
        self.calls.append((sport, query, limit))
        return list(self.rows_by_query.get(query, []))[:limit]


class OpportunityScannerTests(unittest.TestCase):
    def test_low_identity_uses_zero_queries(self):
        cherry = FakeCherry(
            {
                "NFL": [
                    listing(
                        "LOW",
                        "NFL",
                        "Random Football Card",
                    )
                ]
            }
        )
        provider = QueryProvider()

        result = scan_cherry_opportunities(
            cherry_source=cherry,
            sold_provider=provider,
            sport="NFL",
            max_candidates_per_sport=10,
            max_sold_queries=10,
            as_of=AS_OF,
        )

        self.assertEqual(provider.calls, [])
        self.assertEqual(result.sold_queries_used, 0)
        self.assertEqual(result.candidates_scanned, 0)
        self.assertEqual(result.insufficient_identity_count, 1)

    def test_budget_stops_before_second_candidate(self):
        cards = [
            listing(
                "A",
                "MLB",
                "2025 Bowman Draft ALPHA PLAYER "
                "Chrome Prospect Auto Gold Wave 1/50",
            ),
            listing(
                "B",
                "MLB",
                "2025 Bowman Draft BETA PLAYER "
                "Chrome Prospect Auto Gold Wave 2/50",
            ),
        ]

        result = scan_cherry_opportunities(
            cherry_source=FakeCherry({"MLB": cards}),
            sold_provider=QueryProvider(),
            sport="MLB",
            max_candidates_per_sport=2,
            max_sold_queries=2,
            as_of=AS_OF,
        )

        self.assertEqual(result.candidates_scanned, 1)
        self.assertLessEqual(result.sold_queries_used, 2)
        self.assertGreaterEqual(result.budget_remaining, 0)

    def test_player_first_query_is_used(self):
        target = listing(
            "M",
            "NFL",
            "2020 Panini Prizm PATRICK MAHOMES "
            "Lazer Prizm PSA 10",
        )

        provider = QueryProvider()

        scan_cherry_opportunities(
            cherry_source=FakeCherry({"NFL": [target]}),
            sold_provider=provider,
            sport="NFL",
            max_candidates_per_sport=1,
            max_sold_queries=2,
            as_of=AS_OF,
        )

        self.assertTrue(provider.calls)
        self.assertEqual(
            provider.calls[0][1],
            "Patrick Mahomes",
        )

    def test_three_exact_comps_can_value(self):
        target = listing(
            "KYSON",
            "MLB",
            "2025 Bowman Draft KYSON WITHERSPOON "
            "Chrome Prospect 1st Auto Gold Wave 38/50",
            price=50.0,
        )

        rows = [
            sold(
                "S1",
                "MLB",
                "2025 Bowman Draft KYSON WITHERSPOON "
                "Chrome Prospect 1st Auto Gold Wave 1/50",
                150.0,
            ),
            sold(
                "S2",
                "MLB",
                "2025 Bowman Draft KYSON WITHERSPOON "
                "Chrome Prospect 1st Auto Gold Wave 2/50",
                155.0,
            ),
            sold(
                "S3",
                "MLB",
                "2025 Bowman Draft KYSON WITHERSPOON "
                "Chrome Prospect 1st Auto Gold Wave 3/50",
                152.0,
            ),
        ]

        provider = QueryProvider(
            {
                "Kyson Witherspoon": rows,
            }
        )

        result = scan_cherry_opportunities(
            cherry_source=FakeCherry({"MLB": [target]}),
            sold_provider=provider,
            sport="MLB",
            max_candidates_per_sport=1,
            max_sold_queries=2,
            as_of=AS_OF,
        )

        item = result.results[0]

        self.assertEqual(item.exact_count, 3)
        self.assertEqual(item.valuation.status, "VALUED")
        self.assertIsNotNone(item.valuation.fair_value_aud)

    def test_one_exact_comp_remains_insufficient(self):
        target = listing(
            "ONE",
            "NFL",
            "2020 Panini Prizm PATRICK MAHOMES "
            "Lazer Prizm PSA 10",
            price=50.0,
        )

        row = sold(
            "S1",
            "NFL",
            "2020 Panini Prizm PATRICK MAHOMES "
            "Lazer Prizm PSA 10",
            100.0,
        )

        provider = QueryProvider(
            {
                "Patrick Mahomes": [row],
            }
        )

        result = scan_cherry_opportunities(
            cherry_source=FakeCherry({"NFL": [target]}),
            sold_provider=provider,
            sport="NFL",
            max_candidates_per_sport=1,
            max_sold_queries=2,
            as_of=AS_OF,
        )

        item = result.results[0]

        self.assertEqual(item.exact_count, 1)
        self.assertEqual(
            item.valuation.status,
            "INSUFFICIENT_RECENT_COMPS",
        )
        self.assertEqual(
            item.opportunity.status,
            "INSUFFICIENT_SOLD_COMPS",
        )
        self.assertIsNone(item.valuation.fair_value_aud)

    def test_wrong_sibling_is_rejected(self):
        target = listing(
            "PINK",
            "NFL",
            "2025 Topps Chrome PATRICK MAHOMES II "
            "#148 Pink Wave /250",
        )

        wrong = sold(
            "WRONG",
            "NFL",
            "2025 Topps Chrome PATRICK MAHOMES II "
            "#148 Gold Wave /50",
            300.0,
        )

        provider = QueryProvider(
            {
                "Patrick Mahomes II": [wrong],
            }
        )

        result = scan_cherry_opportunities(
            cherry_source=FakeCherry({"NFL": [target]}),
            sold_provider=provider,
            sport="NFL",
            max_candidates_per_sport=1,
            max_sold_queries=2,
            as_of=AS_OF,
        )

        item = result.results[0]

        self.assertEqual(item.accepted_count, 0)
        self.assertEqual(item.exact_count, 0)
        self.assertEqual(
            item.opportunity.status,
            "INSUFFICIENT_SOLD_COMPS",
        )


if __name__ == "__main__":
    unittest.main()

def test_generic_store_scanner_accepts_non_cherry_source() -> None:
    title = (
        "2020 Panini Prizm PATRICK MAHOMES "
        "Lazer Prizm PSA 10"
    )

    target = listing(
        "store-1",
        "NFL",
        title,
        price=229.0,
    ).model_copy(
        update={"source": "sportscardstore"}
    )

    provider = QueryProvider()

    result = scan_store_opportunities(
        store_source=FakeCherry({"NFL": [target]}),
        sold_provider=provider,
        sport="NFL",
        max_candidates_per_sport=1,
        sold_results_per_query=100,
        max_sold_queries=2,
        as_of=AS_OF,
    )

    assert result.fetched_listings == 1
    assert result.candidates_considered == 1
    assert result.candidates_scanned == 1
    assert result.results[0].listing.source == "sportscardstore"


def test_multi_store_uses_one_shared_sold_query_budget():
    from card_scanner.opportunity_scanner import (
        MultiStoreSource,
        NamedStoreSource,
        scan_store_opportunities,
    )

    class FakeStore:
        def __init__(self, listings):
            self._listings = listings

        def search(self, sport, query="", limit=50):
            return self._listings[:limit]

    class FakeSoldProvider:
        persistence_allowed = False
        raw_response_persistence_allowed = False

        def __init__(self):
            self.query_count = 0

        def sold_comps(self, sport, query, limit):
            self.query_count += 1
            return []

    first = listing(
        "store-a-card",
        "NFL",
        "2020 Panini Prizm PATRICK MAHOMES Lazer Prizm PSA 10",
    ).model_copy(update={"source": "store_a"})

    second = listing(
        "store-b-card",
        "NFL",
        "2020 Panini Prizm PATRICK MAHOMES Lazer Prizm PSA 10",
    ).model_copy(update={
        "source": "store_b",
    })

    stores = MultiStoreSource(
        [
            NamedStoreSource(
                name="Store A",
                source=FakeStore([first]),
            ),
            NamedStoreSource(
                name="Store B",
                source=FakeStore([second]),
            ),
        ]
    )

    provider = FakeSoldProvider()

    summary = scan_store_opportunities(
        store_source=stores,
        sold_provider=provider,
        sport="NFL",
        listings_per_sport=10,
        max_candidates_per_sport=2,
        sold_results_per_query=100,
        max_sold_queries=2,
    )

    assert summary.fetched_listings == 2
    assert summary.candidates_considered == 2
    assert summary.candidates_scanned == 1
    assert summary.sold_queries_used == 2
    assert summary.query_budget == 2
    assert summary.budget_remaining == 0
    assert provider.query_count == 2