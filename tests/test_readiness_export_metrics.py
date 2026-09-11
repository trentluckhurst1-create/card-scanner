from __future__ import annotations

from types import SimpleNamespace

from card_scanner.dashboard_export import build_dashboard_payload
from card_scanner.market_catalogue import MarketListingObservation
from card_scanner.models import CardIdentity, Listing


def _summary():
    return SimpleNamespace(
        results=[],
        fetched_listings=2,
        candidates_scanned=0,
        valued_count=0,
        strong_buy_count=0,
        buy_count=0,
        watch_count=0,
        insufficient_comps_count=0,
        insufficient_identity_count=1,
        sold_queries_used=0,
        history_observed_count=0,
        history_new_count=0,
        history_price_drop_count=0,
        history_price_increase_count=0,
        history_relisted_count=0,
        history_stale_count=0,
    )


def _observation(external_id: str, identity: CardIdentity) -> MarketListingObservation:
    return MarketListingObservation(
        listing=Listing(
            source="cherry",
            external_id=external_id,
            url=f"https://example.test/{external_id}",
            title=f"2025 Topps Example Player #{external_id}",
            sport="NFL",
            price=100.0,
            currency="AUD",
            identity=identity,
        )
    )


def test_top_level_metrics_expose_governed_sold_research_readiness():
    ready = _observation(
        "10",
        CardIdentity(
            sport="NFL",
            player="Example Player",
            year="2025",
            brand="Topps",
            card_number="10",
            parallel="Gold",
        ),
    )
    not_ready = _observation(
        "11",
        CardIdentity(
            sport="NFL",
            player="Other Player",
            year="2025",
            brand="Topps",
            card_number="11",
        ),
    )

    payload = build_dashboard_payload(
        _summary(),
        generated_at="2026-09-11T00:00:00+00:00",
        market_listings=[ready, not_ready],
    )
    metrics = payload["metrics"]
    diagnostics = payload["identity_diagnostics"]

    assert metrics["sold_research_identity_ready"] == diagnostics["sold_research_ready_count"] == 1
    assert metrics["sold_research_identity_not_ready"] == diagnostics["sold_research_not_ready_count"] == 1
    assert metrics["sold_research_identity_ready_pct"] == diagnostics["sold_research_ready_pct"] == 50.0
    assert metrics["sold_research_identity_threshold"] == diagnostics["sold_identity_quality_threshold"] == 0.70

    # Exporting readiness does not add valuation or sold evidence to catalogue-only rows.
    assert all("valuation" not in card for card in payload["market_cards"])
    assert all("sold_evidence" not in card for card in payload["market_cards"])
