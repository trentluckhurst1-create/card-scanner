from dataclasses import replace

from card_scanner.candidate_discovery import assess_candidate_discovery
from card_scanner.identity import parse_identity
from card_scanner.models import Listing
from card_scanner.research_priority import (
    assess_research_priority,
    research_priority_sort_key,
)


def listing(title: str, price: float = 100.0) -> Listing:
    return Listing(
        source="test",
        external_id=title,
        url="https://example.invalid/card",
        title=title,
        sport="NBA",
        price=price,
        currency="AUD",
        shipping=0.0,
        identity=parse_identity(title, sport="NBA"),
    )


def test_research_layer_cannot_create_buy_or_fair_value():
    row = listing(
        "2023-24 Panini Prizm Victor Wembanyama #136 Silver Prizm RC"
    )
    discovery = assess_candidate_discovery(row)
    result = assess_research_priority(discovery)

    assert result.can_create_buy is False
    assert result.can_create_strong_buy is False
    assert result.fair_value_aud is None


def test_skip_discovery_stays_skip():
    row = listing(
        "2021 Panini Select Football Hanger Pack Black Gold Prizms"
    )
    discovery = assess_candidate_discovery(row)

    if discovery.discovery_status != "SKIP":
        discovery = replace(
            discovery,
            discovery_status="SKIP",
            discovery_score=0.0,
            sold_comp_ready=False,
        )

    result = assess_research_priority(discovery)

    assert result.priority == "SKIP"
    assert result.score == 0.0
    assert result.can_create_buy is False


def test_higher_discovery_quality_ranks_ahead():
    strong_row = listing(
        "2023-24 Panini Prizm Victor Wembanyama #136 Silver Prizm RC"
    )
    weak_row = listing("Victor Wembanyama Card")

    strong = assess_research_priority(
        assess_candidate_discovery(strong_row)
    )
    weak = assess_research_priority(
        assess_candidate_discovery(weak_row)
    )

    assert strong.score > weak.score
    assert research_priority_sort_key(strong) < research_priority_sort_key(weak)


def test_active_reference_is_not_fair_value_authority():
    row = listing(
        "2023-24 Panini Prizm Victor Wembanyama #136 Silver Prizm RC"
    )
    discovery = assess_candidate_discovery(row)

    result = assess_research_priority(discovery)

    assert result.fair_value_aud is None
    assert result.can_create_buy is False
    assert result.can_create_strong_buy is False


def test_score_is_bounded():
    row = listing(
        "2023-24 Panini Prizm Victor Wembanyama #136 Silver Prizm RC"
    )
    discovery = assess_candidate_discovery(row)

    result = assess_research_priority(discovery)

    assert 0.0 <= result.score <= 100.0