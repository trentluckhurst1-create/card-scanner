from card_scanner.cross_store_provider import CrossStoreReferenceProvider
from card_scanner.market_reference import MarketReferenceStatus
from card_scanner.models import CardIdentity, Listing
from card_scanner.opportunity_scanner import NamedStoreSource


def make_identity(
    *,
    serial_current: int = 7,
) -> CardIdentity:
    return CardIdentity(
        sport="NBA",
        year="2025",
        brand="Panini Prizm",
        player="Example Player",
        card_number="101",
        parallel="Gold",
        serial_current=serial_current,
        serial_total=50,
        rookie=True,
    )


def make_listing(
    *,
    source: str,
    external_id: str,
    price: float,
    shipping: float = 0.0,
    serial_current: int = 7,
) -> Listing:
    return Listing(
        source=source,
        external_id=external_id,
        url=f"https://example.com/{source}/{external_id}",
        title="2025 Panini Prizm Example Player Gold #101 /50 RC",
        sport="NBA",
        price=price,
        shipping=shipping,
        currency="AUD",
        identity=make_identity(
            serial_current=serial_current,
        ),
    )


class FakeStore:
    def __init__(
        self,
        listings: list[Listing],
    ) -> None:
        self.listings = list(listings)
        self.calls: list[tuple[str, str, int]] = []

    def search(
        self,
        sport: str,
        query: str = "",
        limit: int = 50,
    ) -> list[Listing]:
        self.calls.append(
            (sport, query, limit)
        )

        return self.listings[:limit]


class FailingStore:
    def __init__(self) -> None:
        self.calls = 0

    def search(
        self,
        sport: str,
        query: str = "",
        limit: int = 50,
    ) -> list[Listing]:
        self.calls += 1
        raise RuntimeError("synthetic store failure")


def test_provider_excludes_candidates_own_store() -> None:
    candidate = make_listing(
        source="cherry",
        external_id="candidate",
        price=120.0,
    )

    cherry = FakeStore(
        [
            make_listing(
                source="cherry",
                external_id="c2",
                price=140.0,
            )
        ]
    )

    gimko = FakeStore(
        [
            make_listing(
                source="gimko",
                external_id="g1",
                price=165.0,
                serial_current=38,
            )
        ]
    )

    provider = CrossStoreReferenceProvider(
        stores=[
            NamedStoreSource("cherry", cherry),
            NamedStoreSource("gimko", gimko),
        ],
        listings_per_store=25,
    )

    collected = provider.search(candidate)

    assert cherry.calls == []
    assert gimko.calls == [("NBA", "", 25)]
    assert collected.stores_considered == 1
    assert collected.stores_searched == 1
    assert len(collected.listings) == 1
    assert collected.listings[0].source == "gimko"


def test_assess_builds_reference_from_other_stores() -> None:
    candidate = make_listing(
        source="cherry",
        external_id="candidate",
        price=120.0,
    )

    gimko = FakeStore(
        [
            make_listing(
                source="gimko",
                external_id="g1",
                price=165.0,
                serial_current=38,
            )
        ]
    )

    sportscardstore = FakeStore(
        [
            make_listing(
                source="sportscardstore",
                external_id="s1",
                price=160.0,
                shipping=10.0,
                serial_current=12,
            )
        ]
    )

    provider = CrossStoreReferenceProvider(
        stores=[
            NamedStoreSource("gimko", gimko),
            NamedStoreSource(
                "sportscardstore",
                sportscardstore,
            ),
        ],
        listings_per_store=50,
    )

    result = provider.assess(candidate)

    assert result.stores_considered == 2
    assert result.stores_searched == 2
    assert result.listings_fetched == 2
    assert result.store_errors == ()

    assert (
        result.reference.status
        is MarketReferenceStatus.REFERENCE_AVAILABLE
    )
    assert result.reference.matched_listing_count == 2
    assert result.reference_funnel is not None
    assert result.reference_funnel["CROSS_STORE"] == 2
    assert result.reference_funnel["IDENTITY_PRESENT"] == 2
    assert result.reference_funnel["SAME_PLAYER"] == 2
    assert result.reference_funnel["SAME_YEAR"] == 2
    assert result.reference_funnel["SAME_PRODUCT"] == 2
    assert result.reference_funnel["SAME_CARD_NUMBER"] == 2
    assert result.reference_funnel["SAME_PARALLEL"] == 2
    assert result.reference_funnel["SAME_SERIAL"] == 2
    assert result.reference_funnel["SAME_ROOKIE"] == 2
    assert result.reference_funnel["SAME_AUTO_MEM"] == 2
    assert result.reference_funnel["SAME_GRADING"] == 2
    assert result.reference_funnel["EXACT_STRONG"] == 2
    assert result.reference.source_count == 2
    assert result.reference.median_reference_price_aud == 167.5
    assert (
        result.reference.candidate_discount_to_median_pct
        == 28.36
    )


def test_provider_records_store_failure_without_aborting() -> None:
    candidate = make_listing(
        source="cherry",
        external_id="candidate",
        price=120.0,
    )

    failing = FailingStore()

    gimko = FakeStore(
        [
            make_listing(
                source="gimko",
                external_id="g1",
                price=165.0,
                serial_current=38,
            )
        ]
    )

    provider = CrossStoreReferenceProvider(
        stores=[
            NamedStoreSource("broken", failing),
            NamedStoreSource("gimko", gimko),
        ],
        listings_per_store=50,
    )

    result = provider.assess(candidate)

    assert result.stores_considered == 2
    assert result.stores_searched == 1
    assert result.listings_fetched == 1
    assert len(result.store_errors) == 1
    assert result.store_errors[0].startswith(
        "broken: RuntimeError:"
    )

    assert (
        result.reference.status
        is MarketReferenceStatus.INSUFFICIENT_REFERENCE
    )
    assert result.reference.matched_listing_count == 1


def test_provider_returns_no_reference_when_other_stores_empty() -> None:
    candidate = make_listing(
        source="cherry",
        external_id="candidate",
        price=120.0,
    )

    empty = FakeStore([])

    provider = CrossStoreReferenceProvider(
        stores=[
            NamedStoreSource("gimko", empty),
        ]
    )

    result = provider.assess(candidate)

    assert result.stores_considered == 1
    assert result.stores_searched == 1
    assert result.listings_fetched == 0
    assert result.store_errors == ()

    assert (
        result.reference.status
        is MarketReferenceStatus.NO_REFERENCE
    )

def test_assess_from_pool_does_not_refetch_stores() -> None:
    candidate = make_listing(
        source="cherry",
        external_id="candidate",
        price=120.0,
    )

    gimko_listing = make_listing(
        source="gimko",
        external_id="g1",
        price=165.0,
        serial_current=38,
    )

    sportscardstore_listing = make_listing(
        source="sportscardstore",
        external_id="s1",
        price=160.0,
        shipping=10.0,
        serial_current=12,
    )

    store = FakeStore([])

    provider = CrossStoreReferenceProvider(
        stores=[
            NamedStoreSource("gimko", store),
        ]
    )

    result = provider.assess_from_pool(
        candidate,
        [
            gimko_listing,
            sportscardstore_listing,
        ],
        stores_considered=2,
        stores_searched=2,
    )

    assert store.calls == []
    assert result.stores_considered == 2
    assert result.stores_searched == 2
    assert result.listings_fetched == 2
    assert (
        result.reference.status
        is MarketReferenceStatus.REFERENCE_AVAILABLE
    )
    assert result.reference.matched_listing_count == 2
