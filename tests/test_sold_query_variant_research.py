from __future__ import annotations

from datetime import date

from card_scanner.identity import parse_identity
from card_scanner.models import Listing
from card_scanner.sold_comps import SoldComp
from card_scanner.sold_evidence_diagnostics import (
    SoldQueryVariant,
    compare_sold_query_variants,
    diagnose_sold_query_variant,
    diagnose_sold_query_variants,
    generate_sold_query_variants,
)


def _listing(title: str, external_id: str = "candidate-1") -> Listing:
    identity = parse_identity(title, "NBA")
    return Listing(
        source="test-store",
        external_id=external_id,
        url=f"https://example.test/{external_id}",
        title=title,
        sport="NBA",
        price=100.0,
        currency="AUD",
        shipping=0.0,
        identity=identity,
    )


def _sold(title: str, external_id: str, price: float = 100.0) -> SoldComp:
    return SoldComp(
        source="the_card_api",
        sale_id=external_id,
        title=title,
        sport="NBA",
        sold_price=price,
        currency="AUD",
        sold_price_aud=price,
        sold_date=date.today().isoformat(),
        identity=parse_identity(title, "NBA"),
    )


class CountingProvider:
    def __init__(self, rows_by_query=None):
        self.rows_by_query = rows_by_query or {}
        self.query_count = 0
        self.calls = []
        self.cache = {}

    def sold_comps(self, sport, query, limit=100):
        key = (sport.upper(), " ".join(query.casefold().split()), limit)
        if key in self.cache:
            return list(self.cache[key])
        self.query_count += 1
        self.calls.append((sport, query, limit))
        rows = list(self.rows_by_query.get(query, []))
        self.cache[key] = rows
        return list(rows)


def test_generate_variants_contains_controls_and_identity_queries():
    listing = _listing("2023-24 Panini Prizm LeBron James Silver #1 /99 PSA 10")
    variants = generate_sold_query_variants(listing.identity)
    names = {row.name for row in variants}
    assert "Q_PLAYER" in names
    assert "Q_PLAYER_YEAR" in names
    assert "Q_PLAYER_PRODUCT" in names
    assert "Q_PLAYER_YEAR_PRODUCT" in names
    assert "Q_PLAYER_CARDNUM" in names
    assert "Q_PLAYER_PRODUCT_CARDNUM" in names
    assert "Q_PLAYER_YEAR_PRODUCT_CARDNUM" in names
    assert "Q_PLAYER_PARALLEL" in names
    assert "Q_IDENTITY_COMPACT" in names
    assert "Q_EXISTING_BROAD" in names
    assert "Q_EXISTING_EXACT" in names


def test_generate_variants_deduplicates_query_text():
    listing = _listing("2023-24 Panini Prizm LeBron James")
    variants = generate_sold_query_variants(listing.identity)
    keys = [" ".join(row.query_text.casefold().split()) for row in variants]
    assert len(keys) == len(set(keys))


def test_variant_diagnostic_uses_existing_strict_matcher():
    listing = _listing("2023-24 Panini Prizm LeBron James Silver #1 /99 PSA 10")
    variant = SoldQueryVariant("Q_PLAYER", "LeBron James")
    provider = CountingProvider(
        {
            "LeBron James": [
                _sold(
                    "2023-24 Panini Prizm LeBron James Silver #1 /99 PSA 10",
                    "exact-1",
                ),
                _sold(
                    "2022-23 Panini Prizm LeBron James Silver #1 /99 PSA 10",
                    "wrong-year",
                ),
            ]
        }
    )
    row = diagnose_sold_query_variant(listing, provider, variant)
    assert row.api_call_made is True
    assert row.cache_hit is False
    assert row.rows_returned == 2
    assert row.funnel["SAME_PLAYER"] == 2
    assert row.funnel["SAME_YEAR"] == 1
    assert row.funnel["ACCEPTED"] == 1


def test_repeated_identical_query_is_reported_as_cache_hit():
    listing = _listing("2023-24 Panini Prizm LeBron James Silver #1 /99 PSA 10")
    variant = SoldQueryVariant("Q_PLAYER", "LeBron James")
    provider = CountingProvider({"LeBron James": []})
    first = diagnose_sold_query_variant(listing, provider, variant)
    second = diagnose_sold_query_variant(listing, provider, variant)
    assert first.api_call_made is True
    assert first.cache_hit is False
    assert second.api_call_made is False
    assert second.cache_hit is True
    assert provider.query_count == 1


def test_zero_live_call_cap_makes_zero_calls():
    listing = _listing("2023-24 Panini Prizm LeBron James Silver #1 /99 PSA 10")
    provider = CountingProvider()
    summary = diagnose_sold_query_variants(
        (listing,),
        provider,
        live_call_cap=0,
    )
    assert summary.actual_api_calls == 0
    assert provider.query_count == 0


def test_one_live_call_cap_never_overspends():
    listing = _listing("2023-24 Panini Prizm LeBron James Silver #1 /99 PSA 10")
    provider = CountingProvider()
    summary = diagnose_sold_query_variants(
        (listing,),
        provider,
        variant_names=("Q_PLAYER", "Q_PLAYER_YEAR", "Q_PLAYER_PRODUCT"),
        live_call_cap=1,
    )
    assert summary.actual_api_calls <= 1
    assert provider.query_count <= 1


def test_two_live_call_cap_never_overspends():
    listing = _listing("2023-24 Panini Prizm LeBron James Silver #1 /99 PSA 10")
    provider = CountingProvider()
    summary = diagnose_sold_query_variants(
        (listing,),
        provider,
        variant_names=("Q_PLAYER", "Q_PLAYER_YEAR", "Q_PLAYER_PRODUCT"),
        live_call_cap=2,
    )
    assert summary.actual_api_calls <= 2
    assert provider.query_count <= 2


def test_comparison_prefers_identity_aligned_evidence_over_raw_noise():
    listing = _listing("2023-24 Panini Prizm LeBron James Silver #1 /99 PSA 10")
    noisy = SoldQueryVariant("Q_PLAYER", "LeBron James")
    precise = SoldQueryVariant(
        "Q_PLAYER_YEAR_PRODUCT",
        "LeBron James 2023-24 Panini Prizm",
    )
    provider = CountingProvider(
        {
            noisy.query_text: [
                _sold("2022-23 Panini Select LeBron James #5", f"noise-{i}")
                for i in range(5)
            ],
            precise.query_text: [
                _sold(
                    "2023-24 Panini Prizm LeBron James Silver #1 /99 PSA 10",
                    "good-1",
                )
            ],
        }
    )
    d1 = diagnose_sold_query_variant(listing, provider, noisy)
    d2 = diagnose_sold_query_variant(listing, provider, precise)
    comparison = compare_sold_query_variants((d1, d2))
    assert comparison[0].variant == "Q_PLAYER_YEAR_PRODUCT"
    assert comparison[0].accepted > comparison[1].accepted


def test_wrong_product_cannot_become_accepted():
    listing = _listing("2023-24 Panini Prizm LeBron James Silver #1 /99 PSA 10")
    variant = SoldQueryVariant("Q_PLAYER", "LeBron James")
    provider = CountingProvider(
        {
            "LeBron James": [
                _sold(
                    "2023-24 Panini Select LeBron James Silver #1 /99 PSA 10",
                    "wrong-product",
                )
            ]
        }
    )
    row = diagnose_sold_query_variant(listing, provider, variant)
    assert row.funnel["SAME_PLAYER"] == 1
    assert row.funnel["SAME_YEAR"] == 1
    assert row.funnel["SAME_PRODUCT"] == 0
    assert row.funnel["ACCEPTED"] == 0

def _accepted_for(candidate_title: str, sold_title: str) -> int:
    listing = _listing(candidate_title)
    variant = SoldQueryVariant("Q_PLAYER", listing.identity.player)
    provider = CountingProvider(
        {variant.query_text: [_sold(sold_title, "adversarial-1")]}
    )
    row = diagnose_sold_query_variant(listing, provider, variant)
    return row.funnel["ACCEPTED"]


def test_adversarial_wrong_serial_is_not_accepted():
    assert _accepted_for(
        "2023-24 Panini Prizm LeBron James Silver #1 /99 PSA 10",
        "2023-24 Panini Prizm LeBron James Silver #1 /199 PSA 10",
    ) == 0


def test_adversarial_raw_vs_graded_is_not_accepted():
    assert _accepted_for(
        "2023-24 Panini Prizm LeBron James Silver #1 /99 PSA 10",
        "2023-24 Panini Prizm LeBron James Silver #1 /99",
    ) == 0


def test_adversarial_wrong_grader_is_not_accepted():
    assert _accepted_for(
        "2023-24 Panini Prizm LeBron James Silver #1 /99 PSA 10",
        "2023-24 Panini Prizm LeBron James Silver #1 /99 BGS 10",
    ) == 0


def test_adversarial_wrong_grade_is_not_accepted():
    assert _accepted_for(
        "2023-24 Panini Prizm LeBron James Silver #1 /99 PSA 10",
        "2023-24 Panini Prizm LeBron James Silver #1 /99 PSA 9",
    ) == 0


def test_adversarial_auto_mismatch_is_not_accepted():
    assert _accepted_for(
        "2023-24 Panini Prizm LeBron James Silver Auto #1 /99",
        "2023-24 Panini Prizm LeBron James Silver #1 /99",
    ) == 0


def test_adversarial_memorabilia_mismatch_is_not_accepted():
    assert _accepted_for(
        "2023-24 Panini Prizm LeBron James Silver Patch #1 /99",
        "2023-24 Panini Prizm LeBron James Silver #1 /99",
    ) == 0


def test_adversarial_wrong_parallel_is_not_accepted():
    assert _accepted_for(
        "2023-24 Panini Prizm LeBron James Silver #1 /99",
        "2023-24 Panini Prizm LeBron James Gold #1 /99",
    ) == 0


def test_duplicate_query_across_candidates_uses_provider_cache():
    first = _listing(
        "2023-24 Panini Prizm LeBron James Silver #1 /99 PSA 10",
        "candidate-a",
    )
    second = _listing(
        "2023-24 Panini Select LeBron James Silver #2 /99 PSA 10",
        "candidate-b",
    )
    provider = CountingProvider()
    summary = diagnose_sold_query_variants(
        (first, second),
        provider,
        variant_names=("Q_PLAYER",),
        live_call_cap=2,
    )
    assert provider.query_count == 1
    assert summary.actual_api_calls == 1
    assert len(summary.diagnostics) == 2
    assert sum(1 for row in summary.diagnostics if row.api_call_made) == 1
    assert sum(1 for row in summary.diagnostics if row.cache_hit) == 1


def test_live_call_cap_applies_across_multiple_candidates():
    first = _listing(
        "2023-24 Panini Prizm LeBron James Silver #1 /99 PSA 10",
        "candidate-a",
    )
    second = _listing(
        "2023-24 Panini Prizm Stephen Curry Silver #2 /99 PSA 10",
        "candidate-b",
    )
    provider = CountingProvider()
    summary = diagnose_sold_query_variants(
        (first, second),
        provider,
        variant_names=("Q_PLAYER", "Q_PLAYER_YEAR", "Q_PLAYER_PRODUCT"),
        live_call_cap=2,
    )
    assert provider.query_count <= 2
    assert summary.actual_api_calls <= 2


def test_zero_accepted_comps_cannot_be_valued_by_variant_research():
    listing = _listing(
        "2023-24 Panini Prizm LeBron James Silver #1 /99 PSA 10"
    )
    variant = SoldQueryVariant("Q_PLAYER", "LeBron James")
    provider = CountingProvider(
        {
            "LeBron James": [
                _sold(
                    "2022-23 Panini Select LeBron James #5",
                    f"noise-value-{i}",
                )
                for i in range(10)
            ]
        }
    )
    row = diagnose_sold_query_variant(listing, provider, variant)
    assert row.funnel["ACCEPTED"] == 0
    assert row.accepted_comps == ()
