from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from card_scanner.dashboard_export import (
    build_dashboard_payload,
    result_to_dashboard_record,
)


def _sample_result(*, valued: bool = False):
    identity = SimpleNamespace(
        player="Victor Wembanyama",
        year="2023",
        brand="Panini",
        set_name="Prizm",
        card_number="136",
        parallel="Silver",
        serial_current=None,
        serial_total=None,
        grader=None,
        grade=None,
        autograph=False,
        memorabilia=False,
        rookie=True,
    )
    listing = SimpleNamespace(
        source="Cherry",
        external_id="abc-123",
        url="https://example.test/card",
        image_url="https://example.test/card.jpg",
        title="2023 Panini Prizm Victor Wembanyama Silver RC #136",
        sport="NBA",
        price=200.0,
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
        current_price=200.0,
        min_observed_price=200.0,
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
        fair_value_aud=260.0 if valued else 260.0,
    )
    opportunity = SimpleNamespace(
        status="BUY" if valued else "INSUFFICIENT_SOLD_COMPS",
        edge_pct=19.23 if valued else 19.23,
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


def _summary(result):
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
        results=[result],
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


def test_payload_contains_safe_history_metrics_and_no_provider_raw_fields():
    payload = build_dashboard_payload(
        _summary(_sample_result()),
        generated_at="2026-09-11T00:00:00+00:00",
    )

    assert payload["schema_version"] == 1
    assert payload["metrics"]["history_observed"] == 253
    assert payload["metrics"]["history_new"] == 253
    assert payload["cards"][0]["history"]["is_price_drop"] is True
    serialized = repr(payload).casefold()
    assert "api_key" not in serialized
    assert "client_secret" not in serialized
    assert "raw_response" not in serialized
