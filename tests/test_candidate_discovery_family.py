from card_scanner.candidate_discovery import (
    allocate_research_candidates,
    assess_candidate_discovery,
    candidate_research_families,
)
from card_scanner.identity import parse_identity
from card_scanner.models import Listing


def listing(external_id: str, title: str, price: float) -> Listing:
    return Listing(
        source="cherry",
        external_id=external_id,
        url=f"https://example.test/{external_id}",
        title=title,
        sport="AFL",
        price=price,
        currency="AUD",
        shipping=0.0,
        identity=parse_identity(title, "AFL"),
    )


def assessment(external_id: str, title: str, price: float):
    return assess_candidate_discovery(
        listing(external_id, title, price)
    )


def test_serial_numerators_collapse_to_one_family():
    a = assessment(
        "a",
        "2025 Select AFL Seamless BEN CAMPOREALE Rookie Badge Signature Auto 39/70 #43",
        129.99,
    )
    b = assessment(
        "b",
        "2025 Select AFL Seamless BEN CAMPOREALE Rookie Badge Signature Auto 42/70 #43",
        119.99,
    )

    families = candidate_research_families([a, b])

    assert len(families) == 1
    assert families[0].member_count == 2
    assert families[0].representative.listing.external_id == "b"
    assert families[0].lowest_landed_aud == 119.99


def test_different_serial_denominators_remain_separate():
    a = assessment(
        "a",
        "2025 Select AFL Seamless BEN CAMPOREALE Rookie Badge Signature Auto 39/70 #43",
        129.99,
    )
    b = assessment(
        "b",
        "2025 Select AFL Seamless BEN CAMPOREALE Rookie Badge Signature Auto 12/25 #43",
        129.99,
    )

    assert len(candidate_research_families([a, b])) == 2


def test_different_parallel_remains_separate():
    a = assessment(
        "a",
        "2020 Panini Prizm LEBRON JAMES Blue Prizm /199 #1 PSA 9",
        100.0,
    )
    b = assessment(
        "b",
        "2020 Panini Prizm LEBRON JAMES Gold Prizm /10 #1 PSA 9",
        100.0,
    )

    assert len(candidate_research_families([a, b])) == 2


def test_different_grade_remains_separate():
    a = assessment(
        "a",
        "2020 Panini Prizm LEBRON JAMES Blue Prizm /199 #1 PSA 9",
        100.0,
    )
    b = assessment(
        "b",
        "2020 Panini Prizm LEBRON JAMES Blue Prizm /199 #1 PSA 10",
        100.0,
    )

    assert len(candidate_research_families([a, b])) == 2


def test_lowest_price_copy_is_family_representative():
    expensive = assessment(
        "expensive",
        "2025 Select AFL Seamless BEN CAMPOREALE Rookie Badge Signature Auto 39/70 #43",
        199.99,
    )
    cheaper = assessment(
        "cheaper",
        "2025 Select AFL Seamless BEN CAMPOREALE Rookie Badge Signature Auto 42/70 #43",
        99.99,
    )

    selected = allocate_research_candidates(
        [expensive, cheaper],
        1,
    )

    assert len(selected) == 1
    assert selected[0].listing.external_id == "cheaper"


def test_price_only_changes_research_priority_not_fair_value():
    low = assessment(
        "low",
        "2025 Bowman Draft AARON WATSON 1st Bowman Base Sky Blue 38/499 #193",
        4.99,
    )
    high = assessment(
        "high",
        "2022 Bowman Chrome FERNANDO TATIS JR. Fuchsia 205/299 #83 BGS 9.5",
        999.99,
    )

    families = candidate_research_families([high, low])

    assert families[0].representative.listing.external_id == "low"
    assert families[0].fair_value_aud is None
    assert families[0].can_create_buy is False


def test_sold_research_prioritizes_lower_friction_identity():
    restrictive = assessment(
        "restrictive",
        "2025 Select AFL Seamless BEN CAMPOREALE "
        "Rookie Badge Signature Auto Black 39/70 #43 PSA 10",
        50.0,
    )
    simpler = assessment(
        "simpler",
        "2023-24 Panini Prizm VICTOR WEMBANYAMA Silver Rookie #136",
        50.0,
    )

    families = candidate_research_families([restrictive, simpler])

    assert families[0].representative.listing.external_id == "simpler"
    assert families[0].fair_value_aud is None
    assert families[0].can_create_buy is False


def test_non_sold_ready_candidate_cannot_enter_research_budget():
    weak = assessment(
        "weak",
        "2025 Panini Prizm Blue PSA 10",
        1.0,
    )

    assert weak.sold_comp_ready is False
    assert candidate_research_families([weak]) == []


def test_limit_is_family_limit_not_listing_limit():
    a1 = assessment(
        "a1",
        "2025 Select AFL Seamless BEN CAMPOREALE Rookie Badge Signature Auto 39/70 #43",
        129.99,
    )
    a2 = assessment(
        "a2",
        "2025 Select AFL Seamless BEN CAMPOREALE Rookie Badge Signature Auto 42/70 #43",
        129.99,
    )
    b = assessment(
        "b",
        "2025 Select AFL Seamless CHARLIE NICHOLLS Rookie Badge Signature Auto 48/70 #34",
        69.99,
    )

    selected = allocate_research_candidates([a1, a2, b], 2)

    assert len(selected) == 2
    assert len({row.listing.identity.player for row in selected}) == 2


def test_zero_limit_returns_nothing():
    a = assessment(
        "a",
        "2025 Select AFL Seamless BEN CAMPOREALE Rookie Badge Signature Auto 39/70 #43",
        129.99,
    )

    assert allocate_research_candidates([a], 0) == []
