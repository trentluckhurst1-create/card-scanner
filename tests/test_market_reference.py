from card_scanner.market_reference import (
    CrossStoreReference,
    MarketReferencePoint,
    MarketReferenceStatus,
)
from card_scanner.models import CardIdentity


def test_market_reference_point_holds_reference_data() -> None:
    identity = CardIdentity(
        sport="NBA",
        year="2025",
        brand="Panini Prizm",
        player="Example Player",
        serial_total=50,
    )

    point = MarketReferencePoint(
        source="example_store",
        external_id="123",
        url="https://example.com/card/123",
        price_aud=100.0,
        shipping_aud=10.0,
        landed_aud=110.0,
        title="2025 Panini Prizm Example Player /50",
        identity=identity,
        match_level="EXACT",
    )

    assert point.source == "example_store"
    assert point.external_id == "123"
    assert point.landed_aud == 110.0
    assert point.identity.serial_total == 50
    assert point.match_level == "EXACT"


def test_cross_store_reference_supports_no_reference_state() -> None:
    reference = CrossStoreReference(
        candidate_source="cherry",
        candidate_external_id="abc",
        candidate_landed_aud=120.0,
        matched_listing_count=0,
        exact_match_count=0,
        strong_match_count=0,
        source_count=0,
        reference_sources=(),
        reference_prices_aud=(),
        min_reference_price_aud=None,
        median_reference_price_aud=None,
        max_reference_price_aud=None,
        candidate_discount_to_median_pct=None,
        confidence=0.0,
        status=MarketReferenceStatus.NO_REFERENCE,
    )

    assert reference.status is MarketReferenceStatus.NO_REFERENCE
    assert reference.reference_prices_aud == ()
    assert reference.median_reference_price_aud is None
    assert reference.confidence == 0.0


def test_cross_store_reference_supports_available_reference_state() -> None:
    reference = CrossStoreReference(
        candidate_source="cherry",
        candidate_external_id="abc",
        candidate_landed_aud=120.0,
        matched_listing_count=2,
        exact_match_count=1,
        strong_match_count=1,
        source_count=2,
        reference_sources=("gimko", "sportscardstore"),
        reference_prices_aud=(165.0, 170.0),
        min_reference_price_aud=165.0,
        median_reference_price_aud=167.5,
        max_reference_price_aud=170.0,
        candidate_discount_to_median_pct=28.3582089552,
        confidence=0.8,
        status=MarketReferenceStatus.REFERENCE_AVAILABLE,
    )

    assert reference.matched_listing_count == 2
    assert reference.source_count == 2
    assert reference.median_reference_price_aud == 167.5
    assert reference.status is MarketReferenceStatus.REFERENCE_AVAILABLE
