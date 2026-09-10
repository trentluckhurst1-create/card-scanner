from card_scanner.identity import parse_identity


def test_black_pearl_is_not_truncated_to_black():
    identity = parse_identity(
        "2024 SELECT AFL SUPREMACY Black Pearl Nick Daicos 29/35",
        "AFL",
    )

    assert identity.player == "Nick Daicos"
    assert identity.parallel == "Black Pearl"
    assert identity.serial_current == 29
    assert identity.serial_total == 35


def test_sealed_hanger_pack_is_excluded_from_card_research():
    from card_scanner.candidate_discovery import (
        assess_candidate_discovery,
        candidate_research_families,
    )
    from card_scanner.models import Listing

    title = (
        "2021 Panini Select Football Hanger Pack "
        "(Black & Gold Prizms!)"
    )

    listing = Listing(
        source="gimko",
        external_id="sealed-hanger-control",
        url="https://example.test/sealed-hanger-control",
        title=title,
        sport="NFL",
        price=39.95,
        currency="AUD",
        shipping=0.0,
        identity=parse_identity(title, "NFL"),
    )

    assessment = assess_candidate_discovery(listing)

    assert assessment.underdescription.status == "NOT_APPLICABLE"
    assert "NON_CARD_PRODUCT" in assessment.underdescription.evidence_flags
    assert assessment.discovery_status == "SKIP"
    assert assessment.sold_comp_ready is False
    assert candidate_research_families([assessment]) == []


def test_packers_card_is_not_classified_as_non_card_pack():
    from card_scanner.candidate_discovery import assess_candidate_discovery
    from card_scanner.models import Listing

    title = "2020 Panini Prizm AARON RODGERS Green Bay Packers #1"

    listing = Listing(
        source="test_store",
        external_id="packers-control",
        url="https://example.test/packers-control",
        title=title,
        sport="NFL",
        price=49.95,
        currency="AUD",
        shipping=0.0,
        identity=parse_identity(title, "NFL"),
    )

    assessment = assess_candidate_discovery(listing)

    assert assessment.underdescription.status != "NOT_APPLICABLE"
    assert "NON_CARD_PRODUCT" not in assessment.underdescription.evidence_flags
    assert assessment.discovery_status != "SKIP"


def test_afl_supremacy_team_name_does_not_replace_player():
    identity = parse_identity(
        "2022 AFL SUPREMACY ROOKIE Blue Nick Daicos COLLINGWOOD MAGPIES 61/75 RPB4",
        "AFL",
    )

    assert identity.player == "Nick Daicos"
    assert identity.parallel == "Blue"
    assert identity.serial_current == 61
    assert identity.serial_total == 75


def test_afl_supremacy_leading_insert_name_does_not_replace_player():
    identity = parse_identity(
        "2024 SELECT AFL SUPREMACY Franchise Future Signature Nick Daicos 14/70",
        "AFL",
    )

    assert identity.player == "Nick Daicos"
    assert identity.parallel is None
    assert identity.serial_current == 14
    assert identity.serial_total == 70


def test_afl_supremacy_player_surname_green_does_not_replace_blue_parallel():
    identity = parse_identity(
        "2023 AFL SUPREMACY ROOKIE Blue Steely Green Richmond 36/75",
        "AFL",
    )

    assert identity.player == "Steely Green"
    assert identity.parallel == "Blue"
    assert identity.serial_current == 36
    assert identity.serial_total == 75


def test_legitimate_plain_black_parallel_remains_black():
    identity = parse_identity(
        "2025 Select AFL Seamless DANIEL RIOLI Black 22/40 #70",
        "AFL",
    )

    assert identity.player == "Daniel Rioli"
    assert identity.parallel == "Black"
    assert identity.card_number == "70"
    assert identity.serial_current == 22
    assert identity.serial_total == 40


def test_existing_black_prizm_remains_compound_parallel():
    identity = parse_identity(
        "2023 Panini Prizm EXAMPLE PLAYER Black Prizm 8/10 #101",
        "NBA",
    )

    assert identity.player == "Example Player"
    assert identity.parallel == "Black Prizm"
    assert identity.serial_current == 8
    assert identity.serial_total == 10
    assert identity.card_number == "101"
