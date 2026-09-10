from __future__ import annotations

from types import SimpleNamespace

from card_scanner.dashboard_export import build_dashboard_payload
from card_scanner.market_catalogue import (
    MarketListingObservation,
    capture_store_source,
    catalogue_observations,
)
from card_scanner.models import CardIdentity, Listing
from card_scanner.opportunity_scanner import MultiStoreSource, NamedStoreSource


class FakeStore:
    def __init__(self, source: str, price: float) -> None:
        self.source = source
        self.price = price
        self.calls = 0

    def search(self, sport: str, query: str = "", limit: int = 50):
        self.calls += 1
        identity = CardIdentity(
            sport=sport,
            year="2023",
            brand="Panini",
            set_name="Prizm",
            player="Victor Wembanyama",
            card_number="136",
            parallel="Silver",
            rookie=True,
        )
        return [
            Listing(
                source=self.source,
                external_id=f"{self.source}-1",
                url=f"https://example.test/{self.source}",
                title="2023 Panini Prizm Victor Wembanyama Silver RC #136",
                sport=sport,
                price=self.price,
                shipping=10.0,
                currency="AUD",
                identity=identity,
            )
        ]


def _summary(*, fetched: int, results=()):
    return SimpleNamespace(
        fetched_listings=fetched,
        candidates_scanned=len(results),
        valued_count=0,
        strong_buy_count=0,
        buy_count=0,
        watch_count=0,
        insufficient_comps_count=len(results),
        insufficient_identity_count=0,
        sold_queries_used=0,
        history_observed_count=fetched,
        history_new_count=0,
        history_price_drop_count=0,
        history_price_increase_count=0,
        history_relisted_count=0,
        history_stale_count=0,
        results=list(results),
    )


def test_single_store_capture_does_not_refetch_for_catalogue():
    store = FakeStore("Cherry", 200.0)
    captured = capture_store_source(store)

    rows = captured.search("NBA", limit=30)
    observations = catalogue_observations(captured, include_history=False)

    assert len(rows) == 1
    assert len(observations) == 1
    assert store.calls == 1


def test_multi_store_capture_preserves_multi_store_type_and_no_refetch():
    cherry = FakeStore("Cherry", 200.0)
    gimko = FakeStore("Gimko", 180.0)
    raw = MultiStoreSource(
        [
            NamedStoreSource("Cherry", cherry),
            NamedStoreSource("Gimko", gimko),
        ]
    )
    captured = capture_store_source(raw)

    assert isinstance(captured, MultiStoreSource)
    collection = captured.collect("NBA", limit=30)
    observations = catalogue_observations(captured, include_history=False)

    assert len(collection.listings) == 2
    assert len(observations) == 2
    assert cherry.calls == 1
    assert gimko.calls == 1


def test_full_market_export_is_separate_from_deep_research_and_drives_families():
    cherry = FakeStore("Cherry", 200.0).search("NBA")[0]
    gimko = FakeStore("Gimko", 180.0).search("NBA")[0]
    observations = [
        MarketListingObservation(cherry),
        MarketListingObservation(gimko),
    ]

    payload = build_dashboard_payload(
        _summary(fetched=2),
        generated_at="2026-09-11T00:00:00+00:00",
        market_listings=observations,
    )

    assert payload["metrics"]["market_cards"] == 2
    assert payload["market_cards"] and len(payload["market_cards"]) == 2
    assert payload["cards"] == []
    assert payload["metrics"]["cross_store_families"] == 1
    assert payload["cross_store_families"][0]["stores"] == ["Cherry", "Gimko"]

    for card in payload["market_cards"]:
        assert card["research_status"] == "NOT_RESEARCHED_IN_THIS_SCAN"
        assert "valuation" not in card
        assert "sold_evidence" not in card
        assert "fair_value_aud" not in card
        assert "edge_pct" not in card


def test_market_catalogue_deduplicates_source_external_id_without_extra_calls():
    store = FakeStore("Cherry", 200.0)
    captured = capture_store_source(store)
    first = captured.search("NBA")
    captured.captured.extend(first)

    observations = catalogue_observations(captured, include_history=False)

    assert len(observations) == 1
    assert store.calls == 1
