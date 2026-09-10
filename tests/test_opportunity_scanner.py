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
    OpportunityScanResult,
    opportunity_result_sort_key,
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

    def test_single_query_budget_scans_candidate(self):
        target = listing(
            "ONE",
            "NFL",
            "2020 Panini Prizm PATRICK MAHOMES Lazer Prizm PSA 10",
        )
        provider = QueryProvider()

        result = scan_cherry_opportunities(
            cherry_source=FakeCherry({"NFL": [target]}),
            sold_provider=provider,
            sport="NFL",
            max_candidates_per_sport=1,
            max_sold_queries=1,
            as_of=AS_OF,
        )

        self.assertEqual(result.candidates_scanned, 1)
        self.assertEqual(result.sold_queries_used, 1)
        self.assertEqual(result.budget_remaining, 0)
        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(provider.calls[0][1], "Patrick Mahomes")

    def test_single_query_budget_suppresses_supplemental_query(self):
        target = listing(
            "ONE-SUPPRESS",
            "MLB",
            "2025 Bowman Draft ALPHA PLAYER Chrome Prospect Auto Gold Wave 1/50",
        )
        provider = QueryProvider()

        result = scan_cherry_opportunities(
            cherry_source=FakeCherry({"MLB": [target]}),
            sold_provider=provider,
            sport="MLB",
            max_candidates_per_sport=1,
            max_sold_queries=1,
            as_of=AS_OF,
        )

        self.assertEqual(result.candidates_scanned, 1)
        self.assertEqual(result.sold_queries_used, 1)
        self.assertEqual(len(provider.calls), 1)

    def test_odd_query_budget_uses_final_single_query(self):
        cards = [
            listing(
                "ODD-A",
                "MLB",
                "2025 Bowman Draft ALPHA PLAYER Chrome Prospect Auto Gold Wave 1/50",
            ),
            listing(
                "ODD-B",
                "MLB",
                "2025 Bowman Draft BETA PLAYER Chrome Prospect Auto Gold Wave 2/50",
            ),
        ]
        provider = QueryProvider()

        result = scan_cherry_opportunities(
            cherry_source=FakeCherry({"MLB": cards}),
            sold_provider=provider,
            sport="MLB",
            max_candidates_per_sport=2,
            max_sold_queries=3,
            as_of=AS_OF,
        )

        self.assertEqual(result.candidates_scanned, 2)
        self.assertEqual(result.sold_queries_used, 3)
        self.assertEqual(result.budget_remaining, 0)
        self.assertEqual(len(provider.calls), 3)

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

    def test_three_exact_comps_can_value_with_one_query_budget(self):
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
            max_sold_queries=1,
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
    assert summary.candidates_considered == 1
    assert summary.candidates_scanned == 1
    assert summary.sold_queries_used == 2
    assert summary.query_budget == 2
    assert summary.budget_remaining == 0
    assert provider.query_count == 2


def test_all_sources_can_be_included_in_multi_store_source():
    from card_scanner.opportunity_scanner import MultiStoreSource, NamedStoreSource

    class FakeStore:
        def __init__(self, source_name, rows):
            self.source_name = source_name
            self.rows = rows

        def search(self, sport, query="", limit=50):
            return [
                row.model_copy(update={"source": self.source_name})
                for row in self.rows[:limit]
            ]

    base = listing(
        "card-1",
        "AFL",
        "2026 Select AFL Footy Stars JASON HORNE-FRANCIS Mercury Green 37/70 #64",
    )

    stores = MultiStoreSource(
        [
            NamedStoreSource("Cherry", FakeStore("cherry", [base])),
            NamedStoreSource("Sports Card Store", FakeStore("sportscardstore", [base])),
            NamedStoreSource("Gimko", FakeStore("gimko", [base])),
            NamedStoreSource("Urban Empire", FakeStore("urbanempire", [base])),
        ]
    )

    rows = stores.search("AFL", limit=5)

    assert [row.source for row in rows] == [
        "cherry",
        "sportscardstore",
        "gimko",
        "urbanempire",
    ]


def test_cli_opportunity_source_dispatch_includes_gimko_and_all():
    from card_scanner.cli import opportunity_store_source
    from card_scanner.opportunity_scanner import MultiStoreSource
    from card_scanner.sources.gimko import GimkoSource
    from card_scanner.sources.urban_empire import UrbanEmpireSource

    gimko_source, gimko_label = opportunity_store_source("gimko")
    urban_source, urban_label = opportunity_store_source("urbanempire")
    all_source, all_label = opportunity_store_source("all")

    assert isinstance(gimko_source, GimkoSource)
    assert gimko_label == "Gimko"
    assert isinstance(urban_source, UrbanEmpireSource)
    assert urban_label == "Urban Empire"
    assert isinstance(all_source, MultiStoreSource)
    assert all_label == "All Stores"
    assert [store.name for store in all_source.stores] == [
        "Cherry",
        "Sports Card Store",
        "Gimko",
        "Urban Empire",
    ]


def test_gimko_unsupported_sport_does_not_break_all_store_fetch():
    from card_scanner.opportunity_scanner import MultiStoreSource, NamedStoreSource
    from card_scanner.sources.gimko import GimkoSource

    class EmptyStore:
        def search(self, sport, query="", limit=50):
            return []

    stores = MultiStoreSource(
        [
            NamedStoreSource("Empty", EmptyStore()),
            NamedStoreSource("Gimko", GimkoSource(client=None)),
        ]
    )

    assert stores.search("CRICKET", limit=5) == []


class CountingStore:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def search(self, sport, query="", limit=50):
        self.calls.append((sport, query, limit))
        return self.rows[:limit]


class BrokenStore:
    def __init__(self):
        self.calls = []

    def search(self, sport, query="", limit=50):
        self.calls.append((sport, query, limit))
        raise RuntimeError("store unavailable")


def reference_ready_listing(source, external_id, price=100.0):
    return listing(
        external_id,
        "NBA",
        "2025 Panini Prizm EXAMPLE PLAYER Gold 7/50 #101 RC",
        price=price,
    ).model_copy(update={"source": source})


def test_multi_store_scan_reuses_one_reference_pool_for_candidates():
    from card_scanner.market_reference import MarketReferenceStatus
    from card_scanner.opportunity_scanner import MultiStoreSource, NamedStoreSource

    cherry = CountingStore([reference_ready_listing("cherry", "c1", 90.0)])
    sportscardstore = CountingStore([
        reference_ready_listing("sportscardstore", "s1", 140.0)
    ])
    gimko = CountingStore([reference_ready_listing("gimko", "g1", 150.0)])
    urban = CountingStore([reference_ready_listing("urbanempire", "u1", 160.0)])

    provider = QueryProvider()

    summary = scan_store_opportunities(
        store_source=MultiStoreSource(
            [
                NamedStoreSource("Cherry", cherry),
                NamedStoreSource("Sports Card Store", sportscardstore),
                NamedStoreSource("Gimko", gimko),
                NamedStoreSource("Urban Empire", urban),
            ]
        ),
        sold_provider=provider,
        sport="NBA",
        listings_per_sport=10,
        max_candidates_per_sport=2,
        sold_results_per_query=100,
        max_sold_queries=4,
        as_of=AS_OF,
    )

    assert cherry.calls == [("NBA", "", 10)]
    assert sportscardstore.calls == [("NBA", "", 10)]
    assert gimko.calls == [("NBA", "", 10)]
    assert urban.calls == [("NBA", "", 10)]
    assert summary.fetched_listings == 4
    assert summary.candidates_considered == 1
    assert summary.candidates_scanned == 1
    assert summary.sold_queries_used == 2
    assert len(provider.calls) == 2
    assert len(summary.results) == 1
    assert summary.results[0].cross_store_reference is not None
    assert (
        summary.results[0].cross_store_reference.status
        is MarketReferenceStatus.REFERENCE_AVAILABLE
    )
    assert summary.results[0].cross_store_reference.matched_listing_count == 3


def test_multi_store_reference_pool_excludes_own_and_same_store_items():
    from card_scanner.market_reference import MarketReferenceStatus
    from card_scanner.opportunity_scanner import MultiStoreSource, NamedStoreSource

    cherry = CountingStore(
        [
            reference_ready_listing("cherry", "candidate", 90.0),
            reference_ready_listing("cherry", "same-store", 120.0),
        ]
    )
    sportscardstore = CountingStore([
        reference_ready_listing("sportscardstore", "s1", 140.0)
    ])
    gimko = CountingStore([reference_ready_listing("gimko", "g1", 150.0)])
    urban = CountingStore([reference_ready_listing("urbanempire", "u1", 160.0)])

    summary = scan_store_opportunities(
        store_source=MultiStoreSource(
            [
                NamedStoreSource("Cherry", cherry),
                NamedStoreSource("Sports Card Store", sportscardstore),
                NamedStoreSource("Gimko", gimko),
                NamedStoreSource("Urban Empire", urban),
            ]
        ),
        sold_provider=QueryProvider(),
        sport="NBA",
        listings_per_sport=10,
        max_candidates_per_sport=1,
        sold_results_per_query=100,
        max_sold_queries=2,
        as_of=AS_OF,
    )

    reference = summary.results[0].cross_store_reference

    assert reference is not None
    assert reference.status is MarketReferenceStatus.REFERENCE_AVAILABLE
    assert reference.matched_listing_count == 3
    assert reference.source_count == 3
    assert "cherry" not in reference.reference_sources


def test_multi_store_source_errors_are_isolated_during_scan():
    from card_scanner.opportunity_scanner import MultiStoreSource, NamedStoreSource

    cherry = CountingStore([reference_ready_listing("cherry", "c1", 90.0)])
    broken = BrokenStore()
    gimko = CountingStore([reference_ready_listing("gimko", "g1", 150.0)])

    summary = scan_store_opportunities(
        store_source=MultiStoreSource(
            [
                NamedStoreSource("Cherry", cherry),
                NamedStoreSource("Broken", broken),
                NamedStoreSource("Gimko", gimko),
            ]
        ),
        sold_provider=QueryProvider(),
        sport="NBA",
        listings_per_sport=10,
        max_candidates_per_sport=1,
        sold_results_per_query=100,
        max_sold_queries=2,
        as_of=AS_OF,
    )

    assert summary.candidates_scanned == 1
    assert len(summary.reference_store_errors) == 1
    assert summary.reference_store_errors[0].startswith(
        "Broken: RuntimeError:"
    )


def test_active_reference_pool_cannot_independently_create_buy():
    from card_scanner.market_reference import MarketReferenceStatus
    from card_scanner.opportunity_scanner import MultiStoreSource, NamedStoreSource

    summary = scan_store_opportunities(
        store_source=MultiStoreSource(
            [
                NamedStoreSource(
                    "Cherry",
                    CountingStore([reference_ready_listing("cherry", "c1", 40.0)]),
                ),
                NamedStoreSource(
                    "Sports Card Store",
                    CountingStore([
                        reference_ready_listing("sportscardstore", "s1", 400.0)
                    ]),
                ),
                NamedStoreSource(
                    "Gimko",
                    CountingStore([reference_ready_listing("gimko", "g1", 420.0)]),
                ),
            ]
        ),
        sold_provider=QueryProvider(),
        sport="NBA",
        listings_per_sport=10,
        max_candidates_per_sport=1,
        sold_results_per_query=100,
        max_sold_queries=2,
        as_of=AS_OF,
    )

    result = summary.results[0]

    assert result.cross_store_reference is not None
    assert (
        result.cross_store_reference.status
        is MarketReferenceStatus.REFERENCE_AVAILABLE
    )
    assert result.valuation.fair_value_aud is None
    assert result.opportunity.status == "INSUFFICIENT_SOLD_COMPS"
    assert result.opportunity.status not in {"BUY", "STRONG_BUY"}


def test_scan_results_include_mispricing_assessment():
    target = listing(
        "KYSON",
        "MLB",
        "2025 Bowman Draft KYSON WITHERSPOON "
        "Chrome Prospect 1st Auto Gold Wave 38/50",
        price=100.0,
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
            152.0,
        ),
        sold(
            "S3",
            "MLB",
            "2025 Bowman Draft KYSON WITHERSPOON "
            "Chrome Prospect 1st Auto Gold Wave 3/50",
            151.0,
        ),
    ]

    result = scan_cherry_opportunities(
        cherry_source=FakeCherry({"MLB": [target]}),
        sold_provider=QueryProvider({"Kyson Witherspoon": rows}),
        sport="MLB",
        max_candidates_per_sport=1,
        max_sold_queries=2,
        as_of=AS_OF,
    ).results[0]

    assert result.mispricing is not None
    assert result.mispricing.score > 0
    assert any(
        "sold fair-value edge" in reason
        for reason in result.mispricing.why_it_looks_cheap
    )


def test_opportunity_sort_uses_mispricing_score_before_raw_edge():
    from card_scanner.mispricing import MispricingAssessment
    from card_scanner.models import Opportunity, SoldValuation

    base_listing = listing(
        "BASE",
        "MLB",
        "2025 Bowman Draft KYSON WITHERSPOON "
        "Chrome Prospect 1st Auto Gold Wave 38/50",
    )

    higher_quality = OpportunityScanResult(
        listing=base_listing,
        identity_quality=0.95,
        player_query=None,
        exact_query=None,
        broad_query=None,
        fetched_count=0,
        accepted_count=0,
        exact_count=0,
        strong_count=0,
        rejected_count=0,
        sold_queries_used=0,
        valuation=SoldValuation(source_listing_external_id="A"),
        opportunity=Opportunity(
            source_listing_external_id="A",
            edge_pct=20.0,
            status="WATCH",
        ),
        mispricing=MispricingAssessment(
            score=80.0,
            why_it_looks_cheap=("strong evidence",),
            why_it_may_be_cheap=(),
            evidence_flags=(),
            suppressions=(),
        ),
    )
    raw_edge_only = OpportunityScanResult(
        listing=base_listing.model_copy(update={"external_id": "RAW"}),
        identity_quality=0.95,
        player_query=None,
        exact_query=None,
        broad_query=None,
        fetched_count=0,
        accepted_count=0,
        exact_count=0,
        strong_count=0,
        rejected_count=0,
        sold_queries_used=0,
        valuation=SoldValuation(source_listing_external_id="B"),
        opportunity=Opportunity(
            source_listing_external_id="B",
            edge_pct=60.0,
            status="WATCH",
        ),
        mispricing=MispricingAssessment(
            score=40.0,
            why_it_looks_cheap=("big raw edge",),
            why_it_may_be_cheap=("weak evidence",),
            evidence_flags=(),
            suppressions=(),
        ),
    )

    assert sorted(
        [raw_edge_only, higher_quality],
        key=opportunity_result_sort_key,
    )[0] is higher_quality

def test_scan_result_exposes_underdescription_assessment():
    target = listing(
        "review-1",
        "NFL",
        "2024 Joe Burrow Gold /10 #55",
        price=50.0,
    )

    summary = scan_store_opportunities(
        store_source=FakeCherry({"NFL": [target]}),
        sold_provider=QueryProvider(),
        sport="NFL",
        listings_per_sport=10,
        max_candidates_per_sport=1,
        sold_results_per_query=10,
        max_sold_queries=2,
    )

    assert len(summary.results) == 1

    result = summary.results[0]

    assert result.identity_quality == 0.75
    assert result.underdescription is not None
    assert result.underdescription.status == "REVIEW"
    assert "MISSING_PRODUCT" in result.underdescription.signal_codes
    assert (
        "SERIAL_WITH_WEAK_IDENTITY"
        in result.underdescription.signal_codes
    )
    assert (
        "CARD_NUMBER_WITH_WEAK_IDENTITY"
        in result.underdescription.signal_codes
    )

    assert result.mispricing is not None
    assert any(
        "under-description risk" in reason
        for reason in result.mispricing.why_it_may_be_cheap
    )

    assert result.opportunity.status not in {"BUY", "STRONG_BUY"}

def test_candidate_budget_deduplicates_serial_numerator_family():
    same_family_expensive = listing(
        "camporeale-39",
        "AFL",
        "2025 Select AFL Seamless BEN CAMPOREALE "
        "Rookie Badge Signature Auto 39/70 #43",
        price=129.99,
    )
    same_family_cheaper = listing(
        "camporeale-42",
        "AFL",
        "2025 Select AFL Seamless BEN CAMPOREALE "
        "Rookie Badge Signature Auto 42/70 #43",
        price=119.99,
    )
    different_family = listing(
        "nicholls-48",
        "AFL",
        "2025 Select AFL Seamless CHARLIE NICHOLLS "
        "Rookie Badge Signature Auto 48/70 #34",
        price=69.99,
    )

    provider = QueryProvider()

    summary = scan_cherry_opportunities(
        cherry_source=FakeCherry(
            {
                "AFL": [
                    same_family_expensive,
                    same_family_cheaper,
                    different_family,
                ]
            }
        ),
        sold_provider=provider,
        sport="AFL",
        max_candidates_per_sport=2,
        max_sold_queries=4,
        as_of=AS_OF,
    )

    assert summary.fetched_listings == 3
    assert summary.candidates_considered == 2
    assert summary.candidates_scanned == 2
    assert summary.sold_queries_used == 4
    assert len(provider.calls) == 4

    researched_players = [
        query
        for _sport, query, _limit in provider.calls
        if query in {"Ben Camporeale", "Charlie Nicholls"}
    ]

    assert "Ben Camporeale" in researched_players
    assert "Charlie Nicholls" in researched_players

    ben_results = [
        result
        for result in summary.results
        if result.listing.identity is not None
        and result.listing.identity.player == "Ben Camporeale"
    ]

    assert len(ben_results) == 1
    assert ben_results[0].listing.external_id == "camporeale-42"
    assert ben_results[0].listing.price == 119.99
