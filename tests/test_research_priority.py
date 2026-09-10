from dataclasses import replace
from datetime import datetime, timezone

from card_scanner.candidate_discovery import assess_candidate_discovery
from card_scanner.identity import parse_identity
from card_scanner.listing_history import ListingHistoryAssessment
from card_scanner.market_reference import CrossStoreReference, MarketReferenceStatus
from card_scanner.models import Listing
from card_scanner.research_priority import (
    assess_research_priority,
    research_priority_sort_key,
)


def listing(title: str, price: float = 100.0) -> Listing:
    return Listing(
        source="test",
        external_id=title,
        url="https://example.invalid/card",
        title=title,
        sport="NBA",
        price=price,
        currency="AUD",
        shipping=0.0,
        identity=parse_identity(title, sport="NBA"),
    )


def active_reference(discount_pct: float = 20.0) -> CrossStoreReference:
    return CrossStoreReference(
        candidate_source="test",
        candidate_external_id="candidate",
        candidate_landed_aud=100.0,
        matched_listing_count=3,
        exact_match_count=3,
        strong_match_count=0,
        source_count=3,
        reference_sources=("store_a", "store_b", "store_c"),
        reference_prices_aud=(120.0, 125.0, 130.0),
        min_reference_price_aud=120.0,
        median_reference_price_aud=125.0,
        max_reference_price_aud=130.0,
        candidate_discount_to_median_pct=discount_pct,
        confidence=0.9,
        status=MarketReferenceStatus.REFERENCE_AVAILABLE,
        active_price_spread_pct=8.0,
        active_mad_pct=10.0,
        candidate_discount_to_lowest_pct=16.67,
        consensus_strength=0.9,
        consensus_level="STRONG",
    )


def price_drop_history(drop_pct: float = -20.0) -> ListingHistoryAssessment:
    now = datetime(2026, 9, 11, tzinfo=timezone.utc)
    return ListingHistoryAssessment(
        source="test",
        external_id="candidate",
        history_status="PRICE_DROP",
        first_seen_at=now,
        last_seen_at=now,
        age_days=5,
        observation_count=3,
        previous_price=125.0,
        current_price=100.0,
        min_observed_price=100.0,
        max_observed_price=125.0,
        price_change_count=1,
        price_drop_count=1,
        price_increase_count=0,
        last_price_change_at=now,
        price_change_amount=-25.0,
        price_change_pct=drop_pct,
        latest_price_drop_pct=drop_pct,
        days_since_price_change=0,
        is_new=False,
        is_price_drop=True,
        is_price_increase=False,
        is_stale=False,
        is_relisted=False,
    )


def strong_discovery():
    row = listing(
        "2023-24 Panini Prizm Victor Wembanyama #136 Silver Prizm RC"
    )
    return assess_candidate_discovery(row)


def test_research_layer_cannot_create_buy_or_fair_value():
    result = assess_research_priority(strong_discovery())

    assert result.can_create_buy is False
    assert result.can_create_strong_buy is False
    assert result.fair_value_aud is None


def test_skip_discovery_stays_skip():
    row = listing(
        "2021 Panini Select Football Hanger Pack Black Gold Prizms"
    )
    discovery = assess_candidate_discovery(row)

    if discovery.discovery_status != "SKIP":
        discovery = replace(
            discovery,
            discovery_status="SKIP",
            discovery_score=0.0,
            sold_comp_ready=False,
        )

    result = assess_research_priority(discovery)

    assert result.priority == "SKIP"
    assert result.score == 0.0
    assert result.can_create_buy is False


def test_higher_discovery_quality_ranks_ahead():
    strong = assess_research_priority(strong_discovery())
    weak_row = listing("Victor Wembanyama Card")
    weak = assess_research_priority(assess_candidate_discovery(weak_row))

    assert strong.score > weak.score
    assert research_priority_sort_key(strong) < research_priority_sort_key(weak)


def test_clean_identity_without_corroboration_is_watch_not_check():
    result = assess_research_priority(strong_discovery())

    assert result.priority == "WATCH"
    assert result.active_reference_signal is False
    assert result.history_signal is False
    assert "NO_STRONG_CORROBORATING_EVIDENCE" in result.cautions


def test_active_reference_can_raise_research_priority_but_not_value():
    result = assess_research_priority(
        strong_discovery(),
        cross_store_reference=active_reference(20.0),
    )

    assert result.priority == "CHECK"
    assert result.active_reference_signal is True
    assert result.fair_value_aud is None
    assert result.can_create_buy is False
    assert result.can_create_strong_buy is False


def test_price_drop_can_raise_research_priority_to_check():
    history = price_drop_history(-20.0)
    result = assess_research_priority(
        strong_discovery(),
        listing_history=history,
    )

    assert result.priority == "CHECK"
    assert result.history_signal is True
    assert "OBSERVED_PRICE_DROP" in result.reasons
    assert result.fair_value_aud is None


def test_check_first_requires_multiple_strong_corroborating_signals():
    result = assess_research_priority(
        strong_discovery(),
        cross_store_reference=active_reference(30.0),
        listing_history=price_drop_history(-20.0),
    )

    assert result.priority == "CHECK_FIRST"
    assert result.active_reference_signal is True
    assert result.history_signal is True
    assert result.fair_value_aud is None
    assert result.can_create_buy is False


def test_score_is_bounded():
    result = assess_research_priority(strong_discovery())

    assert 0.0 <= result.score <= 100.0
