from datetime import datetime, timezone

from card_scanner.candidate_discovery import (
    assess_candidate_discovery,
    rank_candidates,
)
from card_scanner.identity import parse_identity
from card_scanner.listing_history import ListingHistoryAssessment
from card_scanner.models import Listing


def listing(
    external_id="1",
    title="Victor Wembanyama 2023 Panini Select #87 Blue Prizm PSA 10",
):
    return Listing(
        source="test_store",
        external_id=external_id,
        url=f"https://example.test/{external_id}",
        title=title,
        sport="NBA",
        price=150.0,
        currency="AUD",
        shipping=0.0,
        identity=parse_identity(title, "NBA"),
    )


def history(
    external_id="1",
    price_drop=False,
    drop_pct=None,
    is_new=False,
    is_relisted=False,
    is_stale=False,
):
    now = datetime.now(timezone.utc)
    return ListingHistoryAssessment(
        source="test_store",
        external_id=external_id,
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
        is_new=is_new,
        is_price_drop=price_drop,
        is_price_increase=False,
        is_stale=is_stale,
        is_relisted=is_relisted,
        history_notes=(),
    )


def test_discovery_never_creates_buy_or_fair_value():
    result = assess_candidate_discovery(listing())
    assert result.can_create_buy is False
    assert result.fair_value_aud is None
    assert result.discovery_status not in {"BUY", "STRONG_BUY"}


def test_strong_identity_is_sold_comp_ready():
    result = assess_candidate_discovery(listing())
    assert result.sold_comp_ready is True
    assert "SOLD_COMP_READY_IDENTITY" in result.investigation_reasons


def test_price_drop_increases_discovery_priority():
    base = assess_candidate_discovery(listing())
    dropped = assess_candidate_discovery(
        listing(),
        history(price_drop=True, drop_pct=-25.0),
    )
    assert dropped.discovery_score > base.discovery_score
    assert "RECENT_PRICE_DROP" in dropped.investigation_reasons


def test_new_listing_can_raise_priority_but_not_create_buy():
    result = assess_candidate_discovery(
        listing(),
        history(is_new=True),
    )
    assert "NEW_LISTING" in result.investigation_reasons
    assert result.can_create_buy is False
    assert result.fair_value_aud is None


def test_missing_player_is_low_priority():
    item = listing(
        title="2023 Panini Select Blue Prizm PSA 10",
    )
    result = assess_candidate_discovery(item)
    assert result.sold_comp_ready is False
    assert result.discovery_status == "LOW_PRIORITY"


def test_stale_listing_is_caution_not_value_evidence():
    result = assess_candidate_discovery(
        listing(),
        history(is_stale=True),
    )
    assert "STALE_LISTING" in result.caution_reasons
    assert result.fair_value_aud is None


def test_ranking_prefers_higher_discovery_score():
    a = listing(external_id="a")
    b = listing(external_id="b")

    ranked = rank_candidates(
        [a, b],
        {
            ("test_store", "b"): history(
                external_id="b",
                price_drop=True,
                drop_pct=-30.0,
            )
        },
    )
    assert ranked[0].listing.external_id == "b"


def test_ranking_is_deterministic_for_equal_scores():
    a = listing(external_id="2", title="Z Player 2023 Panini Select #2")
    b = listing(external_id="1", title="A Player 2023 Panini Select #1")
    first = rank_candidates([a, b])
    second = rank_candidates([b, a])
    assert [x.listing.external_id for x in first] == [
        x.listing.external_id for x in second
    ]


def test_discovery_does_not_require_sold_valuation():
    result = assess_candidate_discovery(listing())
    assert not hasattr(result, "valuation")
    assert not hasattr(result, "opportunity")
