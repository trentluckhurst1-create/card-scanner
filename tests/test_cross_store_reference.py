from card_scanner.cross_store_reference import build_cross_store_reference
from card_scanner.market_reference import MarketReferenceStatus
from card_scanner.models import CardIdentity, Listing


def make_identity(
    *,
    card_number: str = "101",
    serial_current: int | None = 7,
    serial_total: int | None = 50,
) -> CardIdentity:
    return CardIdentity(
        sport="NBA",
        year="2025",
        brand="Panini Prizm",
        player="Example Player",
        card_number=card_number,
        parallel="Gold",
        serial_current=serial_current,
        serial_total=serial_total,
        rookie=True,
        autograph=False,
        memorabilia=False,
    )


def make_listing(
    *,
    source: str,
    external_id: str,
    price: float,
    shipping: float = 0.0,
    title: str = "2025 Panini Prizm Example Player Gold #101 7/50 RC",
    identity: CardIdentity | None = None,
) -> Listing:
    return Listing(
        source=source,
        external_id=external_id,
        url=f"https://example.com/{source}/{external_id}",
        title=title,
        sport="NBA",
        price=price,
        shipping=shipping,
        currency="AUD",
        identity=identity or make_identity(),
    )


def test_reference_available_from_two_independent_stores() -> None:
    candidate = make_listing(
        source="cherry",
        external_id="candidate",
        price=120.0,
    )

    gimko = make_listing(
        source="gimko",
        external_id="g1",
        price=165.0,
        identity=make_identity(serial_current=38),
    )

    sportscardstore = make_listing(
        source="sportscardstore",
        external_id="s1",
        price=160.0,
        shipping=10.0,
        identity=make_identity(serial_current=12),
    )

    result = build_cross_store_reference(
        candidate,
        [gimko, sportscardstore],
    )

    assert result.status is MarketReferenceStatus.REFERENCE_AVAILABLE
    assert result.matched_listing_count == 2
    assert result.exact_match_count == 2
    assert result.strong_match_count == 0
    assert result.source_count == 2
    assert result.reference_sources == ("gimko", "sportscardstore")
    assert result.reference_prices_aud == (165.0, 170.0)
    assert result.min_reference_price_aud == 165.0
    assert result.median_reference_price_aud == 167.5
    assert result.max_reference_price_aud == 170.0
    assert result.candidate_discount_to_median_pct == 28.36
    assert result.confidence > 0.9


def test_one_store_reference_is_insufficient_not_consensus() -> None:
    candidate = make_listing(
        source="cherry",
        external_id="candidate",
        price=120.0,
    )

    reference = make_listing(
        source="gimko",
        external_id="g1",
        price=165.0,
        identity=make_identity(serial_current=38),
    )

    result = build_cross_store_reference(
        candidate,
        [reference],
    )

    assert result.status is MarketReferenceStatus.INSUFFICIENT_REFERENCE
    assert result.matched_listing_count == 1
    assert result.source_count == 1
    assert result.median_reference_price_aud == 165.0


def test_serial_numerator_does_not_define_identity() -> None:
    candidate = make_listing(
        source="cherry",
        external_id="candidate",
        price=100.0,
        identity=make_identity(
            serial_current=7,
            serial_total=50,
        ),
    )

    reference = make_listing(
        source="gimko",
        external_id="g1",
        price=150.0,
        identity=make_identity(
            serial_current=38,
            serial_total=50,
        ),
    )

    result = build_cross_store_reference(
        candidate,
        [reference],
    )

    assert result.matched_listing_count == 1
    assert result.exact_match_count == 1


def test_serial_denominator_mismatch_is_rejected() -> None:
    candidate = make_listing(
        source="cherry",
        external_id="candidate",
        price=100.0,
        identity=make_identity(serial_total=50),
    )

    wrong_parallel = make_listing(
        source="gimko",
        external_id="g1",
        price=150.0,
        identity=make_identity(serial_total=25),
    )

    result = build_cross_store_reference(
        candidate,
        [wrong_parallel],
    )

    assert result.status is MarketReferenceStatus.NO_REFERENCE
    assert result.matched_listing_count == 0


def test_known_card_number_mismatch_is_rejected() -> None:
    candidate = make_listing(
        source="cherry",
        external_id="candidate",
        price=100.0,
        identity=make_identity(card_number="101"),
    )

    wrong_card = make_listing(
        source="gimko",
        external_id="g1",
        price=150.0,
        identity=make_identity(card_number="102"),
    )

    result = build_cross_store_reference(
        candidate,
        [wrong_card],
    )

    assert result.status is MarketReferenceStatus.NO_REFERENCE
    assert result.matched_listing_count == 0


def test_same_store_reference_is_excluded() -> None:
    candidate = make_listing(
        source="cherry",
        external_id="candidate",
        price=100.0,
    )

    same_store_other_item = make_listing(
        source="cherry",
        external_id="other",
        price=150.0,
        identity=make_identity(serial_current=38),
    )

    result = build_cross_store_reference(
        candidate,
        [same_store_other_item],
    )

    assert result.status is MarketReferenceStatus.NO_REFERENCE
    assert result.matched_listing_count == 0


def test_rejecting_bundle_risk_cannot_be_reference() -> None:
    candidate = make_listing(
        source="cherry",
        external_id="candidate",
        price=100.0,
    )

    bundle = make_listing(
        source="gimko",
        external_id="g1",
        price=150.0,
        title="2025 Panini Prizm Example Player Gold #101 /50 full set",
        identity=make_identity(serial_current=38),
    )

    result = build_cross_store_reference(
        candidate,
        [bundle],
    )

    assert result.status is MarketReferenceStatus.NO_REFERENCE
    assert result.matched_listing_count == 0