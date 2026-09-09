from __future__ import annotations

from datetime import date

from card_scanner.identity import parse_identity
from card_scanner.models import Listing, SoldComp
from card_scanner.opportunity import assess_opportunity
from card_scanner.sold_evidence_diagnostics import (
    build_sold_evidence_funnel,
    diagnose_sold_evidence_candidate,
    scan_store_sold_evidence_diagnostics,
)


AS_OF = date(2026, 9, 8)


class QueryProvider:
    persistence_allowed = False
    raw_response_persistence_allowed = False

    def __init__(self, rows_by_query=None):
        self.rows_by_query = rows_by_query or {}
        self.calls = []
        self.query_count = 0

    def sold_comps(self, sport, query, limit):
        self.calls.append((sport, query, limit))
        self.query_count += 1
        return list(self.rows_by_query.get(query, []))[:limit]


class FakeStore:
    def __init__(self, rows):
        self.rows = rows

    def search(self, sport, query="", limit=50):
        return [
            row
            for row in self.rows
            if row.sport.upper() == sport.upper()
        ][:limit]


def listing(
    title: str,
    *,
    external_id: str = "C1",
    sport: str = "MLB",
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
    title: str,
    *,
    sport: str = "MLB",
    price: float = 150.0,
    currency: str = "AUD",
    sold_price_aud: float | None = None,
    sold_date: str = "2026-09-07",
    sale_type: str | None = "auction",
    parse: bool = True,
) -> SoldComp:
    return SoldComp(
        source="the_card_api_ebay",
        sale_id=sale_id,
        sold_date=sold_date,
        title=title,
        sold_price=price,
        currency=currency,
        shipping=0.0,
        sold_price_aud=(
            price
            if sold_price_aud is None and currency == "AUD"
            else sold_price_aud
        ),
        sale_type=sale_type,
        identity=parse_identity(title, sport) if parse else None,
    )


def target_listing() -> Listing:
    return listing(
        "2025 Bowman Draft KYSON WITHERSPOON "
        "Chrome Prospect 1st Auto Gold Wave 38/50"
    )


def exact_comp(sale_id: str, price: float = 150.0) -> SoldComp:
    return sold(
        sale_id,
        "2025 Bowman Draft KYSON WITHERSPOON "
        f"Chrome Prospect 1st Auto Gold Wave {sale_id[-1]}/50",
        price=price,
    )


def test_candidate_diagnostics_report_queries_counts_and_price_quality():
    target = target_listing()
    duplicate = exact_comp("S1", 150.0)
    rows = [
        duplicate,
        duplicate,
        exact_comp("S2", 155.0),
        exact_comp("S3", 152.0),
    ]
    provider = QueryProvider({"Kyson Witherspoon": rows})

    result = diagnose_sold_evidence_candidate(
        target,
        provider,
        max_queries=2,
        as_of=AS_OF,
    )

    assert result.queries[0].query_text == "Kyson Witherspoon"
    assert result.queries[0].rows_returned == 4
    assert result.unique_sold_rows == 3
    assert result.rows_with_parseable_identity == 3
    assert result.exact_matches == 3
    assert result.valuation_status == "VALUED"
    assert result.median_aud == 152.0
    assert result.spread_pct is not None
    assert result.median_absolute_deviation_pct is not None
    assert result.persistence_allowed is False


def test_store_diagnostic_respects_global_query_budget_and_stays_read_only():
    first = listing(
        "2020 Panini Prizm PATRICK MAHOMES "
        "Lazer Prizm PSA 10",
        external_id="N1",
        sport="NFL",
    )
    second = target_listing().model_copy(update={"external_id": "M1"})
    provider = QueryProvider()

    summary = scan_store_sold_evidence_diagnostics(
        FakeStore([first, second]),
        provider,
        sport="ALL",
        listings_per_sport=10,
        max_candidates_per_sport=1,
        max_sold_queries=1,
        as_of=AS_OF,
    )

    assert summary.candidates_scanned == 1
    assert summary.sold_api_calls == 1
    assert summary.budget_remaining == 0
    assert summary.persistence_writes == 0
    assert summary.history_writes == 0
    assert summary.raw_api_persistence is False


def test_sold_evidence_funnel_is_reporting_only_and_cumulative():
    target = target_listing()
    exact = exact_comp("S1")
    wrong_year = sold(
        "WY",
        "2024 Bowman Draft KYSON WITHERSPOON "
        "Chrome Prospect 1st Auto Gold Wave 1/50",
    )
    wrong_player = sold(
        "WP",
        "2025 Bowman Draft DIFFERENT PLAYER "
        "Chrome Prospect 1st Auto Gold Wave 1/50",
    )

    funnel = build_sold_evidence_funnel(
        target.external_id,
        target.identity,
        [exact, wrong_year, wrong_player],
    )

    ordered = [
        "UNIQUE_ROWS",
        "IDENTITY_PARSED",
        "SAME_PLAYER",
        "SAME_YEAR",
        "SAME_PRODUCT",
        "SAME_CARD_NUMBER",
        "SAME_PARALLEL",
        "SAME_SERIAL",
        "SAME_ROOKIE",
        "SAME_AUTO_MEM",
        "SAME_GRADING",
    ]

    assert all(
        left >= right
        for left, right in zip(
            [funnel[stage] for stage in ordered],
            [funnel[stage] for stage in ordered][1:],
        )
    )
    assert funnel["API_ROWS"] == 3
    assert funnel["SAME_PLAYER"] == 2
    assert funnel["SAME_YEAR"] == 1
    assert funnel["EXACT"] == 1


def test_rejection_buckets_explain_near_match_failures():
    target = target_listing()
    provider = QueryProvider(
        {
            "Kyson Witherspoon": [
                sold(
                    "WY",
                    "2024 Bowman Draft KYSON WITHERSPOON "
                    "Chrome Prospect 1st Auto Gold Wave 1/50",
                ),
                sold(
                    "WS",
                    "2025 Bowman Chrome KYSON WITHERSPOON "
                    "Chrome Prospect 1st Auto Gold Wave 1/50",
                ),
                sold(
                    "WC",
                    "2025 Bowman Draft KYSON WITHERSPOON "
                    "Chrome Prospect 1st Auto Gold Wave #999 1/50",
                ),
                sold(
                    "WP",
                    "2025 Bowman Draft KYSON WITHERSPOON "
                    "Chrome Prospect 1st Auto Purple 1/250",
                ),
            ]
        }
    )

    result = diagnose_sold_evidence_candidate(
        target,
        provider,
        max_queries=1,
        as_of=AS_OF,
    )

    assert result.bottleneck_counts["PLAYER_RESULTS_BUT_WRONG_YEAR"] == 1
    assert result.bottleneck_counts["WRONG_PRODUCT"] == 1
    assert result.bottleneck_counts["WRONG_SERIAL"] >= 1
    assert result.rejected_examples


def test_stale_sales_and_zero_prices_cannot_create_value_or_buy():
    target = target_listing()
    rows = [
        sold(
            "OLD",
            "2025 Bowman Draft KYSON WITHERSPOON "
            "Chrome Prospect 1st Auto Gold Wave 1/50",
            sold_date="2026-09-01",
        ),
        sold(
            "ZERO",
            "2025 Bowman Draft KYSON WITHERSPOON "
            "Chrome Prospect 1st Auto Gold Wave 2/50",
            price=0.0,
            sold_price_aud=0.0,
        ),
    ]
    provider = QueryProvider({"Kyson Witherspoon": rows})

    result = diagnose_sold_evidence_candidate(
        target,
        provider,
        max_queries=1,
        as_of=AS_OF,
    )
    opportunity = assess_opportunity(target, result.valuation, [])

    assert result.valuation.fair_value_aud is None
    assert result.valuation_status == "INSUFFICIENT_RECENT_COMPS"
    assert opportunity.status == "INSUFFICIENT_SOLD_COMPS"
    assert opportunity.status not in {"BUY", "STRONG_BUY"}
    assert result.bottleneck_counts["RECENCY"] == 1


def test_malformed_sold_title_is_counted_as_identity_parse_failure():
    target = target_listing()
    row = sold(
        "BAD",
        "Mystery card",
        parse=False,
    )

    result = diagnose_sold_evidence_candidate(
        target,
        QueryProvider({"Kyson Witherspoon": [row]}),
        max_queries=1,
        as_of=AS_OF,
    )

    assert result.rows_with_parseable_identity == 0
    assert result.bottleneck_counts["IDENTITY_PARSE_FAILURE"] >= 1
    assert result.valuation.fair_value_aud is None


def test_extreme_outlier_is_audited_without_breaking_robust_value():
    target = target_listing()
    rows = [
        exact_comp("S1", 149.0),
        exact_comp("S2", 150.0),
        exact_comp("S3", 151.0),
        exact_comp("S4", 152.0),
        exact_comp("S5", 153.0),
        exact_comp("S6", 5000.0),
    ]

    result = diagnose_sold_evidence_candidate(
        target,
        QueryProvider({"Kyson Witherspoon": rows}),
        max_queries=1,
        as_of=AS_OF,
    )

    assert result.valuation_status == "VALUED"
    assert result.valuation.fair_value_aud is not None
    assert result.valuation.fair_value_aud < 200.0
    assert result.valuation.explanation["outlier_filtered_count"] == 1


def test_adversarial_near_matches_never_create_valuation_or_buy():
    target = listing(
        "2025 Bowman Draft KYSON WITHERSPOON "
        "Chrome Prospect 1st Auto Gold Wave #101 38/50"
    )
    bad_rows = [
        sold(
            "YEAR",
            "2024 Bowman Draft KYSON WITHERSPOON "
            "Chrome Prospect 1st Auto Gold Wave #101 1/50",
        ),
        sold(
            "PRODUCT",
            "2025 Bowman Chrome KYSON WITHERSPOON "
            "Chrome Prospect 1st Auto Gold Wave #101 1/50",
        ),
        sold(
            "CARD",
            "2025 Bowman Draft KYSON WITHERSPOON "
            "Chrome Prospect 1st Auto Gold Wave #999 1/50",
        ),
        sold(
            "PARALLEL",
            "2025 Bowman Draft KYSON WITHERSPOON "
            "Chrome Prospect 1st Auto Blue Wave #101 1/50",
        ),
        sold(
            "SERIAL",
            "2025 Bowman Draft KYSON WITHERSPOON "
            "Chrome Prospect 1st Auto Gold Wave #101 1/25",
        ),
        sold(
            "RAWGRADED",
            "2025 Bowman Draft KYSON WITHERSPOON "
            "Chrome Prospect 1st Auto Gold Wave #101 1/50 PSA 10",
        ),
        sold(
            "AUTOMISS",
            "2025 Bowman Draft KYSON WITHERSPOON "
            "Chrome Prospect 1st Gold Wave #101 1/50",
        ),
        sold(
            "MEM",
            "2025 Bowman Draft KYSON WITHERSPOON "
            "Chrome Prospect 1st Auto Gold Wave Relic #101 1/50",
        ),
        sold(
            "ROOKIE",
            "2025 Bowman Draft KYSON WITHERSPOON "
            "Chrome Prospect Auto Gold Wave #101 1/50",
        ),
        sold(
            "LOT",
            "2025 Bowman Draft KYSON WITHERSPOON "
            "Chrome Prospect 1st Auto Gold Wave #101 1/50 lot",
        ),
    ]

    result = diagnose_sold_evidence_candidate(
        target,
        QueryProvider({"Kyson Witherspoon": bad_rows}),
        max_queries=1,
        as_of=AS_OF,
    )
    opportunity = assess_opportunity(target, result.valuation, [])

    assert result.accepted_comps == ()
    assert result.valuation.fair_value_aud is None
    assert opportunity.status == "INSUFFICIENT_SOLD_COMPS"
    assert opportunity.status not in {"BUY", "STRONG_BUY"}
    assert result.bottleneck_counts["PLAYER_RESULTS_BUT_WRONG_YEAR"] == 1
    assert result.bottleneck_counts["WRONG_PRODUCT"] >= 1
    assert result.bottleneck_counts["WRONG_SERIAL"] >= 1
    assert result.bottleneck_counts["AUTO_MEM_MISMATCH"] >= 1
    assert result.bottleneck_counts["ROOKIE_MISMATCH"] >= 1


def test_grader_and_grade_mismatches_are_audited():
    target = listing(
        "2025 Bowman Draft KYSON WITHERSPOON "
        "Chrome Prospect 1st Auto Gold Wave 38/50 PSA 10"
    )
    rows = [
        sold(
            "GRADER",
            "2025 Bowman Draft KYSON WITHERSPOON "
            "Chrome Prospect 1st Auto Gold Wave 1/50 BGS 10",
        ),
        sold(
            "GRADE",
            "2025 Bowman Draft KYSON WITHERSPOON "
            "Chrome Prospect 1st Auto Gold Wave 2/50 PSA 9",
        ),
    ]

    result = diagnose_sold_evidence_candidate(
        target,
        QueryProvider({"Kyson Witherspoon": rows}),
        max_queries=1,
        as_of=AS_OF,
    )

    assert result.valuation.fair_value_aud is None
    assert result.bottleneck_counts["GRADING_MISMATCH"] == 2
