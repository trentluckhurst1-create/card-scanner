from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from card_scanner.dashboard_export import (
    build_dashboard_payload,
    canonical_family_key,
    result_to_dashboard_record,
)
from card_scanner.market_catalogue import MarketListingObservation
from card_scanner.models import CardIdentity, Listing


def _sample_result(
    *,
    valued: bool = False,
    source: str = "Cherry",
    external_id: str = "abc-123",
    price: float = 200.0,
    parallel: str | None = "Silver",
    card_number: str | None = "136",
):
    identity = SimpleNamespace(
        player="Victor Wembanyama",
        year="2023",
        brand="Panini",
        set_name="Prizm",
        card_number=card_number,
        parallel=parallel,
        serial_current=None,
        serial_total=None,
        grader=None,
        grade=None,
        autograph=False,
        memorabilia=False,
        rookie=True,
    )
    listing = SimpleNamespace(
        source=source,
        external_id=external_id,
        url=f"https://example.test/{external_id}",
        image_url="https://example.test/card.jpg",
        title="2023 Panini Prizm Victor Wembanyama Silver RC #136",
        sport="NBA",
        price=price,
        shipping=10.0,
        currency="AUD",
        identity=identity,
    )
    history = SimpleNamespace(
        history_status="PRICE_DROP",
        first_seen_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        last_seen_at=datetime(2026, 9, 11, tzinfo=timezone.utc),
        age_days=10,
        observation_count=3,
        previous_price=225.0,
        current_price=price,
        min_observed_price=price,
        max_observed_price=225.0,
        price_change_count=1,
        price_drop_count=1,
        price_increase_count=0,
        price_change_amount=-25.0,
        price_change_pct=-11.11,
        latest_price_drop_pct=11.11,
        is_new=False,
        is_price_drop=True,
        is_price_increase=False,
        is_stale=False,
        is_relisted=False,
    )
    reference = SimpleNamespace(
        status="AVAILABLE",
        accepted_count=3,
        exact_count=2,
        strong_count=1,
        stores_considered=3,
        stores_searched=3,
        lowest_aud=190.0,
        median_aud=215.0,
        trimmed_median_aud=210.0,
        discount_to_lowest_pct=-5.26,
        discount_to_median_pct=6.98,
        confidence=0.9,
    )
    research = SimpleNamespace(
        score=71.4,
        priority="CHECK",
        reasons=("PRICE_DROP", "ACTIVE_REFERENCE_DISCOUNT"),
        cautions=("INSUFFICIENT_SOLD_COMPS",),
    )
    valuation = SimpleNamespace(
        status="VALUED" if valued else "INSUFFICIENT_SOLD_COMPS",
        fair_value_aud=260.0,
    )
    opportunity = SimpleNamespace(
        status="BUY" if valued else "INSUFFICIENT_SOLD_COMPS",
        edge_pct=19.23,
    )
    return SimpleNamespace(
        listing=listing,
        identity_quality=0.94,
        listing_history=history,
        cross_store_reference=reference,
        research_priority=research,
        valuation=valuation,
        opportunity=opportunity,
        accepted_count=0 if not valued else 4,
        exact_count=0 if not valued else 3,
        strong_count=0 if not valued else 1,
        fetched_count=25,
    )


def _summary(*results):
    return SimpleNamespace(
        fetched_listings=253,
        candidates_scanned=10,
        valued_count=0,
        strong_buy_count=0,
        buy_count=0,
        watch_count=0,
        insufficient_comps_count=10,
        insufficient_identity_count=92,
        sold_queries_used=20,
        history_observed_count=253,
        history_new_count=253,
        history_price_drop_count=0,
        history_price_increase_count=0,
        history_relisted_count=0,
        history_stale_count=0,
        results=list(results),
    )


def _market_observation(*, source: str, external_id: str, discriminator: bool) -> MarketListingObservation:
    identity = CardIdentity(
        sport="NFL",
        player="Test Player",
        year="2025",
        brand="Topps",
        card_number="10" if discriminator else None,
    )
    return MarketListingObservation(
        listing=Listing(
            source=source,
            external_id=external_id,
            url=f"https://example.test/{external_id}",
            title=f"Test card {external_id}",
            sport="NFL",
            price=100.0,
            currency="AUD",
            identity=identity,
        )
    )


def test_insufficient_sold_evidence_never_exports_fair_value_or_edge():
    row = result_to_dashboard_record(_sample_result(valued=False))
    assert row["valuation"]["status"] == "INSUFFICIENT_SOLD_COMPS"
    assert row["valuation"]["fair_value_aud"] is None
    assert row["valuation"]["edge_pct"] is None
    assert row["research"]["can_create_buy"] is False
    assert row["research"]["fair_value_aud"] is None


def test_active_market_reference_remains_separate_from_valuation():
    row = result_to_dashboard_record(_sample_result(valued=False))
    assert row["active_market_reference"]["median_aud"] == 215.0
    assert row["valuation"]["fair_value_aud"] is None
    assert row["opportunity_status"] == "INSUFFICIENT_SOLD_COMPS"


def test_valued_result_can_export_governed_fair_value_and_edge():
    row = result_to_dashboard_record(_sample_result(valued=True))
    assert row["valuation"]["status"] == "VALUED"
    assert row["valuation"]["fair_value_aud"] == 260.0
    assert row["valuation"]["edge_pct"] == 19.23
    assert row["opportunity_status"] == "BUY"


def test_family_key_requires_structured_discriminator_and_changes_with_variant():
    base_identity = {
        "player": "Victor Wembanyama",
        "year": "2023",
        "brand": "Panini",
        "set_name": "Prizm",
        "card_number": "136",
        "parallel": "Silver",
        "serial_total": None,
        "grader": None,
        "grade": None,
        "autograph": False,
        "memorabilia": False,
        "rookie": True,
    }
    key = canonical_family_key(sport="NBA", identity=base_identity)
    assert key and key.startswith("cf_")
    different_parallel = dict(base_identity, parallel="Red")
    assert canonical_family_key(sport="NBA", identity=different_parallel) != key
    weak = dict(base_identity, card_number=None, parallel=None, serial_total=None)
    assert canonical_family_key(sport="NBA", identity=weak) is None


def test_cross_store_family_groups_only_same_strict_identity_and_keeps_asks_non_valuation():
    cherry = _sample_result(source="Cherry", external_id="cherry-1", price=200.0)
    gimko = _sample_result(source="Gimko", external_id="gimko-1", price=180.0)
    other_parallel = _sample_result(source="Urban Empire", external_id="urban-1", price=150.0, parallel="Red")
    payload = build_dashboard_payload(_summary(cherry, gimko, other_parallel), generated_at="2026-09-11T00:00:00+00:00")
    assert payload["metrics"]["cross_store_families"] == 1
    family = payload["cross_store_families"][0]
    assert family["store_count"] == 2
    assert family["listing_count"] == 2
    assert family["stores"] == ["Cherry", "Gimko"]
    assert family["lowest_active_ask_aud"] == 190.0
    assert family["median_active_ask_aud"] == 200.0
    assert family["highest_active_ask_aud"] == 210.0
    assert family["pricing_basis"] == "ACTIVE_ASKS_ONLY_NOT_FAIR_VALUE"
    assert "fair_value" not in family


def test_payload_contains_safe_history_metrics_and_no_provider_raw_fields():
    payload = build_dashboard_payload(_summary(_sample_result()), generated_at="2026-09-11T00:00:00+00:00")
    assert payload["schema_version"] == 1
    assert payload["metrics"]["history_observed"] == 253
    assert payload["metrics"]["history_new"] == 253
    assert payload["metrics"]["cross_store_families"] == 0
    assert payload["cards"][0]["history"]["is_price_drop"] is True
    assert payload["cards"][0]["card_family"]["eligible"] is True
    serialized = repr(payload).casefold()
    assert "api_key" not in serialized
    assert "client_secret" not in serialized
    assert "raw_response" not in serialized


def test_payload_exports_diagnostic_identity_summary_without_changing_market_rows():
    observations = [
        _market_observation(source="Cherry", external_id="eligible", discriminator=True),
        _market_observation(source="Gimko", external_id="ineligible", discriminator=False),
    ]
    payload = build_dashboard_payload(
        _summary(),
        generated_at="2026-09-11T00:00:00+00:00",
        market_listings=observations,
    )
    diagnostic = payload["identity_diagnostics"]
    assert diagnostic["listing_count"] == 2
    assert diagnostic["family_eligible_count"] == 1
    assert diagnostic["family_ineligible_count"] == 1
    assert diagnostic["gap_counts"] == {"MISSING_STRUCTURED_DISCRIMINATOR": 1}
    assert payload["metrics"]["family_eligible"] == 1
    assert payload["metrics"]["family_ineligible"] == 1
    assert all(card["research_status"] == "NOT_RESEARCHED_IN_THIS_SCAN" for card in payload["market_cards"])
    assert all("valuation" not in card for card in payload["market_cards"])
    assert all("sold_evidence" not in card for card in payload["market_cards"])
