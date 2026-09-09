from __future__ import annotations

from card_scanner.identity import parse_identity
from card_scanner.listing_history import ListingHistoryAssessment
from card_scanner.market_reference import (
    CrossStoreReference,
    MarketReferenceStatus,
)
from card_scanner.mispricing import assess_mispricing
from card_scanner.models import Listing, Opportunity, SoldValuation
from card_scanner.underdescription import assess_underdescription


def listing(
    title: str,
    price: float = 100.0,
) -> Listing:
    return Listing(
        source="cherry",
        external_id="C1",
        url="https://example.invalid/c1",
        title=title,
        sport="MLB",
        price=price,
        currency="AUD",
        identity=parse_identity(title, "MLB"),
    )


def valued(
    *,
    fair: float = 150.0,
    comps: int = 4,
    exact: int = 4,
    confidence: float = 0.85,
    liquidity: float = 0.5,
    spread: float = 8.0,
    age: float = 12.0,
) -> SoldValuation:
    return SoldValuation(
        source_listing_external_id="C1",
        sold_comp_count=comps,
        exact_comp_count=exact,
        fair_value_aud=fair,
        quick_sale_value_aud=round(fair * 0.85, 2),
        comp_confidence=confidence,
        liquidity_score=liquidity,
        status="VALUED",
        explanation={
            "price_spread_pct": spread,
            "median_absolute_deviation_pct": spread / 4,
            "median_comp_age_days": age,
        },
    )


def opportunity(
    *,
    landed: float = 100.0,
    edge: float = 50.0,
    identity: float = 0.95,
    comp_confidence: float = 0.85,
    liquidity: float = 0.5,
    status: str = "BUY",
) -> Opportunity:
    return Opportunity(
        source_listing_external_id="C1",
        landed_cost_aud=landed,
        fair_value_aud=150.0,
        quick_sale_value_aud=127.5,
        edge_pct=edge,
        opportunity_score=80.0,
        identity_confidence=identity,
        comp_confidence=comp_confidence,
        liquidity_score=liquidity,
        status=status,
    )


def active_reference(
    *,
    discount: float = 30.0,
    status: MarketReferenceStatus = MarketReferenceStatus.REFERENCE_AVAILABLE,
) -> CrossStoreReference:
    return CrossStoreReference(
        candidate_source="cherry",
        candidate_external_id="C1",
        candidate_landed_aud=100.0,
        matched_listing_count=3,
        exact_match_count=3,
        strong_match_count=0,
        source_count=2,
        reference_sources=("sportscardstore", "urbanempire"),
        reference_prices_aud=(130.0, 140.0, 160.0),
        min_reference_price_aud=130.0,
        median_reference_price_aud=140.0,
        max_reference_price_aud=160.0,
        candidate_discount_to_median_pct=discount,
        confidence=0.9,
        active_price_spread_pct=21.43,
        active_mad_pct=7.14,
        candidate_discount_to_lowest_pct=23.08,
        consensus_strength=0.95,
        consensus_level="STRONG",
        status=status,
    )


def history(
    *,
    status: str = "UNCHANGED",
    age_days: int = 3,
    observations: int = 2,
    change_pct: float | None = None,
    drops: int = 0,
) -> ListingHistoryAssessment:
    from datetime import datetime, timezone

    first_seen = datetime(2026, 9, 1, tzinfo=timezone.utc)
    last_seen = datetime(2026, 9, 4, tzinfo=timezone.utc)

    return ListingHistoryAssessment(
        source="cherry",
        external_id="C1",
        history_status=status,
        first_seen_at=first_seen,
        last_seen_at=last_seen,
        age_days=age_days,
        observation_count=observations,
        previous_price=120.0,
        current_price=100.0,
        min_observed_price=100.0,
        max_observed_price=120.0,
        price_change_count=drops,
        price_drop_count=drops,
        price_increase_count=0,
        last_price_change_at=last_seen if change_pct is not None else None,
        price_change_amount=-20.0 if change_pct is not None else None,
        price_change_pct=change_pct,
        latest_price_drop_pct=abs(change_pct) if change_pct and change_pct < 0 else None,
        days_since_price_change=0 if change_pct is not None else None,
        is_new=status == "NEW_LISTING",
        is_price_drop=status == "PRICE_DROP",
        is_price_increase=status == "PRICE_INCREASE",
        is_stale=age_days >= 45,
        is_relisted=status == "RELISTED",
    )


def test_mispricing_score_rewards_evidence_quality_over_raw_edge():
    target = listing(
        "2025 Bowman Draft KYSON WITHERSPOON Chrome Prospect "
        "1st Auto Gold Wave 38/50"
    )
    lower_edge_strong_evidence = assess_mispricing(
        target,
        valued(confidence=0.92, liquidity=0.9, spread=6.0, age=5),
        opportunity(edge=24.0, comp_confidence=0.92, liquidity=0.9),
        [],
    )
    high_edge_weak_evidence = assess_mispricing(
        target,
        valued(comps=3, exact=0, confidence=0.56, liquidity=0.25, spread=95.0, age=160),
        opportunity(edge=46.0, comp_confidence=0.56, liquidity=0.25),
        [],
    )

    assert lower_edge_strong_evidence.score > high_edge_weak_evidence.score
    assert any(
        "sold prices are widely dispersed" in reason
        for reason in high_edge_weak_evidence.why_it_may_be_cheap
    )


def test_insufficient_sold_comps_caps_score_and_explains_suppression():
    target = listing(
        "2020 Panini Prizm PATRICK MAHOMES Lazer Prizm PSA 10",
        price=40.0,
    )
    valuation = SoldValuation(
        source_listing_external_id="C1",
        sold_comp_count=0,
        exact_comp_count=0,
        comp_confidence=0.0,
        liquidity_score=0.0,
        status="INSUFFICIENT_RECENT_COMPS",
    )
    result = assess_mispricing(
        target,
        valuation,
        Opportunity(
            source_listing_external_id="C1",
            landed_cost_aud=40.0,
            identity_confidence=0.9,
            status="INSUFFICIENT_SOLD_COMPS",
        ),
        [],
        active_reference(discount=70.0),
    )

    assert result.score <= 25.0
    assert "genuine sold-comp evidence is insufficient" in result.why_it_may_be_cheap
    assert "sold valuation unavailable" in result.suppressions


def test_active_ask_context_is_reported_but_not_valuation_evidence():
    target = listing(
        "2025 Bowman Draft KYSON WITHERSPOON Chrome Prospect "
        "1st Auto Gold Wave 38/50"
    )
    result = assess_mispricing(
        target,
        valued(),
        opportunity(edge=25.0),
        [],
        active_reference(discount=33.3),
    )

    assert any(
        "cross-store ask is 33.3% below median ask" == reason
        for reason in result.why_it_looks_cheap
    )
    assert any(
        "cross-store active references" in reason
        for reason in result.evidence_flags
    )


def test_price_drop_appears_in_mispricing_explanation():
    target = listing(
        "2025 Bowman Draft KYSON WITHERSPOON Chrome Prospect "
        "1st Auto Gold Wave 38/50"
    )
    result = assess_mispricing(
        target,
        valued(),
        opportunity(edge=25.0),
        [],
        listing_history=history(
            status="PRICE_DROP",
            change_pct=-22.0,
            drops=1,
        ),
    )

    assert "price dropped 22.0% since previous observation" in result.why_it_looks_cheap


def test_stale_apparent_bargain_adds_caution_not_boost():
    target = listing(
        "2025 Bowman Draft KYSON WITHERSPOON Chrome Prospect "
        "1st Auto Gold Wave 38/50"
    )
    fresh = assess_mispricing(
        target,
        valued(),
        opportunity(edge=25.0),
        [],
        listing_history=history(status="NEW_LISTING", age_days=0),
    )
    stale = assess_mispricing(
        target,
        valued(),
        opportunity(edge=25.0),
        [],
        listing_history=history(age_days=60),
    )

    assert stale.score < fresh.score
    assert any(
        "remained active for 60 days" in reason
        for reason in stale.why_it_may_be_cheap
    )


def test_history_cannot_create_high_score_without_sold_value():
    target = listing(
        "2020 Panini Prizm PATRICK MAHOMES Lazer Prizm PSA 10",
        price=40.0,
    )
    valuation = SoldValuation(
        source_listing_external_id="C1",
        sold_comp_count=0,
        exact_comp_count=0,
        comp_confidence=0.0,
        liquidity_score=0.0,
        status="INSUFFICIENT_RECENT_COMPS",
    )

    result = assess_mispricing(
        target,
        valuation,
        Opportunity(
            source_listing_external_id="C1",
            landed_cost_aud=40.0,
            identity_confidence=0.95,
            status="INSUFFICIENT_SOLD_COMPS",
        ),
        [],
        listing_history=history(
            status="PRICE_DROP",
            change_pct=-40.0,
            drops=1,
        ),
    )

    assert result.score <= 25.0
    assert "genuine sold-comp evidence is insufficient" in result.why_it_may_be_cheap

def test_underdescription_penalizes_mispricing_without_changing_opportunity_status():
    clear_listing = listing(
        "2024 Panini Prizm Joe Burrow Gold 7/10 #55"
    )
    poor_listing = listing(
        "2024 Panini Prizm Gold /10 #101"
    )

    clear_opportunity = opportunity(edge=25.0)
    poor_opportunity = opportunity(edge=25.0)

    clear_underdescription = assess_underdescription(clear_listing)
    poor_underdescription = assess_underdescription(poor_listing)

    clear_result = assess_mispricing(
        clear_listing,
        valued(),
        clear_opportunity,
        [],
        underdescription=clear_underdescription,
    )

    poor_result = assess_mispricing(
        poor_listing,
        valued(),
        poor_opportunity,
        [],
        underdescription=poor_underdescription,
    )

    assert clear_underdescription.status == "CLEAR"
    assert poor_underdescription.status == "POOR_IDENTITY"
    assert poor_result.score < clear_result.score

    assert clear_opportunity.status == poor_opportunity.status
    assert poor_opportunity.status not in {"BUY", "STRONG_BUY"} or (
        clear_opportunity.status in {"BUY", "STRONG_BUY"}
    )

    assert any(
        "under-description risk" in reason
        for reason in poor_result.why_it_may_be_cheap
    )
    assert (
        "poor title identity limits confidence in apparent mispricing"
        in poor_result.suppressions
    )


def test_underdescription_does_not_modify_existing_buy_status():
    target = listing(
        "2024 Panini Prizm Gold /10 #101"
    )

    original = Opportunity(
        source_listing_external_id="C1",
        landed_cost_aud=40.0,
        fair_value_aud=100.0,
        quick_sale_value_aud=80.0,
        edge_pct=60.0,
        opportunity_score=90.0,
        identity_confidence=0.95,
        comp_confidence=0.90,
        liquidity_score=0.85,
        risk_score=0.0,
        market_direction="STABLE",
        status="BUY",
    )

    underdescription = assess_underdescription(target)

    assess_mispricing(
        target,
        valued(),
        original,
        [],
        underdescription=underdescription,
    )

    assert original.status == "BUY"

def test_strong_consensus_strengthens_active_market_context():
    target = listing(
        "2025 Bowman Draft KYSON WITHERSPOON Chrome Prospect "
        "1st Auto Gold Wave 38/50"
    )
    reference = active_reference(discount=33.3)

    result = assess_mispricing(
        target,
        valued(),
        opportunity(edge=25.0),
        [],
        reference,
    )

    assert any(
        "active-market consensus strong (0.950)" == flag
        for flag in result.evidence_flags
    )
    assert any(
        "candidate is 23.1% below lowest accepted competing ask" == flag
        for flag in result.evidence_flags
    )


def test_weak_consensus_reduces_active_market_score_and_adds_caution():
    target = listing(
        "2025 Bowman Draft KYSON WITHERSPOON Chrome Prospect "
        "1st Auto Gold Wave 38/50"
    )

    strong = active_reference(discount=40.0)
    weak = CrossStoreReference(
        candidate_source=strong.candidate_source,
        candidate_external_id=strong.candidate_external_id,
        candidate_landed_aud=strong.candidate_landed_aud,
        matched_listing_count=strong.matched_listing_count,
        exact_match_count=strong.exact_match_count,
        strong_match_count=strong.strong_match_count,
        source_count=strong.source_count,
        reference_sources=strong.reference_sources,
        reference_prices_aud=strong.reference_prices_aud,
        min_reference_price_aud=strong.min_reference_price_aud,
        median_reference_price_aud=strong.median_reference_price_aud,
        max_reference_price_aud=strong.max_reference_price_aud,
        candidate_discount_to_median_pct=40.0,
        confidence=strong.confidence,
        active_price_spread_pct=90.0,
        active_mad_pct=45.0,
        candidate_discount_to_lowest_pct=10.0,
        consensus_strength=0.40,
        consensus_level="WEAK",
        status=MarketReferenceStatus.REFERENCE_AVAILABLE,
    )

    strong_result = assess_mispricing(
        target,
        valued(),
        opportunity(edge=25.0),
        [],
        strong,
    )
    weak_result = assess_mispricing(
        target,
        valued(),
        opportunity(edge=25.0),
        [],
        weak,
    )

    assert weak_result.score < strong_result.score
    assert (
        "cross-market active-ask consensus is weak"
        in weak_result.why_it_may_be_cheap
    )


def test_active_consensus_still_cannot_escape_missing_sold_value_cap():
    target = listing(
        "2020 Panini Prizm PATRICK MAHOMES Lazer Prizm PSA 10",
        price=40.0,
    )
    valuation = SoldValuation(
        source_listing_external_id="C1",
        sold_comp_count=0,
        exact_comp_count=0,
        comp_confidence=0.0,
        liquidity_score=0.0,
        status="INSUFFICIENT_RECENT_COMPS",
    )
    reference = active_reference(discount=70.0)

    result = assess_mispricing(
        target,
        valuation,
        Opportunity(
            source_listing_external_id="C1",
            landed_cost_aud=40.0,
            identity_confidence=0.95,
            status="INSUFFICIENT_SOLD_COMPS",
        ),
        [],
        reference,
    )

    assert result.score <= 25.0
    assert "sold valuation unavailable" in result.suppressions
    assert (
        "genuine sold-comp evidence is insufficient"
        in result.why_it_may_be_cheap
    )
