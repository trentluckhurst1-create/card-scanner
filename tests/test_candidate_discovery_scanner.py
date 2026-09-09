from datetime import date, datetime, timezone

import card_scanner.opportunity_scanner as scanner
from card_scanner.identity import parse_identity
from card_scanner.listing_history import (
    ListingHistoryAssessment,
    ListingHistoryBatch,
)
from card_scanner.models import Listing


def listing(external_id, title=None):
    title = title or (
        f"Victor Wembanyama 2023 Panini Select #{external_id} "
        "Blue Prizm PSA 10"
    )
    return Listing(
        source="test_store",
        external_id=str(external_id),
        url=f"https://example.test/{external_id}",
        title=title,
        sport="NBA",
        price=150.0,
        currency="AUD",
        shipping=0.0,
        identity=parse_identity(title, "NBA"),
    )


def history(item, price_drop=False, drop_pct=None):
    now = datetime.now(timezone.utc)
    return ListingHistoryAssessment(
        source=item.source,
        external_id=item.external_id,
        history_status="ACTIVE",
        first_seen_at=now,
        last_seen_at=now,
        age_days=0,
        observation_count=2,
        previous_price=200.0,
        current_price=150.0,
        min_observed_price=150.0,
        max_observed_price=200.0,
        price_change_count=int(price_drop),
        price_drop_count=int(price_drop),
        price_increase_count=0,
        last_price_change_at=now if price_drop else None,
        price_change_amount=-50.0 if price_drop else None,
        price_change_pct=drop_pct,
        latest_price_drop_pct=drop_pct,
        days_since_price_change=0 if price_drop else None,
        is_new=False,
        is_price_drop=price_drop,
        is_price_increase=False,
        is_stale=False,
        is_relisted=False,
        history_notes=(),
    )


class FakeStore:
    def __init__(self, rows):
        self.rows = rows

    def search(self, sport, query="", limit=50):
        return list(self.rows)


def test_scanner_uses_candidate_discovery_order(monkeypatch):
    ordinary = listing("87")
    dropped = listing("88")

    batch = ListingHistoryBatch(
        histories={
            (ordinary.source.casefold(), ordinary.external_id): history(
                ordinary
            ),
            (dropped.source.casefold(), dropped.external_id): history(
                dropped,
                price_drop=True,
                drop_pct=-30.0,
            ),
        },
        observed_count=2,
        state_created_count=0,
        state_updated_count=1,
        unchanged_count=1,
        price_drop_count=1,
        price_increase_count=0,
        relisted_count=0,
        stale_count=0,
        event_count=1,
        errors=(),
    )

    monkeypatch.setattr(
        scanner,
        "record_store_listing_observations",
        lambda *args, **kwargs: batch,
    )

    selected = []

    class StopAfterSelection:
        def __init__(self, provider=None, results_per_query=100):
            pass

        def scan_identity(
            self,
            source_listing_external_id,
            sport,
            identity,
            as_of=None,
            max_queries=2,
        ):
            selected.append(source_listing_external_id)
            raise RuntimeError("SELECTION_CAPTURED")

    monkeypatch.setattr(
        scanner,
        "EphemeralSoldCompEngine",
        StopAfterSelection,
    )

    try:
        scanner.scan_store_opportunities(
            store_source=FakeStore([ordinary, dropped]),
            sold_provider=object(),
            sport="NBA",
            listings_per_sport=50,
            max_candidates_per_sport=1,
            max_sold_queries=2,
            record_history=True,
            as_of=date(2026, 9, 9),
        )
    except RuntimeError as exc:
        assert str(exc) == "SELECTION_CAPTURED"
    else:
        raise AssertionError("Expected selection capture.")

    assert selected == ["88"]


def test_scanner_does_not_select_identity_below_threshold(monkeypatch):
    weak = listing(
        "weak",
        title="2023 Panini Select Blue Prizm PSA 10",
    )
    strong = listing("87")

    selected = []

    class StopAfterSelection:
        def __init__(self, provider=None, results_per_query=100):
            pass

        def scan_identity(
            self,
            source_listing_external_id,
            sport,
            identity,
            as_of=None,
            max_queries=2,
        ):
            selected.append(source_listing_external_id)
            raise RuntimeError("SELECTION_CAPTURED")

    monkeypatch.setattr(
        scanner,
        "EphemeralSoldCompEngine",
        StopAfterSelection,
    )

    try:
        scanner.scan_store_opportunities(
            store_source=FakeStore([weak, strong]),
            sold_provider=object(),
            sport="NBA",
            max_candidates_per_sport=1,
            max_sold_queries=2,
            record_history=False,
            as_of=date(2026, 9, 9),
        )
    except RuntimeError as exc:
        assert str(exc) == "SELECTION_CAPTURED"
    else:
        raise AssertionError("Expected selection capture.")

    assert selected == ["87"]


def test_candidate_discovery_does_not_change_query_cap():
    text = open(scanner.__file__, encoding="utf-8").read()
    assert "max_queries=min(2, remaining)" in text


def test_candidate_discovery_does_not_replace_valuation_authority():
    text = open(scanner.__file__, encoding="utf-8").read()
    assert "sold_result.valuation" in text
    assert "assess_opportunity(" in text
    assert "assess_mispricing(" in text
